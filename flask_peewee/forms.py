from peewee import BooleanField, ForeignKeyField, TextField

from wtforms import fields
from wtfpeewee.fields import ModelSelectField, ModelHiddenField, BooleanSelectField
from wtfpeewee.orm import ModelConverter


class AdminModelConverter(ModelConverter):
    def __init__(self, model_admin, additional=None):
        super(AdminModelConverter, self).__init__(additional)
        self.model_admin = model_admin

        self.converters[BooleanField] = self.handle_boolean
        self.converters[ForeignKeyField] = self.handle_foreign_key

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
