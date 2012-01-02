import functools
try:
    import simplejson as json
except ImportError:
    import json

from flask import Blueprint, abort, request, Response, session, redirect, url_for, g
from peewee import *

from flask_peewee.filters import QueryFilter
from flask_peewee.serializer import Serializer, Deserializer
from flask_peewee.utils import PaginatedQuery, slugify, get_object_or_404


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
    be searched for when authing a request
    """
    def __init__(self, model, protected_methods=None):
        super(APIKeyAuthentication, self).__init__(protected_methods)
        self.model = model
    
    def get_query(self):
        return self.model.select()
    
    def get_key(self, k, s):
        try:
            return self.get_query().get(key=k, secret=s)
        except self.model.DoesNotExist:
            pass
    
    def authorize(self):
        g.api_key = None
        
        if request.method not in self.protected_methods:
            return True

        if 'key' in request.args and 'secret' in request.args:
            g.api_key = self.get_key(request.args['key'], request.args['secret'])
        
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
    fields = None
    exclude = None
    
    # filtering
    ignore_filters = ('ordering', 'page', 'limit', 'key', 'secret',)
    exclude_filter_fields = None
    related_filters = []
    
    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.authentication = authentication
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE']
    
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
    
    def get_query_filter(self, query):
        return QueryFilter(query, self.exclude_filter_fields, self.ignore_filters, self.related_filters)
    
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
            obj, s.serialize_object(obj, self.fields, self.exclude)
        )
    
    def serialize_query(self, query):
        s = self.get_serializer()
        return [
            self.prepare_data(obj, s.serialize_object(obj, self.fields, self.exclude)) \
                for obj in query
        ]
    
    def deserialize_object(self, data, instance):
        return self.get_deserializer().deserialize_object(data, instance)
    
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
    
    def api_detail(self, pk):
        obj = get_object_or_404(self.get_query(), **{
            self.model._meta.pk_name: pk
        })
        
        if not getattr(self, 'check_%s' % request.method.lower())(obj):
            return self.response_forbidden()
        
        if request.method == 'GET':
            return self.object_detail(obj)
        elif request.method in ('PUT', 'POST'):
            return self.edit(obj)
        elif request.method == 'DELETE':
            return self.delete(obj)
    
    def apply_ordering(self, query):
        ordering = request.args.get('ordering') or ''
        if ordering:
            desc, column = ordering.startswith('-'), ordering.lstrip('-')
            if column in self.model._meta.fields:
                query = query.order_by((column, desc and 'desc' or 'asc'))
        
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
    
    def apply_filters(self, query):
        filters = []
        for key in request.args:
            if key in self.ignore_filters:
                continue
            
            values = request.args.getlist(key)
            if len(values) == 1:
                filters.append((key, values[0]))
            else:
                filters.append(('%s__in' % key, values))
        
        if filters:
            query = query.filter(**dict(filters))
        
        return query
    
    def object_list(self):
        query = self.get_query()
        query = self.apply_ordering(query)
        
        # create a QueryFilter object with our current query
        query_filter = self.get_query_filter(query)
        
        # process the filters from the request
        filtered_query = query_filter.get_filtered_query()
        
        try:
            paginate_by = int(request.args.get('limit', self.paginate_by))
        except ValueError:
            paginate_by = self.paginate_by
        else:
            paginate_by = min(paginate_by, self.paginate_by) # restrict
        
        pq = PaginatedQuery(filtered_query, paginate_by)
        meta_data = self.get_request_metadata(pq)
        
        query_dict = self.serialize_query(pq.get_list())
        
        return self.response({
            'meta': meta_data,
            'objects': query_dict,
        })
    
    def object_detail(self, obj):
        return self.response(self.serialize_object(obj))
    
    def create(self):
        data = request.data or request.form.get('data') or ''
        
        try:
            data = json.loads(data)
        except ValueError:
            return self.response_bad_request()
        
        instance = self.deserialize_object(data, self.model())
        instance = self.save_object(instance, data)
        
        return self.response(self.serialize_object(instance))
    
    def edit(self, obj):
        try:
            data = json.loads(request.data)
        except ValueError:
            return self.response_bad_request()
        
        obj = self.deserialize_object(data, obj)
        obj = self.save_object(obj, data)
        
        return self.response(self.serialize_object(obj))
    
    def delete(self, obj):
        res = self.model.delete().where(**{
            self.model._meta.pk_name: obj.get_pk()
        }).execute()
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
