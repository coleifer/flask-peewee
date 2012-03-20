import datetime
import operator

from flask import request
from flask_peewee.utils import models_to_path
from peewee import *


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
    'year_eq': 'year is',
    'year_lt': 'year is less than...',
    'year_gt': 'year is greater than...',
}

FIELD_TYPES = {
    'foreign_key': [ForeignKeyField],
    'text': [CharField, TextField],
    'numeric': [PrimaryKeyField, IntegerField, FloatField, DecimalField, DoubleField],
    'boolean': [BooleanField],
    'datetime': [DateTimeField],
}

INV_FIELD_TYPES = dict((v,k) for k in FIELD_TYPES for v in FIELD_TYPES[k])

FIELDS_TO_LOOKUPS = {
    'foreign_key': ['eq', 'in'],
    'text': ['eq', 'icontains', 'istartswith'],
    'numeric': ['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in'],
    'boolean': ['eq'],
    'datetime': ['today', 'yesterday', 'this_week', 'lte_days_ago', 'gte_days_ago', 'year_eq', 'year_lt', 'year_gt'],
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

def _rd(n):
    return datetime.date.today() + datetime.timedelta(days=n)

def yr_l(n):
    return datetime.datetime(year=n, month=1, day=1)

def yr_h(n):
    return datetime.datetime.combine(
        datetime.date(year=n, month=12, day=31),
        datetime.time.max,
    )


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

    def process_year_eq(self, field_part, values):
        return [{
            '%s__gte' % field_part: yr_l(int(value)),
            '%s__lte' % field_part: yr_h(int(value)),
        } for value in values]

    def process_year_lt(self, field_part, values):
        return [{
            '%s__lt' % field_part: yr_l(int(value)),
        } for value in values]

    def process_year_gt(self, field_part, values):
        return [{
            '%s__gte' % field_part: yr_l(int(value)),
        } for value in values]


class QueryFilter(object):
    def __init__(self, query, exclude=None, ignore_filters=None):
        self.query = query
        self.model = self.query.model

        self.exclude = exclude or ()
        self.ignore_filters = ignore_filters or ()

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

            if column not in self.exclude:
                lookups_by_column.setdefault(column, [])
                lookups_by_column[column].append(Q(**filter_dict))

        return [reduce(operator.or_, lookups) for lookups in lookups_by_column.values()]

    def get_filtered_query(self):
        nodes = self.process_request()
        if nodes:
            return self.query.filter(*nodes)

        return self.query


FIELD_TYPES = ('text', 'select', 'select_multiple', 'hidden', 'foreign_key', 'foreign_key_multiple')

class Lookup(object):
    def __init__(self, field, lookup, field_type, data=None, prefix=''):
        self.field = field
        self.lookup = lookup
        self.field_type = field_type
        self.data = data
        self.prefix = prefix

        self.name = '%s%s__%s' % (self.prefix, self.field.name, self.lookup)
        self.lookup_name = None

    def get_request(self):
        if self.lookup == 'in':
            return request.args.getlist(self.name)
        else:
            return request.args.get(self.name)

    def get_repr(self, default=''):
        if self.name in request.args:
            if self.lookup == 'in':
                pk_list = request.args.getlist(self.name)
            else:
                pk_list = [request.args.get(self.name)]
            return dict([
                (pk, unicode(self.get_by_pk(pk))) \
                    for pk in pk_list
            ])
        return default

    def get_by_pk(self, pk):
        if not isinstance(self.field, ForeignKeyField):
            raise TypeError('field %s is not a foreign key field' % self.field.name)
        model_class = self.data
        return model_class.get(**{model_class._meta.pk_name: pk})
