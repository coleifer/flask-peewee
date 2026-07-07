import functools
import json
import operator

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
from flask_peewee.utils import convert_boolean
from flask_peewee.utils import get_object_or_404
from flask_peewee.utils import slugify
from functools import reduce


# every HTTP method the REST API handles. Pass as protected_methods to require
# authentication on reads as well as writes, e.g.
# BearerAuthentication(Token, ALL_METHODS).
ALL_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class RestForbidden(Exception):
    # raised when a nested write fails the child resource's check_*; caught in
    # create/edit and turned into a 403 (and rolls back the enclosing atomic).
    pass


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


class BearerAuthentication(Authentication):
    """
    Token auth via the ``Authorization: Bearer <token>`` header. Requires a
    model with a token field (default "token"), which is looked up to authorize
    the request. Unlike APIKeyAuthentication the credential rides in a header
    rather than the query-string, so it does not leak into access logs. Store
    high-entropy tokens; to keep them hashed at rest, override get_key.
    """
    token_field = 'token'

    def __init__(self, model, protected_methods=None):
        super(BearerAuthentication, self).__init__(protected_methods)
        self.model = model
        self._token_field = model._meta.fields[self.token_field]

    def get_query(self):
        return self.model.select()

    def get_token(self):
        scheme, _, token = request.headers.get(
            'Authorization', '').partition(' ')
        if scheme.lower() == 'bearer' and token.strip():
            return token.strip()

    def get_key(self, token):
        try:
            return self.get_query().where(self._token_field == token).get()
        except self.model.DoesNotExist:
            pass

    def authorize(self):
        g.api_key = None

        if request.method not in self.protected_methods:
            return True

        token = self.get_token()
        if token:
            g.api_key = self.get_key(token)

        return g.api_key


