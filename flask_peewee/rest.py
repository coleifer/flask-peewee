import functools
import operator
try:
    import simplejson as json
except ImportError:
    import json

from flask import Blueprint
from flask import Response
from flask import abort
from flask import g
from flask import redirect
from flask import request
from flask import session
from flask import url_for
from peewee import *
from peewee import DJANGO_MAP

from flask_peewee.filters import make_field_tree
from flask_peewee.serializer import Deserializer
from flask_peewee.serializer import Serializer
from flask_peewee.utils import PaginatedQuery
from flask_peewee.utils import get_object_or_404
from flask_peewee.utils import slugify
from flask_peewee._compat import reduce


class Authentication(object):
    def __init__(self, protected_methods=None):
        if protected_methods is None:
            protected_methods = ['POST', 'PUT', 'DELETE']

        self.protected_methods = protected_methods

    def authorize(self):
        if request.method in self.protected_methods:
            return False

        return True


class APIKeyAuthentication(Authentication):
    """
    Requires a model that has at least two fields, "key" and "secret", which will
    be searched for when authing a request.
    """
    key_field = 'key'
    secret_field = 'secret'

    def __init__(self, model, protected_methods=None):
        super(APIKeyAuthentication, self).__init__(protected_methods)
        self.model = model
        self._key_field = model._meta.fields[self.key_field]
        self._secret_field = model._meta.fields[self.secret_field]

    def get_query(self):
        return self.model.select()

    def get_key(self, k, s):
        try:
            return self.get_query().where(
                self._key_field==k,
                self._secret_field==s
            ).get()
        except self.model.DoesNotExist:
            pass

    def get_key_secret(self):
        for search in [request.args, request.headers, request.form]:
            if 'key' in search and 'secret' in search:
                return search['key'], search['secret']
        return None, None

    def authorize(self):
        g.api_key = None

        if request.method not in self.protected_methods:
            return True

        key, secret = self.get_key_secret()
        if key or secret:
            g.api_key = self.get_key(key, secret)

        return g.api_key


class UserAuthentication(Authentication):
    def __init__(self, auth, protected_methods=None):
        super(UserAuthentication, self).__init__(protected_methods)
        self.auth = auth

    def authorize(self):
        g.user = None

        if request.method not in self.protected_methods:
            return True

        basic_auth = request.authorization
        if not basic_auth:
            return False

        g.user = self.auth.authenticate(basic_auth.username, basic_auth.password)
        return g.user


class AdminAuthentication(UserAuthentication):
    def verify_user(self, user):
        return user.admin

    def authorize(self):
        res = super(AdminAuthentication, self).authorize()

        if res and g.user:
            return self.verify_user(g.user)
        return res


