import datetime
import uuid

from peewee import Model

from .filters import get_dictionary_from_model
from .filters import get_model_from_dictionary


class Serializer(object):
    date_format = '%Y-%m-%d'
    time_format = '%H:%M:%S'
    datetime_format = ' '.join([date_format, time_format])
    response_format = "json"

    def __init__(self, date_formatter="javascript"):
        self.date_formatter = date_formatter

    def convert_value(self, value):
        if isinstance(value, datetime.datetime):
            if self.date_formatter == "javascript":
                return int(datetime.datetime.timestamp(value) * 1000)
            return value.strftime(self.datetime_format)
        elif isinstance(value, datetime.date):
            return value.strftime(self.date_format)
        elif isinstance(value, datetime.time):
            return value.strftime(self.time_format)
        elif isinstance(value, Model):
            return value._pk
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return value

    def clean_data(self, data):
        if isinstance(data, (list, tuple)):
            return list(map(self.clean_data, data))
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = self.clean_data(value)
            return data
        return self.convert_value(data)

    def serialize_object(self, obj, fields=None, exclude=None):
        data = get_dictionary_from_model(obj, fields, exclude)
        return self.clean_data(data)


class Deserializer(object):
    def deserialize_object(self, model, data):
        return get_model_from_dictionary(model, data)
