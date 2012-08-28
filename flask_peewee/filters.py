import datetime
import operator

from flask import request
from peewee import *
from wtforms import fields, form


class QueryFilter(object):
    """
    Basic class representing a named field (with or without a list of options)
    and an operation against a given value
    """
    def __init__(self, field, name, options=None):
        self.field = field
        self.name = name
        self.options = options

    def apply(self, query, value):
        raise NotImplementedError

    def operation(self):
        raise NotImplementedError

    def get_options(self):
        return self.options


class EqualQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field == value)

    def operation(self):
        return 'equal to'


class NotEqualQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field != value)

    def operation(self):
        return 'not equal to'


class LessThanQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field < value)

    def operation(self):
        return 'less than'


class LessThanEqualToQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field <= value)

    def operation(self):
        return 'less than or equal to'


class GreaterThanQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field > value)

    def operation(self):
        return 'greater than'


class GreaterThanEqualToQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field >= value)

    def operation(self):
        return 'greater than or equal to'


class StartsWithQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field ^ value)

    def operation(self):
        return 'starts with'


class ContainsQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field ** value)

    def operation(self):
        return 'contains'


class InQueryFilter(QueryFilter):
    def apply(self, query, value):
        return query.where(self.field << value)

    def operation(self):
        return 'is one of'


class FilterMapping(object):
    """
    Map a peewee field to a list of valid query filters for that field
    """
    string = (EqualQueryFilter, NotEqualQueryFilter, StartsWithQueryFilter, ContainsQueryFilter)
    numeric = (EqualQueryFilter, NotEqualQueryFilter, LessThanQueryFilter, GreaterThanQueryFilter,
        LessThanEqualToQueryFilter, GreaterThanEqualToQueryFilter)
    foreign_key = (EqualQueryFilter, NotEqualQueryFilter, InQueryFilter)
    boolean = (EqualQueryFilter, NotEqualQueryFilter)

    def get_field_types(self):
        return {
            CharField: 'string',
            TextField: 'string',
            DateTimeField: 'numeric',
            DateField: 'numeric',
            TimeField: 'numeric',
            IntegerField: 'numeric',
            BigIntegerField: 'numeric',
            FloatField: 'numeric',
            DoubleField: 'numeric',
            DecimalField: 'numeric',
            BooleanField: 'boolean',
            PrimaryKeyField: 'numeric',
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

    def convert_boolean(self, field):
        boolean_choices = [('True', '1', 'False', '')]
        return [f(field, field.verbose_name, boolean_choices) for f in self.boolean]

    def convert_foreign_key(self, field):
        return [f(field, field.verbose_name, field.choices) for f in self.foreign_key]


class FilterForm(object):
    base_class = form.Form

    def __init__(self, model, model_converter, filter_mapping, fields=None, exclude=None):
        self.model = model
        self.model_converter = model_converter
        self.filter_mapping = filter_mapping

        if fields:
            self._fields = [model._meta.fields[f] for f in fields]
        else:
            self._fields = model._meta.get_fields()

        if exclude:
            self._fields = [f for f in self._fields if f.name not in exclude]

        self._query_filters = self.load_query_filters()

    def load_query_filters(self):
        query_filters = {}

        for field in self._fields:
            query_filters[field] = self.filter_mapping.convert(field)

        return query_filters

    def get_operation_field(self, field):
        # return a select for choosing an operation on the field
        choices = []
        for i, query_filter in enumerate(self._query_filters[field]):
            choices.append(('filter_%s_%s' % (field.name, i), query_filter.operation()))

        return fields.SelectField(choices=choices)

    def get_value_field(self, field):
        field_name, field = self.model_converter.convert(self.model, field, None)
        return field

    def get_field_dict(self):
        field_dict = {}

        for field in self._fields:
            op_field = self.get_operation_field(field)
            val_field = self.get_value_field(field)
            field_dict['filter_op_%s' % (field.name)] = op_field
            field_dict['filter_val_%s' % (field.name)] = val_field

        return field_dict

    def get_form(self):
        return type(
            self.model.__name__ + 'FilterForm',
            (self.base_class, ),
            self.get_field_dict(),
        )

    def process_request(self, query):
        field_dict = self.get_field_dict()

        FormClass = self.get_form()
        form = FormClass(request.args)
        if form.validate():
            pass

        return form, query
