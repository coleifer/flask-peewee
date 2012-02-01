import math
import random
import re
import sys
from hashlib import sha1

from flask import abort, request, render_template
from peewee import Model, DoesNotExist, SelectQuery, ForeignKeyField


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

def get_string_lookups_for_model(model, include_foreign_keys=False, fields=None, exclude=None, accum=None):
    """
    Returns a list of 2-tuples: [
        ('field_a', field_a_obj),
        ('field_b', field_b_obj),
        ('rel__rel_field_a', rel_field_a_obj),
        # ...
    ]
    
    fields & exclude parameters: {
        Model: [f1, f2],
        RelModel: [rf1, ...],
    }
    
    this fails though when there are multiple foreign keys to the same model
    
    perhaps better:
    [f1, f2, {f3: [rf1, rf2]}]
    """
    if isinstance(model, Model):
        model_class = type(model)
    else:
        model_class = model
    
    lookups = []
    models = [model]
    
    accum = accum or []
    
    for field in model._meta.get_fields():
        if isinstance(field, ForeignKeyField):
            rel_model = field.to

            if isinstance(model, Model):
                try:
                    rel_obj = getattr(model, field.name)
                except rel_model.DoesNotExist:
                    rel_obj = None
            else:
                rel_obj = rel_model
            
            if rel_obj and (not fields or rel_model in fields):
                rel_lookups, rel_models = get_string_lookups_for_model(
                    rel_obj,
                    include_foreign_keys,
                    fields,
                    exclude,
                    accum + [field.name],
                )
                lookups.extend(rel_lookups)
                models.extend(rel_models)
        
        if include_foreign_keys or not isinstance(field, ForeignKeyField):
            if (not fields or field.name in fields.get(model_class, ())) and \
               (not exclude or (exclude and field.name not in exclude.get(model_class, ()))):
                lookups.append(
                    ('__'.join(accum + [field.name]), getattr(model, field.name))
                )
    
    return lookups, models

def get_dictionary_lookups_for_model(model, include_foreign_keys=False, fields=None, exclude=None):
    lookups, models = get_string_lookups_for_model(
        model,
        include_foreign_keys,
        fields=fields,
        exclude=exclude,
    )
    return convert_string_lookups_to_dict(lookups), models

def get_models_from_string_lookups(model, lookups):
    """
    Returns a fully-populated model instance from a list of 2-tuples of
    lookup/value: [
        ('field_a', 'value a'),
        ('field_b', 'value_b'),
        ('rel__rel_field_a', 'rel_value_a'),
        # ...
    ]
    """
    field_dict = convert_string_lookups_to_dict(lookups)
    return get_models_from_dictionary(model, field_dict)

def convert_string_lookups_to_dict(lookups):
    field_dict = {}
    split_lookups = [(l.split('__'), v) for l, v in lookups]
    for (lookups, value) in sorted(split_lookups):
        curr = field_dict
        for piece in lookups[:-1]:
            if not isinstance(curr.get(piece, None), dict):
                curr[piece] = {}
            
            curr = curr[piece]
        curr[lookups[-1]] = value
    return field_dict

def get_models_from_dictionary(model, field_dict):
    if isinstance(model, Model):
        model_instance = model
    else:
        model_instance = model()
    models = [model_instance]
    for field_name, value in field_dict.items():
        field_obj = model._meta.fields[field_name]
        if isinstance(value, dict):
            rel_inst, rel_models = get_models_from_dictionary(field_obj.to, value)
            models.extend(rel_models)
            setattr(model_instance, field_name, rel_inst)
        else:
            setattr(model_instance, field_name, field_obj.python_value(value))
    return model_instance, models

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
                accum.append(fk_field.name)
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
