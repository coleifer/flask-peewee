from peewee import BooleanField, ForeignKeyField
from wtforms import fields, form, widgets
from wtfpeewee.orm import ModelConverter, ModelSelectField


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
            # use a different widget here
            search = self.model_admin.foreign_key_lookups[field.name]
            form_field = ModelSelectField(model=field.to, **kwargs)
        else:
            form_field = ModelSelectField(model=field.to, **kwargs)
        return field.name, form_field
