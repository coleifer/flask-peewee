from peewee import BooleanField

from wtfpeewee.fields import BooleanSelectField
from wtfpeewee.orm import ModelConverter


class BaseModelConverter(ModelConverter):
    def __init__(self, *args, **kwargs):
        super(BaseModelConverter, self).__init__(*args, **kwargs)
        self.converters[BooleanField] = self.handle_boolean

    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)