class RestResource(object):
    paginate_by = 20
    value_transforms = {'False': False, 'false': False,
                        'True': True, 'true': True,
                        'None': None, 'none': None}

    # serializing: dictionary of model -> field names to restrict output
    fields = None
    exclude = None

    # exclude certian fields from being exposed as filters -- for related fields
    # use "__" notation, e.g. user__password
    filter_exclude = None
    filter_fields = None
    filter_recursive = True

    # mapping of field name to resource class
    include_resources = None

    # delete behavior
    delete_recursive = True

    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.pk = model._meta.primary_key

        self.authentication = authentication
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE']

        self._fields = {self.model: self.fields or self.model._meta.sorted_field_names}
        if self.exclude:
            self._exclude = {self.model: self.exclude}
        else:
            self._exclude = {}

        self._filter_fields = self.filter_fields or list(self.model._meta.sorted_field_names)
        self._filter_exclude = self.filter_exclude or []

        self._resources = {}

        # recurse into nested resources
        if self.include_resources:
            for field_name, resource in self.include_resources.items():
                field_obj = self.model._meta.fields[field_name]
                resource_obj = resource(self.api, field_obj.rel_model, self.authentication, self.allowed_methods)
                self._resources[field_name] = resource_obj
                self._fields.update(resource_obj._fields)
                self._exclude.update(resource_obj._exclude)

                self._filter_fields.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_fields])
                self._filter_exclude.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_exclude])

            self._include_foreign_keys = False
        else:
            self._include_foreign_keys = True

        self._field_tree = make_field_tree(self.model, self._filter_fields, self._filter_exclude, self.filter_recursive)

    def authorize(self):
        return self.authentication.authorize()

    def get_api_name(self):
        return slugify(self.model.__name__)

    def get_url_name(self, name):
        return '%s.%s_%s' % (
            self.api.blueprint.name,
            self.get_api_name(),
            name,
        )

    def get_query(self):
        return self.model.select()

    def process_query(self, query):
        raw_filters = {}

        # clean and normalize the request parameters
        for key in request.args:
            orig_key = key
            if key.startswith('-'):
                negated = True
                key = key[1:]
            else:
                negated = False
            if '__' in key:
                expr, op = key.rsplit('__', 1)
                if op not in DJANGO_MAP:
                    expr = key
                    op = 'eq'
            else:
                expr = key
                op = 'eq'
            raw_filters.setdefault(expr, [])
            raw_filters[expr].append((op, request.args.getlist(orig_key), negated))

        # do a breadth first search across the field tree created by filter_fields,
        # searching for matching keys in the request parameters -- when found,
        # filter the query accordingly
        queue = [(self._field_tree, '')]
        while queue:
            node, prefix = queue.pop(0)
            for field in node.fields:
                filter_expr = '%s%s' % (prefix, field.name)
                if filter_expr in raw_filters:
                    for op, arg_list, negated in raw_filters[filter_expr]:
                        clean_args = self.clean_arg_list(arg_list)
                        query = self.apply_filter(query, filter_expr, op, clean_args, negated)

            for child_prefix, child_node in node.children.items():
                queue.append((child_node, prefix + child_prefix + '__'))

        return query

    def clean_arg_list(self, arg_list):
        return [self.value_transforms.get(arg, arg) for arg in arg_list]

    def apply_filter(self, query, expr, op, arg_list, negated):
        query_expr = '%s__%s' % (expr, op)
        constructor = lambda kwargs: negated and ~DQ(**kwargs) or DQ(**kwargs)
        if op == 'in':
            # in gives us a string format list '1,2,3,4'
            # we have to turn it into a list before passing to
            # the filter.
            arg_list = [i.strip() for i in arg_list[0].split(',')]
            return query.filter(constructor({query_expr: arg_list}))
        elif len(arg_list) == 1:
            return query.filter(constructor({query_expr: arg_list[0]}))
        else:
            query_clauses = [
                constructor({query_expr: val}) for val in arg_list]
            return query.filter(reduce(operator.or_, query_clauses))

    def get_serializer(self):
        return Serializer()

    def get_deserializer(self):
        return Deserializer()

    def prepare_data(self, obj, data):
        """
        Hook for modifying outgoing data
        """
        return data

    def serialize_object(self, obj):
        s = self.get_serializer()
        return self.prepare_data(
            obj, s.serialize_object(obj, self._fields, self._exclude)
        )

    def serialize_query(self, query):
        s = self.get_serializer()
        return [
            self.prepare_data(obj, s.serialize_object(obj, self._fields, self._exclude)) \
                for obj in query
        ]

    def deserialize_object(self, data, instance):
        d = self.get_deserializer()
        return d.deserialize_object(instance, data)

    def response_forbidden(self):
        return Response('Forbidden', 403)

    def response_bad_method(self):
        return Response('Unsupported method "%s"' % (request.method), 405)

    def response_bad_request(self):
        return Response('Bad request', 400)

    def response(self, data):
        kwargs = {} if request.is_xhr else {'indent': 2}
        return Response(json.dumps(data, **kwargs), mimetype='application/json')

    def require_method(self, func, methods):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            if request.method not in methods:
                return self.response_bad_method()
            return func(*args, **kwargs)
        return inner

    def get_urls(self):
        return (
            ('/', self.require_method(self.api_list, ['GET', 'POST'])),
            ('/<pk>/', self.require_method(self.api_detail, ['GET', 'POST', 'PUT', 'DELETE'])),
            ('/<pk>/delete/', self.require_method(self.post_delete, ['POST', 'DELETE'])),
        )

    def check_get(self, obj=None):
        return True

    def check_post(self, obj=None):
        return True

    def check_put(self, obj):
        return True

    def check_delete(self, obj):
        return True

    def save_object(self, instance, raw_data):
        instance.save()
        return instance

    def api_list(self):
        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        if request.method == 'GET':
            return self.object_list()
        elif request.method == 'POST':
            return self.create()

    def api_detail(self, pk, method=None):
        obj = get_object_or_404(self.get_query(), self.pk==pk)

        method = method or request.method

        if not getattr(self, 'check_%s' % method.lower())(obj):
            return self.response_forbidden()

        if method == 'GET':
            return self.object_detail(obj)
        elif method in ('PUT', 'POST'):
            return self.edit(obj)
        elif method == 'DELETE':
            return self.delete(obj)

    def post_delete(self, pk):
        return self.api_detail(pk, 'DELETE')

    def apply_ordering(self, query):
        ordering = request.args.get('ordering') or ''
        if ordering:
            desc, column = ordering.startswith('-'), ordering.lstrip('-')
            if column in self.model._meta.fields:
                field = self.model._meta.fields[column]
                query = query.order_by(field.asc() if not desc else field.desc())

        return query

    def get_request_metadata(self, paginated_query):
        var = paginated_query.page_var
        request_arguments = request.args.copy()

        current_page = paginated_query.get_page()
        next = previous = ''

        if current_page > 1:
            request_arguments[var] = current_page - 1
            previous = url_for(self.get_url_name('api_list'), **request_arguments)
        if current_page < paginated_query.get_pages():
            request_arguments[var] = current_page + 1
            next = url_for(self.get_url_name('api_list'), **request_arguments)

        return {
            'model': self.get_api_name(),
            'page': current_page,
            'previous': previous,
            'next': next,
        }

    def get_paginate_by(self):
        try:
            paginate_by = int(request.args.get('limit', self.paginate_by))
        except ValueError:
            paginate_by = self.paginate_by
        else:
            if self.paginate_by:
                paginate_by = min(paginate_by, self.paginate_by) # restrict
        return paginate_by

    def paginated_object_list(self, filtered_query):
        paginate_by = self.get_paginate_by()
        pq = PaginatedQuery(filtered_query, paginate_by)
        meta_data = self.get_request_metadata(pq)

        query_dict = self.serialize_query(pq.get_list())

        return self.response({
            'meta': meta_data,
            'objects': query_dict,
        })

    def object_list(self):
        query = self.get_query()
        query = self.apply_ordering(query)

        # process any filters
        query = self.process_query(query)

        if self.paginate_by or 'limit' in request.args:
            return self.paginated_object_list(query)

        return self.response(self.serialize_query(query))

    def object_detail(self, obj):
        return self.response(self.serialize_object(obj))

    def save_related_objects(self, instance, data):
        for k, v in data.items():
            if k in self._resources and isinstance(v, dict):
                rel_resource = self._resources[k]
                rel_obj, rel_models = rel_resource.deserialize_object(v, getattr(instance, k))
                rel_resource.save_related_objects(rel_obj, v)
                setattr(instance, k, rel_resource.save_object(rel_obj, v))

    def read_request_data(self):
        if request.data:
            return json.loads(request.data.decode('utf-8'))
        elif request.form.get('data'):
            return json.loads(request.form['data'])
        else:
            return dict(request.form)

    def create(self):
        try:
            data = self.read_request_data()
        except ValueError:
            return self.response_bad_request()

        obj, models = self.deserialize_object(data, self.model())

        self.save_related_objects(obj, data)
        obj = self.save_object(obj, data)

        return self.response(self.serialize_object(obj))

    def edit(self, obj):
        try:
            data = self.read_request_data()
        except ValueError:
            return self.response_bad_request()

        obj, models = self.deserialize_object(data, obj)

        self.save_related_objects(obj, data)
        obj = self.save_object(obj, data)

        return self.response(self.serialize_object(obj))

    def delete(self, obj):
        res = obj.delete_instance(recursive=self.delete_recursive)
        return self.response({'deleted': res})


