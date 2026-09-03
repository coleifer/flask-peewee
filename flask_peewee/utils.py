import datetime
import hmac
import math
import re
import sys
from hashlib import sha1
from urllib.parse import urlparse

from flask import abort
from flask import render_template
from flask import request
from peewee import BooleanField
from peewee import DateField
from peewee import DateTimeField
from peewee import DoesNotExist
from peewee import ForeignKeyField
from peewee import JOIN
from peewee import Model
from peewee import SelectQuery
from peewee import TimeField
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash



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

    # upper bound on ?page= when not counting, since there is no page count
    # to clamp to.
    max_page = 1000000

    def __init__(self, query_or_model, paginate_by, use_count=True):
        self.paginate_by = paginate_by
        self.use_count = use_count

        if isinstance(query_or_model, SelectQuery):
            self.query = query_or_model
            self.model = self.query.model
        else:
            self.model = query_or_model
            self.query = self.model.select()

    def get_page(self):
        curr_page = request.args.get(self.page_var)
        if curr_page and curr_page.isdigit():
            # clamp to the last page. isdigit() accepts any number of digits,
            # and a huge page overflows the OFFSET.
            last = self.get_pages() if self.use_count else self.max_page
            return min(max(int(curr_page), 1), last) or 1
        return 1

    def get_count(self):
        if not hasattr(self, '_get_count'):
            self._get_count = self.query.count()
        return self._get_count

    def get_pages(self):
        if not hasattr(self, '_get_pages'):
            self._get_pages = int(math.ceil(
                float(self.get_count()) / self.paginate_by))
        return self._get_pages

    def get_list(self):
        query = self.query.paginate(self.get_page(), self.paginate_by)
        if self.use_count:
            return query
        if not hasattr(self, '_get_list'):
            # limit() overrides paginate()'s limit but keeps its offset, so
            # the extra row determines has_next without a COUNT().
            rows = list(query.limit(self.paginate_by + 1))
            self.has_next = len(rows) > self.paginate_by
            self._get_list = rows[:self.paginate_by]
        return self._get_list

    def get_page_range(self, window=3):
        # a windowed list of page numbers around the current page, with None
        # marking gaps (rendered as an ellipsis), e.g. [1, None, 4, 5, 6, None, 20].
        total = self.get_pages()
        if total == 0:
            # an empty result set has no pages to page through.
            return []
        current = min(self.get_page(), total)
        pages = sorted(set(
            [1, total] +
            list(range(max(1, current - window), min(total, current + window) + 1))
        ))
        result = []
        prev = 0
        for page in pages:
            if page > prev + 1:
                result.append(None)
            result.append(page)
            prev = page
        return result


def get_next():
    if not request.query_string:
        return request.path
    return '%s?%s' % (request.path, request.query_string.decode('utf-8'))

def is_safe_url(url):
    # only allow redirects to relative, same-host paths -- reject absolute
    # urls (http://evil.com) and scheme-relative urls (//evil.com).
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc

def slugify(s):
    return re.sub(r'[^a-z0-9_\-]+', '-', s.lower())

def load_class(s):
    path, klass = s.rsplit('.', 1)
    __import__(path)
    mod = sys.modules[path]
    return getattr(mod, klass)

def get_dictionary_from_model(model, fields=None, exclude=None, path=()):
    # fields/exclude are keyed by path -- the tuple of field names from the
    # root object (() at the root, ('user',) for a nested fk, and so on) -- so
    # two relations to one model (from_user / to_user) get their own field set
    # instead of sharing one keyed by the model class.
    model_class = type(model)
    data = {}

    fields = fields or {}
    exclude = exclude or {}
    curr_exclude = exclude.get(path, [])
    curr_fields = fields.get(path, model._meta.sorted_field_names)

    for field_name in curr_fields:
        if field_name in curr_exclude:
            continue
        field_obj = model_class._meta.fields[field_name]
        field_data = model.__data__.get(field_name)
        child_path = path + (field_name,)
        if isinstance(field_obj, ForeignKeyField) and field_data and child_path in fields:
            rel_obj = getattr(model, field_name)
            data[field_name] = get_dictionary_from_model(rel_obj, fields, exclude, child_path)
        else:
            data[field_name] = field_data
    return data

def get_model_from_dictionary(model, field_dict, strict=False):
    if isinstance(model, Model):
        model_instance = model
        check_fks = True
    else:
        model_instance = model()
        check_fks = False
    models = [model_instance]
    for field_name, value in field_dict.items():
        try:
            field_obj = model._meta.fields[field_name]
        except KeyError:
            # non-field keys (the "user_id" column name, a user property) are
            # set on the instance. underscore names are peewee internals, and
            # setting _pk or __data__ retargets the write to another row, so
            # they are dropped. strict callers reject unknowns upstream
            # (RestResource.reject_unknown_fields).
            if not strict and not field_name.startswith('_'):
                try:
                    setattr(model_instance, field_name, value)
                except AttributeError:
                    pass  # read-only property, no setter
            continue

        if isinstance(value, dict) and isinstance(field_obj, ForeignKeyField):
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
            if isinstance(field_obj, BooleanField):
                value = convert_boolean(value)
            elif isinstance(field_obj, (DateTimeField, DateField, TimeField)):
                value = deserialize_datetime(field_obj, value)

            setattr(model_instance, field_name, field_obj.python_value(value))
    return model_instance, models

