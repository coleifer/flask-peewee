import datetime
import operator

from flask import request
from flask_peewee.utils import models_to_path
from peewee import *
from wtforms import fields, form, widgets
from wtfpeewee.fields import ModelSelectField, ModelSelectMultipleField


class BooleanSelectField(fields.SelectFieldBase):
    widget = widgets.Select()

    def iter_choices(self):
        yield ('1', 'True', self.data)
        yield ('', 'False', not self.data)

    def process_data(self, value):
        try:
            self.data = bool(value)
        except (ValueError, TypeError):
            self.data = None

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = bool(valuelist[0])
            except ValueError:
                raise ValueError(self.gettext(u'Invalid Choice: could not coerce'))


LOOKUP_TYPES = {
    'eq': 'equal to',
    'lt': 'less than',
    'gt': 'greater than',
    'lte': 'less than or equal to',
    'gte': 'greater than or equal to',
    'ne': 'not equal to',
    'istartswith': 'starts with',
    'icontains': 'contains',
    'in': 'is one of',
    
    # special lookups that require some preprocessing
    'today': 'is today',
    'yesterday': 'is yesterday',
    'this_week': 'this week',
    'lte_days_ago': 'less than ... days ago',
    'gte_days_ago': 'greater than ... days ago',
}

FIELD_TYPES = {
    'foreign_key': [ForeignKeyField],
    'text': [CharField, TextField],
    'numeric': [PrimaryKeyField, IntegerField, FloatField, DecimalField],
    'boolean': [BooleanField],
    'datetime': [DateTimeField],
}

INV_FIELD_TYPES = dict((v,k) for k in FIELD_TYPES for v in FIELD_TYPES[k])

FIELDS_TO_LOOKUPS = {
    'foreign_key': ['eq', 'in'],
    'text': ['eq', 'icontains', 'istartswith'],
    'numeric': ['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in'],
    'boolean': ['eq'],
    'datetime': ['today', 'yesterday', 'this_week', 'lte_days_ago', 'gte_days_ago'],
}

CONVERTERS = {
    (ForeignKeyField, 'eq'): lambda f: ModelSelectField(model=f.to),
    (ForeignKeyField, 'in'): lambda f: ModelSelectMultipleField(model=f.to),
    (DateTimeField, 'today'): lambda f: fields.HiddenField(),
    (DateTimeField, 'yesterday'): lambda f: fields.HiddenField(),
    (DateTimeField, 'this_week'): lambda f: fields.HiddenField(),
    (BooleanField, 'eq'): lambda f: BooleanSelectField(),
}


def is_valid_lookup(model, lookup):
    lookups = lookup.split('__')
    lookup_type = 'eq'
    
    if len(lookups) > 1 and lookups[-1] in LOOKUP_TYPES:
        lookup_type = lookups.pop()
    
    curr = model
    for rel_field in lookups[:-1]:
        if rel_field in curr._meta.rel_fields:
            # is this a lookup using the descriptor name of a foreign key field,
            # if so change it to the actual field name, e.g. user -> user_id
            rel_field = curr._meta.rel_fields[rel_field]
        
        if rel_field in curr._meta.fields:
            field_obj = curr._meta.fields[rel_field]
            if isinstance(field_obj, ForeignKeyField):
                curr = field_obj.to
            else:
                return False
        else:
            if rel_field in curr._meta.reverse_relations:
                curr = curr._meta.reverse_relations[rel_field]
            else:
                return False
    
    lookup = lookups[-1]
    if lookup in curr._meta.rel_fields:
        lookup = curr._meta.rel_fields[lookup]

    if lookup not in curr._meta.fields:
        return False
    
    field_obj = curr._meta.fields[lookup]
    if lookup_type not in FIELDS_TO_LOOKUPS[INV_FIELD_TYPES[type(field_obj)]]:
        return False
    
    return (curr, lookup, lookup_type)

def lookups_for_field(field):
    """
    Get a list of valid lookups for a given field type.  Lookups are expressed
    as a 2-tuple of (<lookup suffix>, <human description>)
    
    >>> lookups_for_field(User.username)
    [('eq', 'equal to'), ('icontains', 'contains'), ('istartswith', 'starts with')]
    """
    field_class = type(field)
    return [
        (lookup, LOOKUP_TYPES[lookup]) \
            for lookup in FIELDS_TO_LOOKUPS[INV_FIELD_TYPES[field_class]]
    ]

class Lookup(object):
    def __init__(self, field):
        self.field = field
        
        self.field_class = type(self.field)
        self.field_name = self.field.name
        self.verbose_name = self.field.verbose_name
        self.model = field.model
    
    def __repr__(self):
        return '<Lookups for: %s.%s>' % (self.model.__name__, self.field_name)

    def __eq__(self, rhs):
        return self.field == rhs.field

    def get_field_type(self):
        return INV_FIELD_TYPES[self.field_class]
    
    def get_lookups(self):
        return lookups_for_field(self.field)
    
    def to_context(self):
        return dict(
            name=self.field_name,
            verbose_name=self.verbose_name,
            field_type=self.get_field_type(),
            lookups=self.get_lookups(),
            prefix=prefix,
        )
    
    def html_fields(self):
        default = lambda f: fields.TextField()
        return dict([
            (
                '%s__%s' % (self.field_name, lookup[0]),
                CONVERTERS.get((self.field_class, lookup[0]), default)(self.field)
            ) for lookup in self.get_lookups()
        ])

