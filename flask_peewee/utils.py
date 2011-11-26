import math
import random
import re
import sys
from hashlib import sha1

from flask import abort, request, render_template
from peewee import Model, DoesNotExist, SelectQuery


def get_object_or_404(query_or_model, **query):
    try:
        return query_or_model.get(**query)
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
        return int(request.args.get(self.page_var) or 1)
    
    def get_pages(self):
        return math.ceil(float(self.query.count()) / self.paginate_by)
    
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

def path_to_models(model, path):
    accum = []
    if '__' in path:
        next, path = path.split('__')
    else:
        next, path = path, ''
    if next in model._meta.rel_fields:
        field_name = model._meta.rel_fields[next]
        model = model._meta.get_field_by_name(field_name).to
        accum.append(model)
    else:
        raise AttributeError('%s has no related field named "%s"' % (model, next))
    if path:
        accum.extend(path_to_models(model, path))
    return accum

def models_to_path(models):
    accum = []
    last = models[0]
    for model in models[1:]:
        fk_field = last._meta.rel_exists(model)
        if fk_field:
            if fk_field in last._meta.get_fields():
                accum.append(fk_field.descriptor)
            else:
                accum.append(fk_field.related_name)
        else:
            raise AttributeError('%s has no relation to %s' % (last, model))
        last = model
    return '__'.join(accum)


# borrowing these methods, slightly modified, from django.contrib.auth
def get_hexdigest(salt, raw_password):
    return sha1(salt + raw_password).hexdigest()

def make_password(raw_password):
    salt = get_hexdigest(str(random.random()), str(random.random()))[:5]
    hsh = get_hexdigest(salt, raw_password)
    return '%s$%s' % (salt, hsh)

def check_password(raw_password, enc_password):
    salt, hsh = enc_password.split('$', 1)
    return hsh == get_hexdigest(salt, raw_password)
