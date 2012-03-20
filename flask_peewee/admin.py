import functools
import operator
import os
import re
try:
    import simplejson as json
except ImportError:
    import json

from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, Response
from flask_peewee.forms import BooleanSelectField, ForeignKeyField, CustomModelConverter
from flask_peewee.filters import QueryFilter, lookups_for_field, Lookup, FIELD_TYPES
from flask_peewee.serializer import Serializer
from flask_peewee.utils import get_next, PaginatedQuery, path_to_models, slugify
from peewee import BooleanField, DateTimeField, ForeignKeyField
from werkzeug import Headers
from wtforms import fields, widgets
from wtfpeewee.fields import ModelSelectField, ModelSelectMultipleField
from wtfpeewee.orm import model_form


current_dir = os.path.dirname(__file__)


class FieldValueMap(object):
    def __init__(self, model_admin):
        self.model_admin = model_admin

    def get_conversions(self):
        return {
            (BooleanField, 'eq'): self.handle_boolean,
            (DateTimeField, 'today'): self.handle_dummy,
            (DateTimeField, 'yesterday'): self.handle_dummy,
            (DateTimeField, 'this_week'): self.handle_dummy,
            (ForeignKeyField, 'eq'): self.handle_foreign_key,
            (ForeignKeyField, 'in'): self.handle_foreign_key_multi,
        }

    def convert(self, field, lookup, lookup_name, prefix):
        conversions = self.get_conversions()
        key = (type(field), lookup)
        lookup_obj = conversions.get(key, self.handle_default)(field, lookup, prefix)

        # wat
        lookup_obj.lookup_name = lookup_name
        lookup_obj.css_class = 'span2 input-small lookup-input'
        return lookup_obj

    def handle_default(self, field, lookup, prefix):
        return Lookup(field, lookup, 'text', prefix=prefix)

    def handle_dummy(self, field, lookup, prefix):
        return Lookup(field, lookup, 'hidden', prefix=prefix)

    def handle_boolean(self, field, lookup, prefix):
        return Lookup(field, lookup, 'select', [('1', 'True'), ('', 'False')], prefix=prefix)

    def fk_to_list(self, field):
        return [(obj.get_pk(), unicode(obj)) for obj in field.to.select()]

    def handle_foreign_key(self, field, lookup, prefix):
        _fkl = self.model_admin.foreign_key_lookups or {}
        if field.name not in _fkl:
            return Lookup(field, lookup, 'select', self.fk_to_list(field), prefix=prefix)
        return Lookup(field, lookup, 'foreign_key', field.to, prefix=prefix)

    def handle_foreign_key_multi(self, field, lookup, prefix):
        _fkl = self.model_admin.foreign_key_lookups or {}
        if field.name not in _fkl:
            return Lookup(field, lookup, 'select_multiple', self.fk_to_list(field), prefix=prefix)
        return Lookup(field, lookup, 'foreign_key_multiple', field.to, prefix=prefix)


