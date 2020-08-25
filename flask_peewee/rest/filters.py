import math
import re
import sys

from flask import abort
from flask import render_template
from flask import request
from peewee import DoesNotExist
from peewee import ForeignKeyField
from peewee import Model
from peewee import SelectQuery


class FieldTreeNode(object):

    def __init__(self, model, fields, children=None):
        self.model = model
        self.fields = fields
        self.children = children or {}


def make_field_tree(model, fields, exclude, force_recursion=False, seen=None):
    no_explicit_fields = fields is None  # assume we want all of them
    if no_explicit_fields:
        fields = model._meta.sorted_field_names
    exclude = exclude or []
    seen = seen or set()

    model_fields = []
    children = {}

    for field_obj in model._meta.sorted_fields:
        if field_obj.name in exclude or field_obj in seen:
            continue

        if field_obj.name in fields:
            model_fields.append(field_obj)

        if isinstance(field_obj, ForeignKeyField):
            seen.add(field_obj)
            if no_explicit_fields:
                rel_fields = None
            else:
                rel_fields = [
                    rf.replace('%s__' % field_obj.name, '')
                    for rf in fields if rf.startswith('%s__' % field_obj.name)
                ]
                if not rel_fields and force_recursion:
                    rel_fields = None

            rel_exclude = [
                rx.replace('%s__' % field_obj.name, '')
                for rx in exclude if rx.startswith('%s__' % field_obj.name)
            ]
            children[field_obj.name] = make_field_tree(
                field_obj.rel_model, rel_fields, rel_exclude, force_recursion, seen)

    return FieldTreeNode(model, model_fields, children)


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
        return int(math.ceil(float(self.query.count()) / self.paginate_by))

    def get_list(self):
        return self.query.paginate(self.get_page(), self.paginate_by)


def get_next():
    if not request.query_string:
        return request.path
    return '%s?%s' % (request.path, request.query_string)


def slugify(s):
    return re.sub(r'[^a-z0-9_\-]+', '-', s.lower())


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
        field_obj = model._meta.fields.get(field_name, None)
        prop = getattr(type(model), field_name, None)
        if isinstance(value, dict) and hasattr(field_obj, "rel_model"):
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
        elif field_obj is not None:
            setattr(model_instance, field_name, field_obj.python_value(value))
        elif isinstance(prop, property) and prop.fset is not None:
            setattr(model_instance, field_name, value)
    return model_instance, models


def path_to_models(model, path):
    accum = []
    if '__' in path:
        next, path = path.split('__')
    else:
        next, path = path, ''
    if next in model._meta.rel:
        field = model._meta.rel[next]
        accum.append(field.rel_model)
    else:
        raise AttributeError('%s has no related field named "%s"' % (model, next))
    if path:
        accum.extend(path_to_models(model, path))
    return accum


class ModelRegistry:

    name = None

    timefield = "created_at"

    def __init__(self, model):
        self.model = model
        self.db = model._meta.database
        self.pk = self.model._meta.primary_key

    def get_fields(self, node, prefix=[]):
        result = [{
            "name": "__".join(prefix + [f.name]),
            "type": f.__class__.__name__
        } for f in node.fields]
        for child_prefix, child in node.children.items():
            result += self.get_fields(child, prefix + [child_prefix])
        return result

    def todict(self):
        field_tree = make_field_tree(self.model, None, None)
        slug = slugify(self.model.__name__)
        return {
            "name": self.name or slug,
            "model": slug,
            "fields": self.get_fields(field_tree),
            "groups": [{
                "name": f.name,
                "type": f.__class__.__name__,
            } for f in self.model._meta.fields.values()]
        }
