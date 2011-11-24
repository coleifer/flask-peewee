import datetime
import sys


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
        else:
            return value
    
    def serialize_object(self, obj, fields=None, exclude=None):
        data = {}
        
        field_list = obj._meta.get_field_names()
        if fields:
            field_list = fields
        if exclude:
            field_list = [f for f in field_list if f not in exclude]
        
        for field_name in field_list:
            data[field_name] = self.convert_value(getattr(obj, field_name))
        
        return data


class ModelSerializer(Serializer):
    def serialize_object(self, obj, fields=None, exclude=None):
        data = super(ModelSerializer, self).serialize_object(obj, fields, exclude)
        
        data['__module__'] = obj.__module__
        data['__model__'] = obj.__class__.__name__
        
        return data


class Deserializer(object):
    def deserialize_object(self, data, instance):
        for field, value in data.iteritems():
            if field in instance._meta.rel_fields:
                field = instance._meta.rel_fields[field]
            
            if field not in instance._meta.fields:
                continue
            
            field_obj = instance._meta.fields[field]
            
            setattr(instance, field, field_obj.python_value(value))
        
        return instance


class ModelDeserializer(Deserializer):
    def __init__(self):
        self._model_cache = {}
    
    def get_model(self, module, model):
        try:
            model_class = self._model_cache[(module, model)]
        except KeyError:
            try:
                __import__(module)
            except ImportError:
                raise ValueError('Unable to import module "%s"' % module)
            
            try:
                model_class = getattr(sys.modules[module], model)
            except AttributeError:
                raise ValueError('Model "%s" not found in module "%s"' % (model, module))
            
            self._model_cache[(module, model)] = model_class
        
        return model_class
    
    def deserialize_object(self, data, instance=None):
        if '__model__' not in data or '__module__' not in data:
            raise ValueError('Unable to deserialize, missing either "__model__" or "__module__" attribute')
        
        module, model = data.pop('__module__'), data.pop('__model__')
        if instance is None:
            instance = self.get_model(module, model)()
        
        return super(ModelDeserializer, self).deserialize_object(data, instance)