class RestrictOwnerResource(RestResource):
    # restrict PUT/DELETE to owner of an object, likewise apply owner to any
    # incoming POSTs
    owner_field = 'user'

    def validate_owner(self, user, obj):
        return user == getattr(obj, self.owner_field)

    def set_owner(self, obj, user):
        setattr(obj, self.owner_field, user)

    def check_put(self, obj):
        return self.validate_owner(g.user, obj)

    def check_delete(self, obj):
        return self.validate_owner(g.user, obj)

    def save_object(self, instance, raw_data):
        self.set_owner(instance, g.user)
        return super(RestrictOwnerResource, self).save_object(instance, raw_data)


class RestAPI(object):
    def __init__(self, app, prefix='/api', default_auth=None, name='api'):
        self.app = app

        self._registry = {}

        self.url_prefix = prefix
        self.blueprint = self.get_blueprint(name)

        self.default_auth = default_auth or Authentication()

    def register(self, model, provider=RestResource, auth=None, allowed_methods=None):
        self._registry[model] = provider(self, model, auth or self.default_auth, allowed_methods)

    def unregister(self, model):
        del(self._registry[model])

    def is_registered(self, model):
        return self._registry.get(model)

    def response_auth_failed(self):
        return Response('Authentication failed', 401, {
            'WWW-Authenticate': 'Basic realm="Login Required"'
        })

    def auth_wrapper(self, func, provider):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            if not provider.authorize():
                return self.response_auth_failed()
            return func(*args, **kwargs)
        return inner

    def get_blueprint(self, blueprint_name):
        return Blueprint(blueprint_name, __name__)

    def get_urls(self):
        return ()

    def configure_routes(self):
        for url, callback in self.get_urls():
            self.blueprint.route(url)(callback)

        for provider in self._registry.values():
            api_name = provider.get_api_name()
            for url, callback in provider.get_urls():
                full_url = '/%s%s' % (api_name, url)
                self.blueprint.add_url_rule(
                    full_url,
                    '%s_%s' % (api_name, callback.__name__),
                    self.auth_wrapper(callback, provider),
                    methods=provider.allowed_methods,
                )

    def register_blueprint(self, **kwargs):
        self.app.register_blueprint(self.blueprint, url_prefix=self.url_prefix, **kwargs)

    def setup(self):
        self.configure_routes()
        self.register_blueprint()
