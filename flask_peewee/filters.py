import datetime
import operator

from flask import request
from peewee import *
from wtforms import fields
from wtforms import form
from wtforms import validators
from wtforms import widgets

from flask_peewee.forms import BaseModelConverter
from functools import reduce


class QueryFilter(object):
    """
    Basic class representing a named field (with or without a list of options)
    and an operation against a given value
    """
    # stable name identifying this operation in query-strings.
    key = None

    # override the value input's HTML type for this operation, e.g. 'number'
    # for operations that take a count or year rather than a date.
    input_type = None

    def __init__(self, field, name, options=None):
        self.field = field
        self.name = name
        self.options = options

    def clean(self, value):
        return self.field.db_value(value)

    def query(self, value):
        raise NotImplementedError

    def operation(self):
        raise NotImplementedError

    def get_options(self):
        return self.options


class EqualQueryFilter(QueryFilter):
    key = 'eq'

    def query(self, value):
        return self.field == value

    def operation(self):
        return 'equal to'


class NotEqualQueryFilter(QueryFilter):
    key = 'ne'

    def query(self, value):
        return self.field != value

    def operation(self):
        return 'not equal to'


class LessThanQueryFilter(QueryFilter):
    key = 'lt'

    def query(self, value):
        return self.field < value

    def operation(self):
        return 'less than'


class LessThanEqualToQueryFilter(QueryFilter):
    key = 'lte'

    def query(self, value):
        return self.field <= value

    def operation(self):
        return 'less than or equal to'


class GreaterThanQueryFilter(QueryFilter):
    key = 'gt'

    def query(self, value):
        return self.field > value

    def operation(self):
        return 'greater than'


class GreaterThanEqualToQueryFilter(QueryFilter):
    key = 'gte'

    def query(self, value):
        return self.field >= value

    def operation(self):
        return 'greater than or equal to'


class StartsWithQueryFilter(QueryFilter):
    key = 'startswith'

    def clean(self, value):
        return value

    def query(self, value):
        return fn.Lower(fn.Substr(self.field, 1, len(value))) == value.lower()

    def operation(self):
        return 'starts with'


class ContainsQueryFilter(QueryFilter):
    key = 'contains'

    def clean(self, value):
        return value

    def query(self, value):
        return self.field ** ('%%%s%%' % value)

    def operation(self):
        return 'contains'


class YearFilter(QueryFilter):
    key = 'year'
    input_type = 'number'

    def clean(self, value):
        return int(value)

    def query(self, value):
        return self.field.year == value

    def operation(self):
        return 'year equals'


class MonthFilter(QueryFilter):
    key = 'month'
    input_type = 'number'

    def clean(self, value):
        return int(value)

    def query(self, value):
        return self.field.month == value

    def operation(self):
        return 'month equals'


class WithinDaysAgoFilter(QueryFilter):
    key = 'within_days'
    input_type = 'number'

    def clean(self, value):
        return int(value)

    def query(self, value):
        return self.field >= (
            datetime.date.today() - datetime.timedelta(days=value))

    def operation(self):
        return 'within X days ago'


class OlderThanDaysAgoFilter(QueryFilter):
    key = 'older_days'
    input_type = 'number'

    def clean(self, value):
        return int(value)

    def query(self, value):
        return self.field < (
            datetime.date.today() - datetime.timedelta(days=value))

    def operation(self):
        return 'older than X days ago'


class BooleanEqualQueryFilter(EqualQueryFilter):
    def clean(self, value):
        if isinstance(value, str) and value.lower() in ('0', 'false', 'f', ''):
            return False
        return True


class BooleanNotEqualQueryFilter(BooleanEqualQueryFilter):
    key = 'ne'

    def query(self, value):
        return self.field != value

    def operation(self):
        return 'not equal to'


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
    boolean = (BooleanEqualQueryFilter, BooleanNotEqualQueryFilter)

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

        # binary fields have no meaningful filter operation.
        if field_obj.name in fields and not isinstance(field_obj, BlobField):
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
        kwargs['class'] = 'form-select form-select-sm w-auto'
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
        self._filter_lookup = dict(
            (field, dict((qf.key, qf) for qf in query_filters))
            for field, query_filters in self._query_filters.items())

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
        for query_filter in self._query_filters[field]:
            if query_filter.input_type:
                choices.append((query_filter.key, query_filter.operation(),
                                {'data-input-type': query_filter.input_type}))
            else:
                choices.append((query_filter.key, query_filter.operation()))

        return fields.SelectField(choices=choices, validators=[validators.Optional()], widget=SmallSelectWidget())

    def get_query_filter(self, field, filter_key):
        try:
            return self._filter_lookup[field][filter_key]
        except KeyError:
            pass

        # fall back to the old positional protocol, e.g. fo_username=2.
        if filter_key.isdigit():
            query_filters = self._query_filters[field]
            idx = int(filter_key)
            if idx < len(query_filters):
                return query_filters[idx]

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

        def _dfs(node, prefix, models, join_columns, path_names):
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
                        ' / '.join(path_names + [field.name]),
                    ))

            for child_prefix, child in node.children.items():
                new_prefix = prefix + self.field_relation_prefix + child_prefix + self.separator
                model_copy = list(models) + [child.model]
                join_copy = list(join_columns) + [node.model._meta.fields[child_prefix]]
                _dfs(child, new_prefix, model_copy, join_copy, path_names + [child_prefix])

        _dfs(self._field_tree, '', [], [], [])

        return accum

    def resolve_form_field(self, form, name):
        # fr_user-fo_username -> form['fr_user'].form['fo_username']
        parts = name.split(self.separator)
        obj = form
        for part in parts[:-1]:
            obj = obj[part].form
        return obj[parts[-1]]

    def process_request(self, query):
        field_dict = self.get_field_dict()
        FormClass = self.get_form(field_dict)

        form = FormClass(request.args)
        query_filters = self.parse_query_filters()
        cleaned = []

        for field, filters in query_filters.items():
            for (filter_key_list, filter_value_list, path, join_path, qf_s, qf_v, label) in filters:
                query = query.switch(self.model)
                for join, model in zip(join_path, path):
                    query = query.ensure_join(join.model, model, join)

                q_objects = []
                for filter_key, filter_value in zip(filter_key_list, filter_value_list):
                    query_filter = self.get_query_filter(field, filter_key)
                    if query_filter is None:
                        continue

                    try:
                        value = query_filter.clean(filter_value)
                    except (TypeError, ValueError):
                        continue

                    q_objects.append(query_filter.query(value))
                    cleaned.append({
                        'label': label,
                        'key': query_filter.key,
                        'value': filter_value,
                        'input_type': query_filter.input_type,
                        'op_field': self.resolve_form_field(form, qf_s),
                        'value_field': self.resolve_form_field(form, qf_v),
                    })

                if q_objects:
                    query = query.where(reduce(operator.or_, q_objects))

        return form, query, cleaned


class DateTimeLocalField(fields.DateTimeLocalField):
    # wtforms' default format list renders with a space separator, which is
    # not a valid value for <input type="datetime-local">.
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('format', ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'])
        super(DateTimeLocalField, self).__init__(*args, **kwargs)


class FilterModelConverter(BaseModelConverter):
    def __init__(self, *args, **kwargs):
        super(FilterModelConverter, self).__init__(*args, **kwargs)
        self.defaults = dict(self.defaults)
        self.defaults[TextField] = fields.StringField
        self.defaults[DateTimeField] = DateTimeLocalField