ISO_FORMATS = ('%Y-%m-%dT%H:%M:%S.%f%z',
               '%Y-%m-%dT%H:%M:%S%z',
               '%Y-%m-%dT%H:%M:%S.%f',
               '%Y-%m-%dT%H:%M:%S',
               '%Y-%m-%dT',
               '%Y-%m-%d')

def deserialize_datetime(field_obj, value):
    # String values arriving over the wire are parsed against the field's own
    # formats plus the ISO-8601 variants the serializer emits.  An unparseable
    # string raises ValueError (a 400 in the REST api) rather than passing
    # garbage through to the database, which sqlite would happily store.
    if not isinstance(value, str):
        return value
    if not value:
        # empty string (e.g. a blank form input) means "no value".
        return None
    formats = list(getattr(field_obj, 'formats', None) or ())
    formats.extend(f for f in ISO_FORMATS if f not in formats)
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError('Unrecognized date/time value for "%s": %r'
                     % (field_obj.name, value))

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
        accum.extend(path_to_models(field.rel_model, path))
    return accum


def alias_join_path(query, base_model, fks, alias_map, join_type=JOIN.INNER,
                    bind=False):
    """
    Join `query` from `base_model` along the foreign keys in `fks`, aliasing each
    related model so two paths to the same model do not collapse onto one join.
    peewee's ensure_join dedupes by model pair and ignores the fk, so filtering
    two different foreign keys to the same model would otherwise share a single
    join and both predicates would hit one alias.

    Joins default to INNER; pass ``JOIN.LEFT_OUTER`` (as search does) to keep a
    base row whose foreign key along the path is null.  `alias_map` caches a path
    prefix -> terminal alias, so repeated uses of one path share their join.
    Returns (query, terminal), where terminal is the base model for an empty path
    or the final alias.
    """
    src = base_model
    prefix = ()
    for fk in fks:
        prefix += (fk.name,)
        dest = alias_map.get(prefix)
        if dest is None:
            dest = fk.rel_model.alias()
            alias_map[prefix] = dest
            # bind=True attaches the alias to the fk's own attr so the joined row
            # is available for serialization. the default uses a throwaway attr,
            # so a filter/search join does not overwrite (and, on a LEFT join
            # with no match, null out) the real relation.
            attr = fk.name if bind else '_join_%s' % '__'.join(prefix)
            query = query.join_from(
                src, dest, join_type,
                on=(getattr(src, fk.name) == getattr(dest, fk.rel_field.name)),
                attr=attr)
        src = dest
    return query, src


def alias_field(query, base_model, fks, field, alias_map, join_type=JOIN.INNER):
    """
    Join `query` along `fks` via alias_join_path and rebind `field` to the
    terminal alias, returning (query, field) ready to build a predicate.
    An empty path returns the field untouched.
    """
    query, target = alias_join_path(query, base_model, fks, alias_map, join_type)
    if target is not base_model:
        field = getattr(target, field.name)
    return query, field


def order_query(query, model, ordering, is_sortable):
    if ordering:
        column = ordering.lstrip('-')
        if is_sortable(column):
            field = model._meta.fields[column]
            return query.order_by(
                field.desc() if ordering.startswith('-') else field.asc())
    return query


def convert_boolean(s):
    if isinstance(s, str) and s.lower() in ('', '0', 'false', 'f'):
        return False
    return bool(s)


# legacy django-style salted-sha1 hashes, e.g. "a1b2c$<40 hex chars>".
LEGACY_PASSWORD_RE = re.compile(r'^[0-9a-f]{5}\$[0-9a-f]{40}$')

# hashing method passed to werkzeug -- override to tune cost, e.g. in tests.
# See werkzeug.security.generate_password_hash for accepted values.
PASSWORD_HASH_METHOD = 'scrypt'


def get_hexdigest(salt, raw_password):
    data = salt + raw_password
    return sha1(data.encode('utf8')).hexdigest()

def is_legacy_password(enc_password):
    return bool(LEGACY_PASSWORD_RE.match(enc_password or ''))

def make_password(raw_password):
    return generate_password_hash(raw_password, method=PASSWORD_HASH_METHOD)

def check_password(raw_password, enc_password):
    if is_legacy_password(enc_password):
        salt, hsh = enc_password.split('$', 1)
        return hmac.compare_digest(hsh, get_hexdigest(salt, raw_password))
    return check_password_hash(enc_password, raw_password)
