import datetime
import operator

from flask import request
from peewee import *
from wtforms import fields
from wtforms import form
from wtforms import validators
from wtforms import widgets

from flask_peewee.forms import BaseModelConverter
from flask_peewee._compat import reduce


class QueryFilter(object):
    """
    Basic class representing a named field (with or without a list of options)
    and an operation against a given value
    """
    def __init__(self, field, name, options=None):
        self.field = field
        self.name = name
        self.options = options

    def query(self, value):
        raise NotImplementedError

    def operation(self):
        raise NotImplementedError

    def get_options(self):
        return self.options


class EqualQueryFilter(QueryFilter):
    def query(self, value):
        return self.field == value

    def operation(self):
        return 'equal to'


class NotEqualQueryFilter(QueryFilter):
    def query(self, value):
        return self.field != value

    def operation(self):
        return 'not equal to'


class LessThanQueryFilter(QueryFilter):
    def query(self, value):
        return self.field < value

    def operation(self):
        return 'less than'


class LessThanEqualToQueryFilter(QueryFilter):
    def query(self, value):
        return self.field <= value

    def operation(self):
        return 'less than or equal to'


class GreaterThanQueryFilter(QueryFilter):
    def query(self, value):
        return self.field > value

    def operation(self):
        return 'greater than'


class GreaterThanEqualToQueryFilter(QueryFilter):
    def query(self, value):
        return self.field >= value

    def operation(self):
        return 'greater than or equal to'


class StartsWithQueryFilter(QueryFilter):
    def query(self, value):
        return fn.Lower(fn.Substr(self.field, 1, len(value))) == value.lower()

    def operation(self):
        return 'starts with'


class ContainsQueryFilter(QueryFilter):
    def query(self, value):
        return self.field ** ('%%%s%%' % value)

    def operation(self):
        return 'contains'


class YearFilter(QueryFilter):
    def query(self, value):
        value = int(value)
        return self.field.year == value

    def operation(self):
        return 'year equals'


class MonthFilter(QueryFilter):
    def query(self, value):
        value = int(value)
        return self.field.month == value

    def operation(self):
        return 'month equals'


class WithinDaysAgoFilter(QueryFilter):
    def query(self, value):
        value = int(value)
        return self.field >= (
            datetime.date.today() - datetime.timedelta(days=value))

    def operation(self):
        return 'within X days ago'


class OlderThanDaysAgoFilter(QueryFilter):
    def query(self, value):
        value = int(value)
        return self.field < (
            datetime.date.today() - datetime.timedelta(days=value))

    def operation(self):
        return 'older than X days ago'


class FilterMapping(object):
    """
    Map a peewee field to a list of valid query filters for that field
    """
    string = (
        EqualQueryFilter, NotEqualQueryFilter, StartsWithQueryFilter,
        ContainsQueryFilter)
    numeric = (
        EqualQueryFilter, NotEqualQueryFilter, LessThanQueryFilter,
        GreaterThanQueryFilter, LessThanEqualToQueryFilter,
        GreaterThanEqualToQueryFilter)
    datetime_date = (numeric + (
        WithinDaysAgoFilter, OlderThanDaysAgoFilter, YearFilter, MonthFilter))
    foreign_key = (EqualQueryFilter, NotEqualQueryFilter)
    boolean = (EqualQueryFilter, NotEqualQueryFilter)

    def get_field_types(self):
        return {
            CharField: 'string',
            TextField: 'string',
            DateTimeField: 'datetime_date',
            DateField: 'datetime_date',
            TimeField: 'numeric',
            IntegerField: 'numeric',
            BigIntegerField: 'numeric',
            FloatField: 'numeric',
            DoubleField: 'numeric',
            DecimalField: 'numeric',
            BooleanField: 'boolean',
            AutoField: 'numeric',
            ForeignKeyField: 'foreign_key',
        }

    def convert(self, field):
        mapping = self.get_field_types()

        for klass in type(field).__mro__:
            if klass in mapping:
                mapping_fn = getattr(self, 'convert_%s' % mapping[klass])
                return mapping_fn(field)

        # fall back to numeric
        return self.convert_numeric(field)

    def convert_string(self, field):
        return [f(field, field.verbose_name, field.choices) for f in self.string]

    def convert_numeric(self, field):
        return [f(field, field.verbose_name, field.choices) for f in self.numeric]

    def convert_datetime_date(self, field):
        return [f(field, field.verbose_name, field.choices) for f in self.datetime_date]

    def convert_boolean(self, field):
        boolean_choices = [('True', '1', 'False', '')]
        return [f(field, field.verbose_name, boolean_choices) for f in self.boolean]

    def convert_foreign_key(self, field):
        return [f(field, field.verbose_name, field.choices) for f in self.foreign_key]


class FieldTreeNode(object):
    def __init__(self, model, fields, children=None):
        self.model = model
        self.fields = fields
        self.children = children or {}


def make_field_tree(model, fields, exclude, force_recursion=False, seen=None):
    no_explicit_fields = fields is None # assume we want all of them
    if no_explicit_fields:
        fields = model._meta.sorted_field_names
    exclude = exclude or []
    seen = seen or set()

    model_fields = []
    children = {}

    for field_obj in model._meta.sorted_fields:
        if field_obj.name in exclude or field_obj in seen:
            continue

        if field_obj.name in fields:
            model_fields.append(field_obj)

        if isinstance(field_obj, ForeignKeyField):
            seen.add(field_obj)
            if no_explicit_fields:
                rel_fields = None
            else:
                rel_fields = [
                    rf.replace('%s__' % field_obj.name, '') \
                        for rf in fields if rf.startswith('%s__' % field_obj.name)
                ]
                if not rel_fields and force_recursion:
                    rel_fields = None

            rel_exclude = [
                rx.replace('%s__' % field_obj.name, '') \
                    for rx in exclude if rx.startswith('%s__' % field_obj.name)
            ]
            children[field_obj.name] = make_field_tree(field_obj.rel_model, rel_fields, rel_exclude, force_recursion, seen)

    return FieldTreeNode(model, model_fields, children)


