import datetime
import functools
import hashlib
import json
import operator
import secrets

from flask import Blueprint
from flask import Response
from flask import g
from flask import request
from flask import url_for
from peewee import *
from peewee import DJANGO_MAP

from flask_peewee.filters import make_field_tree
from flask_peewee.serializer import Deserializer
from flask_peewee.serializer import Serializer
from flask_peewee.utils import PaginatedQuery
from flask_peewee.utils import alias_field
from flask_peewee.utils import convert_boolean
from flask_peewee.utils import order_query
from flask_peewee.utils import slugify
from functools import reduce


# every HTTP method the REST API handles. Pass as protected_methods to require
# authentication on reads as well as writes, e.g.
# BearerAuthentication(Token, ALL_METHODS).
ALL_METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')

# errors raised while persisting a write, reported to the client as a 400.
PERSIST_ERRORS = (IntegrityError, DataError, ValueError, TypeError)


class RestForbidden(Exception):
    # raised when a nested write fails the child resource's check_*. caught in
    # create/edit and turned into a 403 (and rolls back the enclosing atomic).
    pass


class Authentication(object):
    def __init__(self, protected_methods=None):
        if protected_methods is None:
            protected_methods = ['POST', 'PUT', 'PATCH', 'DELETE']

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
    Token auth via the ``Authorization: Bearer <token>`` header (requires a
    model with a token field, default "token").
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
    Bearer-token auth that resolves the token to a *user* and sets g.user.
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


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class HashedBearerAuthentication(BearerAuthentication):
    """
    Bearer auth for tokens stored hashed at rest, as created by
    make_token_model(). The presented token is hashed with sha256 and looked
    up in the token_hash column, skipping revoked and expired rows. The
    matching row is stored on g.api_key, and g.user is set to the row's user
    when the model has a user foreign key.
    """
    token_field = 'token_hash'
    user_field = 'user'

    def get_query(self):
        model = self.model
        return model.select().where(
            model.revoked == False,
            model.expires.is_null() | (model.expires > datetime.datetime.now()))

    def get_key(self, token):
        return super(HashedBearerAuthentication, self).get_key(
            _hash_token(token))

    def authorize(self):
        g.user = None
        res = super(HashedBearerAuthentication, self).authorize()
        if g.api_key is not None and self.user_field in self.model._meta.fields:
            g.user = getattr(g.api_key, self.user_field)
        return res