class UserBearerAuthentication(BearerAuthentication):
    """
    Bearer-token auth that resolves the token to a *user* and sets g.user, so
    it drives RestrictOwnerResource and the rest of the user-auth stack. The
    token model has a foreign key to the user (default "user"); set
    user_field=None if the token lives directly on the user model.
    """
    user_field = 'user'

    def authorize(self):
        g.user = None

        if request.method not in self.protected_methods:
            return True

        token = self.get_token()
        if token:
            key = self.get_key(token)
            if key is not None:
                g.user = key if self.user_field is None \
                    else getattr(key, self.user_field)

        return g.user


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
    # default page size when the client does not request a "limit".
    paginate_by = 20
    # upper bound on a client-requested "limit"; None means no ceiling. This
    # lets clients ask for pages larger than paginate_by (up to the cap) --
    # paginate_by alone is only the default, never a maximum.
    max_paginate_by = None
    value_transforms = {'False': False, 'false': False,
                        'True': True, 'true': True,
                        'None': None, 'none': None}

    # serializing: dictionary of model -> field names to restrict output
    fields = None
    exclude = None

    # field names that clients may never write, even when they appear in an
    # incoming POST/PUT body -- protects against mass assignment.
    readonly_fields = None

    # exclude certian fields from being exposed as filters -- for related fields
    # use "__" notation, e.g. user__password
    filter_exclude = None
    filter_fields = None
    filter_recursive = True

    # mapping of field name to resource class
    include_resources = None

    # whether related objects may be created/updated through a nested {...} in
    # this resource's payload. When False, a nested object is ignored (the FK
    # can still be set by scalar id).
    nested_writes = True

    # delete behavior
    delete_recursive = True

    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.pk = model._meta.primary_key

        self.authentication = authentication
        self.allowed_methods = allowed_methods or list(ALL_METHODS)

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
            if key in ('ordering', 'page', 'limit'):
                continue

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

        if not raw_filters:
            return query

        # do a breadth first search across the field tree created by filter_fields,
        # searching for matching keys in the request parameters -- when found,
        # filter the query accordingly
        queue = [(self._field_tree, '')]
        while queue:
            node, prefix = queue.pop(0)
            for field in node.fields:
                filter_expr = '%s%s' % (prefix, field.name)

                if filter_expr in raw_filters:
                    for op, arg_list, negated in raw_filters.pop(filter_expr):
                        clean_args = self.clean_arg_list(arg_list)
                        query = self.apply_filter(query, field, filter_expr, op, clean_args, negated)

            for child_prefix, child_node in node.children.items():
                queue.append((child_node, prefix + child_prefix + '__'))

        return query

    def clean_arg_list(self, arg_list):
        return [self.value_transforms.get(arg, arg) for arg in arg_list]

    def apply_filter(self, query, field, expr, op, arg_list, negated):
        query_expr = '%s__%s' % (expr, op)
        constructor = lambda kwargs: ~DQ(**kwargs) if negated else DQ(**kwargs)
        if isinstance(field, BooleanField):
            arg_list = [convert_boolean(arg) for arg in arg_list]

        if op == 'in':
            # `in` values may be given comma-separated and/or as repeated
            # params, e.g. ?id__in=1,2&id__in=3 -> [1, 2, 3].
            values = []
            for arg in arg_list:
                values.extend(v.strip() for v in str(arg).split(','))
            return query.filter(constructor({query_expr: values}))
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

    def get_readonly_fields(self):
        # the primary key is always read-only: it is addressed via the URL,
        # never rewritten from the request body.
        readonly = set(self.readonly_fields or ())
        readonly.add(self.pk.name)
        return readonly

    def scrub_readonly_fields(self, data):
        # Strip read-only fields at *every* level of a (possibly nested)
        # payload. A top-level-only strip is not enough: the deserializer
        # recurses into nested foreign-key dicts and would write read-only
        # fields (e.g. "admin") straight onto the related instance, defeating
        # the guard and allowing privilege escalation via a nested write.
        # Recurse through the declared child resources so each applies its own
        # read-only policy.
        if not isinstance(data, dict):
            return data
        readonly = self.get_readonly_fields()
        cleaned = {}
        for key, value in data.items():
            if key in readonly:
                continue
            if key in self._resources and isinstance(value, dict):
                if not self.nested_writes:
                    # nested writes disabled: ignore the nested object.
                    continue
                value = self._resources[key].scrub_readonly_fields(value)
            cleaned[key] = value
        return cleaned

    def deserialize_object(self, data, instance):
        data = self.scrub_readonly_fields(data)
        d = self.get_deserializer()
        return d.deserialize_object(instance, data)

    def response_error(self, message, status):
        return Response(json.dumps({'error': message}), status=status,
                        mimetype='application/json')

    def response_forbidden(self):
        return self.response_error('Forbidden', 403)

    def response_bad_method(self):
        return self.response_error('Unsupported method "%s"' % request.method, 405)

    def response_bad_request(self, message='Bad request'):
        return self.response_error(message, 400)

    def response(self, data):
        return Response(json.dumps(data), mimetype='application/json')

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
        # to_dict(flat=False) keeps repeated params (e.g. ?user=1&user=2) so
        # they survive into the next/previous links.
        request_arguments = request.args.to_dict(flat=False)

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
            'page_count': paginated_query.get_pages(),
            'object_count': paginated_query.get_count(),
            'previous': previous,
            'next': next,
        }

    def get_paginate_by(self):
        # an explicit "limit" wins (capped at max_paginate_by if set),
        # otherwise fall back to the resource default. paginate_by is the
        # default page size, not a maximum -- clients may request more.
        if 'limit' in request.args:
            try:
                limit = int(request.args['limit'])
            except (TypeError, ValueError):
                limit = 0
            if limit > 0:
                if self.max_paginate_by:
                    return min(limit, self.max_paginate_by)
                return limit
        return self.paginate_by

    def paginated_object_list(self, filtered_query):
        paginate_by = self.get_paginate_by()
        if not paginate_by:
            # pagination disabled and no limit requested: put everything on a
            # single page so the response still uses the {meta, objects}
            # envelope rather than a bare list.
            paginate_by = filtered_query.count() or 1
        pq = PaginatedQuery(filtered_query, paginate_by)
        meta_data = self.get_request_metadata(pq)

        query_dict = self.serialize_query(pq.get_list())

        return self.response({
            'meta': meta_data,
            'objects': query_dict,
        })

    def apply_related_joins(self, query):
        # Eager-load the include_resources tree in a single query so nested
        # serialization does not issue a lookup per row (the N+1 you would get
        # from lazily following each foreign key). Each related model is LEFT
        # OUTER joined -- nullable FKs stay None -- and aliased, so the same
        # model may be nested more than once (e.g. from_user / to_user).
        return self._join_related(query, self.model, self)

    def _join_related(self, query, src, resource):
        for field_name, child in resource._resources.items():
            dest = child.model.alias()
            fk = getattr(src, field_name)
            pk = getattr(dest, child.model._meta.primary_key.name)
            query = query.select_extend(dest).join_from(
                src, dest, JOIN.LEFT_OUTER, on=(fk == pk), attr=field_name)
            query = self._join_related(query, dest, child)
        return query

    def object_list(self):
        query = self.get_query()
        query = self.apply_ordering(query)

        # process any filters
        query = self.process_query(query)

        # eager-load nested relations (avoids N+1 during serialization). This
        # runs after process_query so it composes with the DQ-based filter
        # joins -- the related models are aliased, so they never collide.
        query = self.apply_related_joins(query)

        # always return the paginated envelope so the response shape is
        # consistent regardless of the resource's paginate_by setting.
        return self.paginated_object_list(query)

    def object_detail(self, obj):
        return self.response(self.serialize_object(obj))

    def save_related_objects(self, instance, data):
        if not self.nested_writes:
            return
        for k, v in data.items():
            if k in self._resources and isinstance(v, dict):
                rel_resource = self._resources[k]
                existing = getattr(instance, k)
                rel_obj, rel_models = rel_resource.deserialize_object(v, existing)
                # a nested write must satisfy the child resource's own
                # per-object authorization, exactly as a direct write to that
                # resource would -- editing an existing related row runs
                # check_put, creating a new one runs check_post.
                if existing is not None and existing.get_id() is not None:
                    allowed = rel_resource.check_put(rel_obj)
                else:
                    allowed = rel_resource.check_post(rel_obj)
                if not allowed:
                    raise RestForbidden()
                rel_resource.save_related_objects(rel_obj, v)
                setattr(instance, k, rel_resource.save_object(rel_obj, v))

    def read_request_data(self):
        if request.data:
            return json.loads(request.data.decode('utf-8'))
        elif request.form.get('data'):
            return json.loads(request.form['data'])
        else:
            return dict(request.form)

    def persist_object(self, instance, data):
        # deserialize + save, translating validation/integrity problems into a
        # 400 (see create/edit) rather than letting them surface as a 500.
        # Wrapped in a transaction so a rejected nested write (RestForbidden)
        # or an integrity error cannot leave a half-written object graph.
        with self.model._meta.database.atomic():
            obj, models = self.deserialize_object(data, instance)
            self.save_related_objects(obj, data)
            return self.save_object(obj, data)

    def create(self):
        try:
            data = self.read_request_data()
        except ValueError:
            return self.response_bad_request('Request body is not valid JSON.')

        try:
            obj = self.persist_object(self.model(), data)
        except RestForbidden:
            return self.response_forbidden()
        except (IntegrityError, DataError, ValueError, TypeError) as exc:
            return self.response_bad_request(str(exc))

        return self.response(self.serialize_object(obj))

    def edit(self, obj):
        try:
            data = self.read_request_data()
        except ValueError:
            return self.response_bad_request('Request body is not valid JSON.')

        try:
            obj = self.persist_object(obj, data)
        except RestForbidden:
            return self.response_forbidden()
        except (IntegrityError, DataError, ValueError, TypeError) as exc:
            return self.response_bad_request(str(exc))

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