class ModelLookup(object):
    def __init__(self, model, exclude, path, raw_id_fields):
        self.model = model
        self.exclude = exclude
        self.path = path
        self.raw_id_fields = raw_id_fields
    
    def get_lookups(self):
        return [
            Lookup(f) for f in self.model._meta.get_fields() \
                if f.name not in self.exclude
        ]
    
    def get_prefix(self):
        if not self.path:
            return ''
        return models_to_path(self.path) + '__'
    
    def get_html_fields(self):
        fields = {}
        for lookup in self.get_lookups():
            fields.update(lookup.html_fields())
        return fields
    
    def html_form(self):
        frm = form.BaseForm(self.get_html_fields(), prefix=self.get_prefix())
        frm.process(None)
        return frm

def _rd(n):
    return datetime.date.today() + datetime.timedelta(days=n)


class FilterPreprocessor(object):
    def process_lookup(self, raw_lookup, values=None):
        """
        Returns a list of dictionaries
        """
        if '__' in raw_lookup:
            field_part, lookup = raw_lookup.rsplit('__', 1)
            if hasattr(self, 'process_%s' % lookup):
                return getattr(self, 'process_%s' % lookup)(field_part, values)
        
        return [{raw_lookup: v} for v in values]
    
    def process_in(self, field_part, values):
        return [{'%s__in' % field_part: values}]
    
    def process_today(self, field_part, values):
        return [{
            '%s__gte' % field_part: _rd(0),
            '%s__lt' % field_part: _rd(1),
        }]
    
    def process_yesterday(self, field_part, values):
        return [{
            '%s__gte' % field_part: _rd(-1),
            '%s__lt' % field_part: _rd(0),
        }]
    
    def process_this_week(self, field_part, values):
        return [{
            '%s__gte' % field_part: _rd(-6),
            '%s__lt' % field_part: _rd(1),
        }]
    
    def process_lte_days_ago(self, field_part, values):
        return [{
            '%s__gte' % field_part: _rd(-1 * int(value)),
        } for value in values]
    
    def process_gte_days_ago(self, field_part, values):
        return [{
            '%s__lte' % field_part: _rd(-1 * int(value)),
        } for value in values]


class QueryFilter(object):
    def __init__(self, query, exclude_fields=None, ignore_filters=None, raw_id_fields=None, related=None):
        self.query = query
        self.model = self.query.model

        # fix any foreign key fields
        self.exclude_fields = []
        for field_name in exclude_fields or ():
            if field_name in self.model._meta.fields:
                self.exclude_fields.append(field_name)
            else:
                self.exclude_fields.append(self.model._meta.rel_fields[field_name])
        
        self.ignore_filters = ignore_filters or ()
        self.raw_id_fields = raw_id_fields or ()
        
        # a list of related QueryFilter() objects
        self.related = related or ()
    
    def get_model_lookups(self, path=None):
        model_lookups = [ModelLookup(self.model, self.exclude_fields, path, self.raw_id_fields)]
        path = path or []
        path.append(self.model)
        for related_filter in self.related:
            model_lookups.extend(
                related_filter.get_model_lookups(list(path))
            )
        return model_lookups
    
    def get_preprocessor(self):
        return FilterPreprocessor()
    
    def process_request(self):
        self.raw_lookups = []
        
        filters = []
        lookups_by_column = {}
        
        preprocessor = self.get_preprocessor()
        
        # preprocessing -- essentially a place to store "raw" filters (used to
        # reconstruct filter widgets on frontend), and a place to munge filters
        # that have special meaning, i.e. "today"
        for key in request.args:
            if key in self.ignore_filters:
                continue

            if not is_valid_lookup(self.model, key):
                continue
            
            values = request.args.getlist(key)
            if key.endswith('__in'):
                self.raw_lookups.append((key, values))
            else:
                for v in values:
                    self.raw_lookups.append((key, v))
            
            # preprocessor returns a list of filters to apply
            filters.extend(preprocessor.process_lookup(key, values))
        
        # at this point, need to figure out which parts of the query to "AND"
        # together and which to "OR" together ... this is naive and simply groups
        # lookups on the same column together in an OR clause.
        for filter_dict in filters:
            for field_part, value in filter_dict.items():
                if '__' in field_part:
                    column, lookup = field_part.rsplit('__', 1)
                else:
                    column = field_part
            
            lookups_by_column.setdefault(column, [])
            lookups_by_column[column].append(Q(**filter_dict))
        
        return [reduce(operator.or_, lookups) for lookups in lookups_by_column.values()]
    
    def get_filtered_query(self):
        nodes = self.process_request()
        if nodes:
            return self.query.filter(*nodes)
        
        return self.query
