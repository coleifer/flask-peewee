import datetime
import decimal
import uuid

from peewee import Model

from .filters import get_dictionary_from_model
from .filters import get_model_from_dictionary


class Serializer(object):
    date_format = '%Y-%m-%d'
    time_format = '%H:%M:%S'
    datetime_format = ' '.join([date_format, time_format])
    response_format = 'json'
    datetime_formatter = 'python'  # Can be 'python', timestamp, timestamp_ms

    def convert_value(self, value):
        if isinstance(value, datetime.datetime):
            return self.format_datetime(value)
        elif isinstance(value, datetime.date):
            return value.strftime(self.date_format)
        elif isinstance(value, datetime.time):
            return value.strftime(self.time_format)
        elif isinstance(value, Model):
            return value._pk
        elif isinstance(value, uuid.UUID):
            return str(value)
        elif isinstance(value, decimal.Decimal):
            return f"{value:.2f}"
        else:
            return value

    def format_datetime(self, value):
        if self.datetime_formatter == 'timestamp_ms':
            return int(datetime.datetime.timestamp(value) * 1000)
        if self.datetime_formatter == 'timestamp':
            return int(datetime.datetime.timestamp(value))
        return value.strftime(self.datetime_format)

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