class SmallSelectWidget(widgets.Select):
    def __call__(self, field, **kwargs):
        kwargs['class'] = 'span2'
        return super(SmallSelectWidget, self).__call__(field, **kwargs)


class FilterForm(object):
    base_class = form.Form
    separator = '-'
    field_operation_prefix = 'fo_'
    field_value_prefix = 'fv_'
    field_relation_prefix = 'fr_'

    def __init__(self, model, model_converter, filter_mapping, fields=None, exclude=None):
        self.model = model
        self.model_converter = model_converter
        self.filter_mapping = filter_mapping

        # convert fields and exclude into a tree
        self._field_tree = make_field_tree(model, fields, exclude)

        self._query_filters = self.load_query_filters()

    def load_query_filters(self):
        query_filters = {}
        queue = [self._field_tree]

        while queue:
            curr = queue.pop(0)
            for field in curr.fields:
                query_filters[field] = self.filter_mapping.convert(field)
            queue.extend(curr.children.values())

        return query_filters

    def get_operation_field(self, field):
        choices = []
        for i, query_filter in enumerate(self._query_filters[field]):
            choices.append((str(i), query_filter.operation()))

        return fields.SelectField(choices=choices, validators=[validators.Optional()], widget=SmallSelectWidget())

    def get_field_default(self, field):
        if isinstance(field, DateTimeField):
            return datetime.datetime.now()
        elif isinstance(field, DateField):
            return datetime.date.today()
        elif isinstance(field, TimeField):
            return datetime.time(0, 0)
        return field.default

    def get_value_field(self, field):
        field_name, form_field = self.model_converter.convert(field.model, field, None)

        form_field.kwargs['default'] = self.get_field_default(field)
        form_field.kwargs['validators'] = [validators.Optional()]
        return form_field

    def get_field_dict(self, node=None, prefix=None):
        field_dict = {}
        node = node or self._field_tree

        for field in node.fields:
            op_field = self.get_operation_field(field)
            val_field = self.get_value_field(field)
            field_dict['%s%s' % (self.field_operation_prefix, field.name)] = op_field
            field_dict['%s%s' % (self.field_value_prefix, field.name)] = val_field

        for prefix, node in node.children.items():
            child_fd = self.get_field_dict(node, prefix)
            field_dict['%s%s' % (self.field_relation_prefix, prefix)] = fields.FormField(
                self.get_form(child_fd),
                separator=self.separator,
            )

        return field_dict

    def get_form(self, field_dict):
        return type(
            self.model.__name__ + 'FilterForm',
            (self.base_class, ),
            field_dict,
        )

    def parse_query_filters(self):
        # reconstruct the "select" and "value" fields we are searching for in the
        # arguments from the request by depth-first searching the field tree --
        # basically what we should have at the end is the field we're querying,
        # the type of query (QueryFilter), the value requested, and the path we
        # took to get there (joins)
        accum = {}

        def _dfs(node, prefix, models, join_columns):
            for field in node.fields:
                qf_select = self.field_operation_prefix.join((prefix, field.name))
                qf_value = self.field_value_prefix.join((prefix, field.name))

                if qf_select in request.args and qf_value in request.args:
                    accum.setdefault(field, [])
                    accum[field].append((
                        request.args.getlist(qf_select),
                        request.args.getlist(qf_value),
                        models,
                        join_columns,
                        qf_select,
                        qf_value,
                    ))

            for child_prefix, child in node.children.items():
                new_prefix = prefix + self.field_relation_prefix + child_prefix + self.separator
                model_copy = list(models) + [child.model]
                join_copy = list(join_columns) + [node.model._meta.fields[child_prefix]]
                _dfs(child, new_prefix, model_copy, join_copy)

        _dfs(self._field_tree, '', [], [])

        return accum

    def process_request(self, query):
        field_dict = self.get_field_dict()
        FormClass = self.get_form(field_dict)

        form = FormClass(request.args)
        query_filters = self.parse_query_filters()
        cleaned = []

        for field, filters in query_filters.items():
            for (filter_idx_list, filter_value_list, path, join_path, qf_s, qf_v) in filters:
                query = query.switch(self.model)
                for join, model in zip(join_path, path):
                    query = query.join(model, on=join)

                q_objects = []
                for filter_idx, filter_value in zip(filter_idx_list, filter_value_list):
                    idx = int(filter_idx)
                    cleaned.append((qf_s, idx, qf_v, filter_value))
                    query_filter = self._query_filters[field][idx]
                    q_objects.append(query_filter.query(field.db_value(filter_value)))

                query = query.where(reduce(operator.or_, q_objects))

        return form, query, cleaned


class FilterModelConverter(BaseModelConverter):
    def __init__(self, *args, **kwargs):
        super(FilterModelConverter, self).__init__(*args, **kwargs)
        self.defaults = dict(self.defaults)
        self.defaults[TextField] = fields.StringField
        self.defaults[DateTimeField] = fields.DateTimeField