class ModelAdmin(object):
    """
    ModelAdmin provides create/edit/delete functionality for a peewee Model.
    """
    paginate_by = 20
    filter_paginate_by = 15

    # columns to display in the list index - can be field names or callables on
    # a model instance, though in the latter case they will not be sortable
    columns = None

    # filter parameters -- what is available for filtering via the request
    exclude_filters = None
    ignore_filters = ('ordering', 'page',)

    # form parameters, lists of fields
    exclude = None
    fields = None

    # foreign_key_field --> related field to search on, e.g. {'user': 'username'}
    foreign_key_lookups = None

    # delete behavior
    delete_collect_objects = True
    delete_recursive = True

    def __init__(self, admin, model):
        self.admin = admin
        self.model = model
        self.pk_name = self.model._meta.pk_name
        self.templates = { 'index'  : 'admin/models/index.html',
                           'add'    : 'admin/models/add.html',
                           'edit'   : 'admin/models/edit.html',
                           'delete' : 'admin/models/delete.html' }

    def get_url_name(self, name):
        return '%s.%s_%s' % (
            self.admin.blueprint.name,
            self.get_admin_name(),
            name,
        )

    def get_form(self):
        return model_form(self.model, only=self.fields, exclude=self.exclude, converter=CustomModelConverter(self))

    def get_add_form(self):
        return self.get_form()

    def get_edit_form(self):
        return self.get_form()

    def get_query(self):
        return self.model.select()

    def get_object(self, pk):
        return self.get_query().get(**{self.pk_name: pk})

    def get_query_filter(self, query):
        return QueryFilter(query, self.ignore_filters)

    def get_urls(self):
        return (
            ('/', self.index),
            ('/add/', self.add),
            ('/delete/', self.delete),
            ('/export/', self.export),
            ('/<pk>/', self.edit),
            ('/_ajax/', self.ajax_list),
        )

    def get_columns(self):
        return self.model._meta.get_field_names()

    def column_is_sortable(self, col):
        return col in self.model._meta.fields

    def get_display_name(self):
        return self.model.__name__

    def get_admin_name(self):
        return slugify(self.model.__name__)

    def get_lookups(self, prefix=''):
        field_value_map = FieldValueMap(self)

        lookups = {}
        active_lookups = []

        for field in self.model._meta.get_fields():
            if self.exclude_filters and field.name in self.exclude_filters:
                continue

            for lookup, lookup_name in lookups_for_field(field):
                key = (prefix, field)
                lookups.setdefault(key, [])
                lookup_obj = field_value_map.convert(field, lookup, lookup_name, prefix)
                lookups[key].append(lookup_obj)

                if lookup_obj.name in request.args:
                    active_lookups.append(lookup_obj)

            if isinstance(field, ForeignKeyField):
                rel_prefix = '%s%s__' % (prefix, field.name)
                rel_model = field.to
                if rel_model in self.admin:
                    rel_lookups, rel_active = self.admin[rel_model].get_lookups(rel_prefix)
                    lookups.update(rel_lookups)
                    active_lookups.extend(rel_active)

        return lookups, active_lookups

    def save_model(self, instance, form, adding=False):
        form.populate_obj(instance)
        instance.save()
        return instance

    def apply_ordering(self, query, ordering):
        if ordering:
            desc, column = ordering.startswith('-'), ordering.lstrip('-')
            if self.column_is_sortable(column):
                query = query.order_by((column, desc and 'desc' or 'asc'))
        return query

    def index(self):
        query = self.get_query()

        ordering = request.args.get('ordering') or ''
        query = self.apply_ordering(query, ordering)

        # create a QueryFilter object with our current query
        query_filter = self.get_query_filter(query)

        # process the filters from the request
        filtered_query = query_filter.get_filtered_query()

        # create a paginated query out of our filtered results
        pq = PaginatedQuery(filtered_query, self.paginate_by)

        if request.method == 'POST':
            id_list = request.form.getlist('id')
            if request.form['action'] == 'delete':
                return redirect(url_for(self.get_url_name('delete'), id=id_list))
            else:
                return redirect(url_for(self.get_url_name('export'), id__in=id_list))

        lookups, active_lookups = self.get_lookups()

        return render_template(self.templates['index'],
            model_admin=self,
            query=pq,
            ordering=ordering,
            query_filter=query_filter,
            lookups=lookups,
            active_lookups=active_lookups,
        )

    def dispatch_save_redirect(self, instance):
        if 'save' in request.form:
            return redirect(url_for(self.get_url_name('index')))
        elif 'save_add' in request.form:
            return redirect(url_for(self.get_url_name('add')))
        else:
            return redirect(
                url_for(self.get_url_name('edit'), pk=instance.get_pk())
            )

    def add(self):
        Form = self.get_add_form()

        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                instance = self.save_model(self.model(), form, True)
                flash('New %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form()

        return render_template(self.templates['add'],
                               model_admin=self, form=form)

    def edit(self, pk):
        try:
            instance = self.get_object(pk)
        except self.model.DoesNotExist:
            abort(404)

        Form = self.get_edit_form()

        if request.method == 'POST':
            form = Form(request.form, obj=instance)
            if form.validate():
                self.save_model(instance, form, False)
                flash('Changes to %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form(obj=instance)

        return render_template(self.templates['edit'],
                               model_admin=self, instance=instance, form=form)

    def collect_objects(self, obj):
        select_queries, nullable_queries = obj.collect_queries()
        objects = []

        for query, fk_field, depth in select_queries:
            model = query.model
            query.query = ['*']
            collected = [obj for obj in query.execute().iterator()]
            if collected:
                objects.append((depth, model, fk_field, collected))

        return sorted(objects, key=lambda i: (i[0], i[1].__name__))

    def delete(self):
        if request.method == 'GET':
            id_list = request.args.getlist('id')
        else:
            id_list = request.form.getlist('id')

        query = self.model.select().where(**{
            '%s__in' % self.model._meta.pk_name: id_list
        })

        if request.method == 'GET':
            collected = {}
            if self.delete_collect_objects:
                for obj in query:
                    collected[obj.get_pk()] = self.collect_objects(obj)

        elif request.method == 'POST':
            count = query.count()
            for obj in query:
                obj.delete_instance(recursive=self.delete_recursive)

            flash('Successfully deleted %s %ss' % (count, self.get_display_name()), 'success')
            return redirect(url_for(self.get_url_name('index')))

        return render_template(self.templates['delete'],
                               **dict(model_admin=self,
                                      query=query,
                                      collected=collected))

    def collect_related_fields(self, model, accum, path):
        path_str = '__'.join(path)
        for field in model._meta.get_fields():
            if isinstance(field, ForeignKeyField):
                self.collect_related_fields(field.to, accum, path + [field.name])
            elif model != self.model:
                accum.setdefault((model, path_str), [])
                accum[(model, path_str)].append(field)

        return accum

    def export(self):
        query = self.get_query()

        ordering = request.args.get('ordering') or ''
        query = self.apply_ordering(query, ordering)

        # create a QueryFilter object with our current query
        query_filter = self.get_query_filter(query)

        # process the filters from the request
        filtered_query = query_filter.get_filtered_query()

        related = self.collect_related_fields(self.model, {}, [])

        if request.method == 'POST':
            raw_fields = request.form.getlist('fields')
            export = Export(filtered_query, related, raw_fields)
            return export.json_response()

        lookups, active_lookups = self.get_lookups()

        return render_template('admin/models/export.html',
            model_admin=self,
            model=filtered_query.model,
            query=filtered_query,
            query_filter=query_filter,
            related_fields=related,
            lookups=lookups,
            active_lookups=active_lookups,
        )

    def ajax_list(self):
        field = request.args.get('field')
        prev_page = 0
        next_page = 0

        try:
            models = path_to_models(self.model, field)
        except AttributeError:
            data = []
        else:
            rel_model = models.pop()
            rel_field = self.foreign_key_lookups[field]

            query = rel_model.select().where(**{
                '%s__icontains'% rel_field: request.args.get('query', ''),
            }).order_by(rel_field)

            pq = PaginatedQuery(query, self.filter_paginate_by)
            current_page = pq.get_page()
            if current_page > 1:
                prev_page = current_page - 1
            if current_page < pq.get_pages():
                next_page = current_page + 1

            data = [
                {'id': obj.get_pk(), 'repr': unicode(obj)} \
                    for obj in pq.get_list()
            ]

        json_data = json.dumps({'prev_page': prev_page, 'next_page': next_page, 'object_list': data})
        return Response(json_data, mimetype='application/json')


class AdminPanel(object):
    template_name = 'admin/panels/default.html'

    def __init__(self, admin, title):
        self.admin = admin
        self.title = title
        self.slug = slugify(self.title)

    def dashboard_url(self):
        return url_for('%s.index' % (self.admin.blueprint.name))

    def get_urls(self):
        return ()

    def get_url_name(self, name):
        return '%s.panel_%s_%s' % (
            self.admin.blueprint.name,
            self.slug,
            name,
        )

    def get_template_name(self):
        return self.template_name

    def get_context(self):
        return {}

    def render(self):
        return render_template(self.get_template_name(), panel=self, **self.get_context())


class AdminTemplateHelper(object):
    def __init__(self, admin):
        self.admin = admin
        self.app = self.admin.app

    def get_model_field(self, model, field):
        attr = getattr(model, field)
        if callable(attr):
            return attr()
        return attr

    def get_form_field(self, form, field_name):
        return getattr(form, field_name)

    def fix_underscores(self, s):
        return s.replace('_', ' ').title()

    def update_querystring(self, querystring, key, val):
        if not querystring:
            return '%s=%s' % (key, val)
        else:
            querystring = re.sub('%s(?:[^&]+)?&?' % key, '', querystring).rstrip('&')
            return ('%s&%s=%s' % (querystring, key, val)).lstrip('&')

    def get_verbose_name(self, model, column_name):
        try:
            field = model._meta.fields[column_name]
        except KeyError:
            return self.fix_underscores(column_name)
        else:
            return field.verbose_name

    def get_model_admins(self):
        return {'model_admins': self.admin.get_model_admins()}

    def get_admin_url(self, obj):
        model_admin = self.admin.get_admin_for(type(obj))
        if model_admin:
            return url_for(model_admin.get_url_name('edit'), pk=obj.get_pk())

    def get_model_name(self, model_class):
        model_admin = self.admin.get_admin_for(model_class)
        if model_admin:
            return model_admin.get_display_name()
        return model_class.__name__

    def prepare_environment(self):
        self.app.template_context_processors[None].append(self.get_model_admins)

        self.app.jinja_env.globals['get_model_field'] = self.get_model_field
        self.app.jinja_env.globals['get_form_field'] = self.get_form_field
        self.app.jinja_env.globals['get_verbose_name'] = self.get_verbose_name
        self.app.jinja_env.filters['fix_underscores'] = self.fix_underscores
        self.app.jinja_env.globals['update_querystring'] = self.update_querystring
        self.app.jinja_env.globals['get_admin_url'] = self.get_admin_url
        self.app.jinja_env.globals['get_model_name'] = self.get_model_name


class Admin(object):
    def __init__(self, app, auth, template_helper=AdminTemplateHelper,
                 prefix='/admin', name='admin'):
        self.app = app
        self.auth = auth

        self._admin_models = {}
        self._registry = {}
        self._panels = {}

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix

        self.template_helper = template_helper(self)
        self.template_helper.prepare_environment()

    def auth_required(self, func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            user = self.auth.get_logged_in_user()

            if not user:
                login_url = url_for('%s.login' % self.auth.blueprint.name, next=get_next())
                return redirect(login_url)

            if not self.check_user_permission(user):
                abort(403)

            return func(*args, **kwargs)
        return inner

    def check_user_permission(self, user):
        return user.admin

    def get_urls(self):
        return (
            ('/', self.auth_required(self.index)),
        )

    def __contains__(self, item):
        return item in self._registry

    def __getitem__(self, item):
        return self._registry[item]

    def register(self, model, admin_class=ModelAdmin):
        model_admin = admin_class(self, model)
        admin_name = model_admin.get_admin_name()

        self._registry[model] = model_admin

    def unregister(self, model):
        del(self._registry[model])

    def register_panel(self, title, panel):
        panel_instance = panel(self, title)
        self._panels[title] = panel_instance

    def unregister_panel(self, title):
        del(self._panels[title])

    def get_admin_for(self, model):
        return self._registry.get(model)

    def get_model_admins(self):
        return sorted(self._registry.values(), key=lambda o: o.get_admin_name())

    def get_panels(self):
        return sorted(self._panels.values(), key=lambda o: o.slug)

    def index(self):
        return render_template('admin/index.html',
            model_admins=self.get_model_admins(),
            panels=self.get_panels(),
        )

    def get_blueprint(self, blueprint_name):
        return Blueprint(
            blueprint_name,
            __name__,
            static_folder=os.path.join(current_dir, 'static'),
            template_folder=os.path.join(current_dir, 'templates'),
        )

    def register_blueprint(self, **kwargs):
        self.app.register_blueprint(
            self.blueprint,
            url_prefix=self.url_prefix,
            **kwargs
        )

    def configure_routes(self):
        for url, callback in self.get_urls():
            self.blueprint.route(url, methods=['GET', 'POST'])(callback)

        for model_admin in self._registry.values():
            admin_name = model_admin.get_admin_name()
            for url, callback in model_admin.get_urls():
                full_url = '/%s%s' % (admin_name, url)
                self.blueprint.add_url_rule(
                    full_url,
                    '%s_%s' % (admin_name, callback.__name__),
                    self.auth_required(callback),
                    methods=['GET', 'POST'],
                )

        for panel in self._panels.values():
            for url, callback in panel.get_urls():
                full_url = '/%s%s' % (panel.slug, url)
                self.blueprint.add_url_rule(
                    full_url,
                    'panel_%s_%s' % (panel.slug, callback.__name__),
                    self.auth_required(callback),
                    methods=['GET', 'POST'],
                )

    def setup(self):
        self.configure_routes()
        self.register_blueprint()


class Export(object):
    def __init__(self, query, related, fields):
        self.query = query
        self.related = related
        self.fields = fields

        self.alias_to_model = dict([(k[1], k[0]) for k in self.related.keys()])

    def prepare_query(self):
        clone = self.query.clone()

        select = {}

        def ensure_join(query, m, p):
            if m not in query._joined_models:
                if '__' not in p:
                    next_model = query.model
                else:
                    next, _ = p.rsplit('__', 1)
                    next_model = self.alias_to_model[next]
                    query = ensure_join(query, next_model, next)

                return query.switch(next_model).join(m)
            else:
                return query

        for lookup in self.fields:
            # lookup may be something like "content" or "user__user_name"
            if '__' in lookup:
                path, column = lookup.rsplit('__', 1)
                model = self.alias_to_model[path]
                clone = ensure_join(clone, model, path)
            else:
                model = self.query.model
                column = lookup

            select.setdefault(model, [])
            select[model].append(column)

        clone.query = select
        return clone

    def json_response(self):
        serializer = Serializer()
        prepared_query = self.prepare_query()

        def generate():
            i = prepared_query.count()
            yield '[\n'
            for obj in prepared_query:
                i -= 1
                yield json.dumps(serializer.serialize_object(obj, prepared_query.query))
                if i > 0:
                    yield ',\n'
            yield '\n]'
        headers = Headers()
        headers.add('Content-Type', 'application/javascript')
        headers.add('Content-Disposition', 'attachment; filename=export.json')
        return Response(generate(), mimetype='text/javascript', headers=headers, direct_passthrough=True)
