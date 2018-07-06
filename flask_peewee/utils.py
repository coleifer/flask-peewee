import math
import random
import re
import sys
from hashlib import sha1

from flask import abort
from flask import render_template
from flask import request
from peewee import DoesNotExist
from peewee import ForeignKeyField
from peewee import Model
from peewee import SelectQuery

from flask_peewee._compat import text_type


def get_object_or_404(query_or_model, *query):
    if not isinstance(query_or_model, SelectQuery):
        query_or_model = query_or_model.select()
    try:
        return query_or_model.where(*query).get()
    except DoesNotExist:
        abort(404)

def object_list(template_name, qr, var_name='object_list', **kwargs):
    pq = PaginatedQuery(qr, kwargs.pop('paginate_by', 20))
    kwargs[var_name] = pq.get_list()
    return render_template(template_name, pagination=pq, page=pq.get_page(), **kwargs)


class PaginatedQuery(object):
    page_var = 'page'

    def __init__(self, query_or_model, paginate_by):
        self.paginate_by = paginate_by

        if isinstance(query_or_model, SelectQuery):
            self.query = query_or_model
            self.model = self.query.model
        else:
            self.model = query_or_model
            self.query = self.model.select()

    def get_page(self):
        curr_page = request.args.get(self.page_var)
        if curr_page and curr_page.isdigit():
            return int(curr_page)
        return 1

    def get_pages(self):
        if not hasattr(self, '_get_pages'):
            self._get_pages = int(math.ceil(
                float(self.query.count()) / self.paginate_by))
        return self._get_pages

    def get_list(self):
        return self.query.paginate(self.get_page(), self.paginate_by)


def get_next():
    if not request.query_string:
        return request.path
    return '%s?%s' % (request.path, request.query_string)

def slugify(s):
    return re.sub('[^a-z0-9_\-]+', '-', s.lower())

def load_class(s):
    path, klass = s.rsplit('.', 1)
    __import__(path)
    mod = sys.modules[path]
    return getattr(mod, klass)

def get_dictionary_from_model(model, fields=None, exclude=None):
    model_class = type(model)
    data = {}

    fields = fields or {}
    exclude = exclude or {}
    curr_exclude = exclude.get(model_class, [])
    curr_fields = fields.get(model_class, model._meta.sorted_field_names)

    for field_name in curr_fields:
        if field_name in curr_exclude:
            continue
        field_obj = model_class._meta.fields[field_name]
        field_data = model.__data__.get(field_name)
        if isinstance(field_obj, ForeignKeyField) and field_data and field_obj.rel_model in fields:
            rel_obj = getattr(model, field_name)
            data[field_name] = get_dictionary_from_model(rel_obj, fields, exclude)
        else:
            data[field_name] = field_data
    return data

def get_model_from_dictionary(model, field_dict):
    if isinstance(model, Model):
        model_instance = model
        check_fks = True
    else:
        model_instance = model()
        check_fks = False
    models = [model_instance]
    for field_name, value in field_dict.items():
        field_obj = model._meta.fields[field_name]
        if isinstance(value, dict):
            rel_obj = field_obj.rel_model
            if check_fks:
                try:
                    rel_obj = getattr(model, field_name)
                except field_obj.rel_model.DoesNotExist:
                    pass
                if rel_obj is None:
                    rel_obj = field_obj.rel_model
            rel_inst, rel_models = get_model_from_dictionary(rel_obj, value)
            models.extend(rel_models)
            setattr(model_instance, field_name, rel_inst)
        else:
            setattr(model_instance, field_name, field_obj.python_value(value))
    return model_instance, models

def path_to_models(model, path):
    accum = []
    if '__' in path:
        attr, path = path.split('__', 1)
    else:
        attr, path = path, ''
    if attr in model._meta.fields:
        field = model._meta.fields[attr]
        accum.append(field.rel_model)
    else:
        raise AttributeError('%s has no related field named "%s"' % (model, attr))
    if path:
        accum.extend(path_to_models(model, path))
    return accum


# borrowing these methods, slightly modified, from django.contrib.auth
def get_hexdigest(salt, raw_password):
    data = salt + raw_password
    return sha1(data.encode('utf8')).hexdigest()

def make_password(raw_password):
    salt = get_hexdigest(text_type(random.random()), text_type(random.random()))[:5]
    hsh = get_hexdigest(salt, raw_password)
    return '%s$%s' % (salt, hsh)

def check_password(raw_password, enc_password):
    salt, hsh = enc_password.split('$', 1)
    return hsh == get_hexdigest(salt, raw_password)