def make_token_model(db, user_model=None, db_table='api_token'):
    """
    Create an ApiToken model bound to the given Database wrapper, for use
    with HashedBearerAuthentication. When user_model is given the tokens
    carry a foreign key to it. create_token() returns the new row and the
    raw token, of which only the sha256 hash is stored.
    """
    class ApiToken(db.Model):
        token_hash = CharField(unique=True)
        created = DateTimeField(default=datetime.datetime.now)
        expires = DateTimeField(null=True)
        revoked = BooleanField(default=False)

        class Meta:
            table_name = db_table

        @classmethod
        def create_token(cls, **kwargs):
            token = secrets.token_urlsafe(32)
            return cls.create(token_hash=_hash_token(token), **kwargs), token

    if user_model is not None:
        ApiToken._meta.add_field('user', ForeignKeyField(user_model))

    return ApiToken


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
    # upper bound on a client-requested "limit". None means no ceiling. This
    # lets clients ask for pages larger than paginate_by (up to the cap) --
    # paginate_by alone is only the default, never a maximum.
    max_paginate_by = None
    value_transforms = {'False': False, 'false': False,
                        'True': True, 'true': True,
                        'None': None, 'none': None}

    # ops whose predicate excludes values instead of matching them. repeated
    # values of an exclusion combine with AND, not OR (see apply_filter).
    NEGATIVE_OPS = frozenset({'ne', 'is_not', 'not_in'})

    # serializing: dictionary of model -> field names to restrict output
    fields = None
    exclude = None

    # field names that clients may never write, even when they appear in an
    # incoming POST/PUT/PATCH body -- protects against mass assignment.
    readonly_fields = None

    # when True, a write payload containing unrecognized keys is rejected with
    # a 400 listing them.
    reject_unknown_fields = False

    # when True, a query-string filter that matches no filterable field returns
    # a 400.
    reject_unknown_filters = False

    # exclude certian fields from being exposed as filters, for related fields
    # use "__", e.g. user__password
    filter_exclude = None
    filter_fields = None

    # when True, a foreign key in filter_fields makes every column of the
    # related model filterable. Off by default, since a filter reveals a
    # column's value even when the column is not serialized. List related
    # columns explicitly (user__username) instead.
    filter_recursive = False

    # max related-model hops when building the filter field tree, so a long or
    # densely linked fk graph cannot explode it.
    max_filter_depth = 3

    # mapping of field name to resource class
    include_resources = None

    # whether related objects may be created/updated through a nested {...} in
    # this resource's payload. When False, a nested object is ignored (the FK
    # can still be set by scalar id).
    nested_writes = True

    # when True, POST also accepts a JSON list of up to max_bulk objects,
    # created in one transaction.
    allow_bulk = False
    max_bulk = 100

    # delete behavior
    delete_recursive = True

    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.pk = model._meta.primary_key

        self.authentication = authentication
        self.allowed_methods = allowed_methods or list(ALL_METHODS)

        # field maps are keyed by path (see get_dictionary_from_model): the
        # root is (), and each nested resource is grafted in under its field
        # name below.
        self._fields = {(): self.fields or self.model._meta.sorted_field_names}
        if self.exclude:
            self._exclude = {(): self.exclude}
        else:
            self._exclude = {}

        self._filter_fields = list(self.filter_fields or self.model._meta.sorted_field_names)
        self._filter_exclude = list(self.filter_exclude or [])

        self._resources = {}

        # recurse into nested resources
        if self.include_resources:
            for field_name, resource in self.include_resources.items():
                field_obj = self.model._meta.fields[field_name]
                resource_obj = resource(self.api, field_obj.rel_model, self.authentication, self.allowed_methods)
                self._resources[field_name] = resource_obj
                # graft the child's path-keyed maps in under this field name,
                # so its root () becomes (field_name,) here.
                self._fields.update({(field_name,) + p: v
                                     for p, v in resource_obj._fields.items()})
                self._exclude.update({(field_name,) + p: v
                                      for p, v in resource_obj._exclude.items()})

                # a nested resource without filter_fields adds no filters. Its
                # default is every column of its model.
                if resource_obj.filter_fields:
                    self._filter_fields.extend(['%s__%s' % (field_name, ff)
                                                for ff in resource_obj._filter_fields])
                self._filter_exclude.extend(['%s__%s' % (field_name, ff)
                                             for ff in resource_obj._filter_exclude])

        self._field_tree = make_field_tree(
            self.model, self._filter_fields, self._filter_exclude,
            self.filter_recursive, max_depth=self.max_filter_depth)

        # only filterable columns are sortable. Ordering by an excluded column
        # reveals its values.
        self._sortable_fields = set(f.name for f in self._field_tree.fields)

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

        # phase 1: breadth first search across the field tree created by
        # filter_fields, matching request parameters to fields and carrying
        # the foreign-key chain needed to reach each one.
        plan = []
        queue = [(self._field_tree, '', [])]
        while queue:
            node, prefix, fks = queue.pop(0)
            for field in node.fields:
                filter_expr = '%s%s' % (prefix, field.name)
                if filter_expr in raw_filters:
                    plan.append((field, fks, raw_filters.pop(filter_expr)))

            for child_prefix, child_node in node.children.items():
                fk = node.model._meta.fields[child_prefix]
                queue.append((child_node, prefix + child_prefix + '__', fks + [fk]))

        # keys left in raw_filters matched no filterable field (a typo, or a
        # field not exposed as a filter). reject them when the resource opts
        # in, else fall through and ignore them as before.
        if raw_filters and self.reject_unknown_filters:
            raise ValueError('Unrecognized filter(s): %s'
                             % ', '.join(sorted(raw_filters)))

        # phase 2: join each related path through its own alias (peewee's
        # filter()/ensure_join would collapse two fks to one model onto a
        # single join) and build predicates against the aliased field.
        alias_map = {}
        for field, fks, filters in plan:
            query, lhs = alias_field(query, self.model, fks, field, alias_map)
            for op, arg_list, negated in filters:
                clean_args = self.clean_arg_list(arg_list)
                if isinstance(field, BooleanField):
                    clean_args = [convert_boolean(arg) for arg in clean_args]
                query = self.apply_filter(query, lhs, op, clean_args, negated)

        return query

    def clean_arg_list(self, arg_list):
        return [self.value_transforms.get(arg, arg) for arg in arg_list]

    def apply_filter(self, query, field, op, arg_list, negated):
        # `field` arrives rebound to its join alias. DJANGO_MAP[op] is the
        # same callable peewee's filter() resolves ops through.
        op_fn = DJANGO_MAP[op]
        make = lambda value: ~op_fn(field, value) if negated else op_fn(field, value)

        if op in ('in', 'not_in'):
            # in/not_in values may be given comma-separated and/or as repeated
            # params, e.g. ?id__in=1,2&id__in=3 -> [1, 2, 3].
            values = []
            for arg in arg_list:
                values.extend(v.strip() for v in str(arg).split(','))
            return query.where(make(values))

        if op == 'between':
            # each value is one "low,high" pair. repeated pairs combine below.
            arg_list = [[v.strip() for v in str(arg).split(',')]
                        for arg in arg_list]
            if any(len(pair) != 2 for pair in arg_list):
                raise ValueError('between requires two comma-separated values')

        # a match ORs its values ("any of"), an exclusion ANDs them ("none
        # of"). the "-" prefix flips one into the other. without this a
        # repeated exclusion is vacuous: id != 1 OR id != 2 matches every row.
        exclude = negated ^ (op in self.NEGATIVE_OPS)
        combine = operator.and_ if exclude else operator.or_
        return query.where(reduce(combine, [make(val) for val in arg_list]))

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

    def check_unknown_fields(self, data, model=None, prefix=''):
        # collect payload keys the deserializer would not recognize as fields.
        # A foreign key may be written by field name ("user") or column name
        # ("user_id"), so both are considered known. nested dicts are checked
        # against the related model, mirroring the deserializer's traversal.
        model = model or self.model
        fields = model._meta.fields
        known = set(fields)
        known.update(f.object_id_name for f in model._meta.sorted_fields
                     if isinstance(f, ForeignKeyField))
        unknown = []
        for key, value in data.items():
            if key not in known:
                unknown.append(prefix + key)
            elif key in fields and isinstance(fields[key], ForeignKeyField) \
                    and isinstance(value, dict):
                unknown.extend(self.check_unknown_fields(
                    value, fields[key].rel_model, prefix + key + '__'))
        return unknown

    def deserialize_object(self, data, instance):
        data = self.scrub_readonly_fields(data)
        if self.reject_unknown_fields:
            unknown = self.check_unknown_fields(data)
            if unknown:
                raise ValueError('Unrecognized field(s): %s'
                                 % ', '.join(sorted(unknown)))
        d = self.get_deserializer()
        return d.deserialize_object(instance, data)

    def response_error(self, message, status):
        return Response(json.dumps({'error': message}), status=status,
                        mimetype='application/json')

    def response_forbidden(self):
        return self.response_error('Forbidden', 403)

    def response_not_found(self):
        return self.response_error('Not found', 404)

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
            ('/<pk>/', self.require_method(self.api_detail, ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])),
            ('/<pk>/delete/', self.require_method(self.post_delete, ['POST', 'DELETE'])),
        )

    def check_get(self, obj=None):
        return True

    def check_post(self, obj=None):
        return True

    def check_put(self, obj):
        return True

    def check_patch(self, obj):
        # api_detail dispatches check_* by method name, so PATCH needs a hook.
        return self.check_put(obj)

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
        try:
            obj = self.get_query().where(self.pk==pk).get()
        except self.model.DoesNotExist:
            return self.response_not_found()

        method = method or request.method

        if not getattr(self, 'check_%s' % method.lower())(obj):
            return self.response_forbidden()

        if method == 'GET':
            return self.object_detail(obj)
        elif method in ('PUT', 'PATCH', 'POST'):
            return self.edit(obj)
        elif method == 'DELETE':
            return self.delete(obj)

    def post_delete(self, pk):
        return self.api_detail(pk, 'DELETE')

    def apply_ordering(self, query):
        ordering = request.args.get('ordering') or ''
        return order_query(query, self.model, ordering,
                           self._sortable_fields.__contains__)

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

        # process any filters, translating an unknown-filter rejection into a
        # 400 (see reject_unknown_filters).
        try:
            query = self.process_query(query)
        except ValueError as exc:
            return self.response_bad_request(str(exc))

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

    def _write(self, instance, bulk=False):
        try:
            data = self.read_request_data()
        except ValueError:
            return self.response_bad_request('Request body is not valid JSON.')

        if bulk and isinstance(data, list):
            return self.create_bulk(data)
        if not isinstance(data, dict):
            return self.response_bad_request(
                'Request body must be a JSON object.')

        try:
            obj = self.persist_object(instance, data)
        except RestForbidden:
            return self.response_forbidden()
        except PERSIST_ERRORS as exc:
            return self.response_bad_request(str(exc))

        return self.response(self.serialize_object(obj))

    def create(self):
        return self._write(self.model(), bulk=self.allow_bulk)

    def create_bulk(self, data):
        if len(data) > self.max_bulk:
            return self.response_bad_request(
                'Bulk create accepts at most %s objects.' % self.max_bulk)

        objects = []
        try:
            # a failing item rolls back the whole batch. persist_object's own
            # atomic() nests here as a savepoint.
            with self.model._meta.database.atomic():
                for i, item in enumerate(data):
                    if not isinstance(item, dict):
                        raise ValueError(
                            'Object at index %s is not a JSON object.' % i)
                    try:
                        objects.append(self.persist_object(self.model(), item))
                    except PERSIST_ERRORS as exc:
                        raise ValueError('Object at index %s: %s' % (i, exc))
        except RestForbidden:
            return self.response_forbidden()
        except ValueError as exc:
            return self.response_bad_request(str(exc))

        return self.response(
            {'objects': [self.serialize_object(obj) for obj in objects]})

    def edit(self, obj):
        return self._write(obj)

    def delete(self, obj):
        res = obj.delete_instance(recursive=self.delete_recursive)
        return self.response({'deleted': res})


class RestrictOwnerResource(RestResource):
    # restrict edits (PUT/PATCH and a POST to a detail url) and DELETE to the
    # owner of the object, and stamp the current user as owner on any create.
    owner_field = 'user'

    def validate_owner(self, user, obj):
        return user == getattr(obj, self.owner_field)

    def set_owner(self, obj, user):
        setattr(obj, self.owner_field, user)

    def check_post(self, obj=None):
        # a list POST creates a new object (obj is None) and is open, becoming
        # owned by the caller in save_object. a detail POST edits an existing
        # object and must clear the same owner check as PUT.
        return obj is None or self.validate_owner(g.user, obj)

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
        return Response(json.dumps({'error': 'Authentication failed'}), 401, {
            'WWW-Authenticate': 'Basic realm="Login Required"'
        }, mimetype='application/json')

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
