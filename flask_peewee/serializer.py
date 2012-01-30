import datetime
import sys

from peewee import Model
from flask_peewee.utils import get_dictionary_lookups_for_model, get_models_from_dictionary


class Serializer(object):
    date_format = '%Y-%m-%d'
    time_format = '%H:%M:%S'
    datetime_format = ' '.join([date_format, time_format])
    
    def convert_value(self, value):
        if isinstance(value, datetime.datetime):
            return value.strftime(self.datetime_format)
        elif isinstance(value, datetime.date):
            return value.strftime(self.date_format)
        elif isinstance(value, datetime.time):
            return value.strftime(self.time_format)
        elif isinstance(value, Model):
            return value.get_pk()
        else:
            return value
    
    def clean_data(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                self.clean_data(value)
            else:
                data[key] = self.convert_value(value)
        return data
    
    def serialize_object(self, obj, fields=None, exclude=None, include_foreign_keys=False):
        data, models = get_dictionary_lookups_for_model(obj, include_foreign_keys, fields, exclude)
        return self.clean_data(data)


class Deserializer(object):
    def deserialize_object(self, model, data):
        return get_models_from_dictionary(model, data)
