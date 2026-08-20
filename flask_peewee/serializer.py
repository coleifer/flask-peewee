import base64
import datetime
import sys
import uuid

from peewee import Model
from flask_peewee.utils import get_dictionary_from_model
from flask_peewee.utils import get_model_from_dictionary


class Serializer(object):
    date_format = '%Y-%m-%d'
    time_format = '%H:%M:%S'
    datetime_format = 'T'.join([date_format, time_format])
    use_iso8601 = True

    def convert_value(self, value):
        if isinstance(value, datetime.datetime):
            if self.use_iso8601:
                return value.isoformat()
            else:
                return value.strftime(self.datetime_format)
        elif isinstance(value, datetime.date):
            return value.strftime(self.date_format)
        elif isinstance(value, datetime.time):
            return value.strftime(self.time_format)
        elif isinstance(value, datetime.timedelta):
            return value.total_seconds()
        elif isinstance(value, Model):
            return value._pk
        elif isinstance(value, uuid.UUID):
            return str(value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            return base64.b64encode(bytes(value)).decode('ascii')
        else:
            return value

    def clean_data(self, data):
        # recurse structurally: dicts and lists are walked element-wise, and any
        # scalar (including a list element) is passed through convert_value. the
        # old code mapped clean_data over list elements and then called .items()
        # on each, which raised on a list of scalars.
        if isinstance(data, dict):
            return {key: self.clean_data(value) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self.clean_data(value) for value in data]
        return self.convert_value(data)

    def serialize_object(self, obj, fields=None, exclude=None):
        data = get_dictionary_from_model(obj, fields, exclude)
        return self.clean_data(data)


class Deserializer(object):
    def deserialize_object(self, model, data):
        return get_model_from_dictionary(model, data)
