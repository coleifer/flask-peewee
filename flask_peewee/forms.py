import datetime

from peewee import BooleanField, DateTimeField, ForeignKeyField, TimeField, DateField
from wtforms import fields, form, widgets
from wtforms.fields import FormField, _unset_value
from wtforms.widgets import HTMLString, html_params

from wtfpeewee.fields import ModelSelectField, ModelHiddenField
from wtfpeewee.orm import ModelConverter


class CustomModelConverter(ModelConverter):
    def __init__(self, model_admin, additional=None):
        super(CustomModelConverter, self).__init__(additional)
        self.model_admin = model_admin
        self.converters[BooleanField] = self.handle_boolean

    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)

    def handle_foreign_key(self, model, field, **kwargs):
        if field.null:
            kwargs['allow_blank'] = True

        if field.name in (self.model_admin.foreign_key_lookups or ()):
            form_field = ModelHiddenField(model=field.to, **kwargs)
        else:
            form_field = ModelSelectField(model=field.to, **kwargs)
        return field.name, form_field
