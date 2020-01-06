import functools
import operator
import os
import re
try:
    import simplejson as json
except ImportError:
    import json

from flask import Blueprint
from flask import Response
from flask import abort
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_peewee.filters import FilterForm
from flask_peewee.filters import FilterMapping
from flask_peewee.filters import FilterModelConverter
from flask_peewee.forms import BaseModelConverter
from flask_peewee.forms import ChosenAjaxSelectWidget
from flask_peewee.forms import LimitedModelSelectField
from flask_peewee.serializer import Serializer
from flask_peewee.utils import PaginatedQuery
from flask_peewee.utils import get_next
from flask_peewee.utils import path_to_models
from flask_peewee.utils import slugify
from peewee import BooleanField
from peewee import DateField
from peewee import DateTimeField
from peewee import ForeignKeyField
from peewee import TextField
from werkzeug.datastructures import Headers
from wtforms import fields
from wtforms import widgets
from wtfpeewee.fields import ModelHiddenField
from wtfpeewee.fields import ModelSelectField
from wtfpeewee.fields import ModelSelectMultipleField
from wtfpeewee.orm import model_form


current_dir = os.path.dirname(__file__)


class AdminModelConverter(BaseModelConverter):
    def __init__(self, model_admin, additional=None):
        super(AdminModelConverter, self).__init__(additional)
        self.model_admin = model_admin

    def handle_foreign_key(self, model, field, **kwargs):
        if field.null:
            kwargs['allow_blank'] = True

        if field.name in (self.model_admin.foreign_key_lookups or ()):
            form_field = ModelHiddenField(model=field.rel_model, **kwargs)
        else:
            form_field = ModelSelectField(model=field.rel_model, **kwargs)
        return field.name, form_field


class AdminFilterModelConverter(FilterModelConverter):
    def __init__(self, model_admin, additional=None):
        super(AdminFilterModelConverter, self).__init__(additional)
        self.model_admin = model_admin

    def handle_foreign_key(self, model, field, **kwargs):
        if field.name in (self.model_admin.foreign_key_lookups or ()):
            data_source = url_for(self.model_admin.get_url_name('ajax_list'))
            widget = ChosenAjaxSelectWidget(data_source, field.name)
            form_field = LimitedModelSelectField(model=field.rel_model, widget=widget, **kwargs)
        else:
            form_field = ModelSelectField(model=field.rel_model, **kwargs)
        return field.name, form_field


class Action(object):
    def __init__(self, name=None, description=None):
        self.name = name or (type(self).__name__.replace('Action', ''))
        self.description = description or re.sub('[\-_]', ' ', self.name).title()

    def callback(self, id_list):
        """
        Perform an action on the list of IDs specified. If the return value is
        a Response object, then that will be returned to the user. Otherwise,
        the return value is ignored and the user is redirected to the index.
        """
        raise NotImplementedError


class ModelAdmin(object):
    """
    ModelAdmin provides create/edit/delete functionality for a peewee Model.
    """
    paginate_by = 20
    filter_paginate_by = 15

    # columns to display in the list index - can be field names or callables on
    # a model instance, though in the latter case they will not be sortable
    columns = None

    # exclude certian fields from being exposed as filters -- for related fields
    # use "__" notation, e.g. user__password
    filter_exclude = None
    filter_fields = None

    # form parameters, lists of fields
    exclude = None
    fields = None

    form_converter = AdminModelConverter

    # User-defined bulk actions. List or tuple of Action instances.
    actions = None

    # foreign_key_field --> related field to search on, e.g. {'user': 'username'}
    foreign_key_lookups = None

    # delete behavior
    delete_collect_objects = True
    delete_recursive = True

    filter_mapping = FilterMapping
    filter_converter = AdminFilterModelConverter

    # templates, to override see get_template_overrides()
    base_templates = {
        'index': 'admin/models/index.html',
        'add': 'admin/models/add.html',
        'edit': 'admin/models/edit.html',
        'delete': 'admin/models/delete.html',
        'export': 'admin/models/export.html',
    }

    def __init__(self, admin, model):
        self.admin = admin
        self.model = model
        self.db = model._meta.database
        self.pk = self.model._meta.primary_key

        self.templates = dict(self.base_templates)
        self.templates.update(self.get_template_overrides())

        self.action_map = dict((action.name, action)
                               for action in (self.actions or ()))

    def get_template_overrides(self):
        return {}

    def get_url_name(self, name):
        return '%s.%s_%s' % (
            self.admin.blueprint.name,
            self.get_admin_name(),
            name,
        )

    def get_filter_form(self):
        return FilterForm(
            self.model,
            self.filter_converter(self),
            self.filter_mapping(),
            self.filter_fields,
            self.filter_exclude,
        )

    def process_filters(self, query):
        filter_form = self.get_filter_form()
        form, query, cleaned = filter_form.process_request(query)
        return form, query, cleaned, filter_form._field_tree

    def get_form(self, adding=False):
        allow_pk = adding and not self.model._meta.auto_increment
        return model_form(self.model,
            allow_pk=allow_pk,
            only=self.fields,
            exclude=self.exclude,
            converter=self.form_converter(self),
        )

    def get_add_form(self):
        return self.get_form(adding=True)

    def get_edit_form(self, instance):
        return self.get_form()

    def get_query(self):
        return self.model.select()

    def get_object(self, pk):
        return self.get_query().where(self.pk==pk).get()

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
        return self.model._meta.sorted_field_names

    def column_is_sortable(self, col):
        return col in self.model._meta.fields

    def get_display_name(self):
        return self.model.__name__

    def get_admin_name(self):
        return slugify(self.model.__name__)

    def save_model(self, instance, form, adding=False):
        form.populate_obj(instance)
        instance.save(force_insert=adding)
        return instance

    def apply_ordering(self, query, ordering):
        if ordering:
            desc, column = ordering.startswith('-'), ordering.lstrip('-')
            if self.column_is_sortable(column):
                field = self.model._meta.fields[column]
                query = query.order_by(field.asc() if not desc else field.desc())
        return query

    def get_extra_context(self):
        return {}

    def index(self):
        if request.method == 'POST':
            id_list = request.form.getlist('id')
            action = request.form['action']
            if action == 'delete':
                return redirect(url_for(self.get_url_name('delete'), id=id_list))
            elif action == 'export':
                return redirect(url_for(self.get_url_name('export'), id=id_list))
            elif action in self.action_map:
                id_list = request.form.getlist('id')
                if not id_list:
                    flash('Please select one or more rows.', 'warning')
                else:
                    action_obj = self.action_map[action]
                    maybe_response = action_obj.callback(id_list)
                    if isinstance(maybe_response, Response):
                        return maybe_response
            else:
                flash('Unknown action: "%s".' % action, 'danger')
            return self._index_redirect()

        session['%s.index' % self.get_admin_name()] = request.url
        query = self.get_query()
        ordering = request.args.get('ordering') or ''
        query = self.apply_ordering(query, ordering)

        # process the filters from the request
        filter_form, query, cleaned, field_tree = self.process_filters(query)

        # create a paginated query out of our filtered results
        pq = PaginatedQuery(query, self.paginate_by)

        return render_template(self.templates['index'],
            model_admin=self,
            query=pq,
            ordering=ordering,
            filter_form=filter_form,
            field_tree=field_tree,
            active_filters=cleaned,
            **self.get_extra_context()
        )

    def _index_redirect(self):
        url = (session.get('%s.index' % self.get_admin_name()) or
               url_for(self.get_url_name('index')))
        return redirect(url)

    def dispatch_save_redirect(self, instance):
        if 'save' in request.form:
            return self._index_redirect()
        elif 'save_add' in request.form:
            return redirect(url_for(self.get_url_name('add')))
        else:
            return redirect(
                url_for(self.get_url_name('edit'), pk=instance._pk)
            )

    def add(self):
        Form = self.get_add_form()
        instance = self.model()

        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                instance = self.save_model(instance, form, True)
                flash('New %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form()

        return render_template(self.templates['add'],
            model_admin=self,
            form=form,
            instance=instance,
            **self.get_extra_context()
        )

    def edit(self, pk):
        try:
            instance = self.get_object(pk)
        except self.model.DoesNotExist:
            abort(404)

        Form = self.get_edit_form(instance)

        if request.method == 'POST':
            form = Form(request.form, obj=instance)
            if form.validate():
                self.save_model(instance, form, False)
                flash('Changes to %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form(obj=instance)

        return render_template(self.templates['edit'],
            model_admin=self,
            instance=instance,
            form=form,
            **self.get_extra_context()
        )

    def collect_objects(self, obj):
        deps = obj.dependencies()
        objects = []

        for query, fk in obj.dependencies():
            if not fk.null:
                sq = fk.model.select().where(query)
                collected = [rel_obj for rel_obj in sq.execute().iterator()]
                if collected:
                    objects.append((0, fk.model, collected))

        return sorted(objects, key=lambda i: (i[0], i[1].__name__))

    def delete(self):
        if request.method == 'GET':
            id_list = request.args.getlist('id')
        else:
            id_list = request.form.getlist('id')

        query = self.model.select().where(self.pk << id_list)

        if request.method == 'GET':
            collected = {}
            if self.delete_collect_objects:
                for obj in query:
                    collected[obj._pk] = self.collect_objects(obj)

        elif request.method == 'POST':
            count = query.count()
            for obj in query:
                obj.delete_instance(recursive=self.delete_recursive)

            flash('Successfully deleted %s %ss' % (count, self.get_display_name()), 'success')
            return self._index_redirect()

        return render_template(self.templates['delete'], **dict(
            model_admin=self,
            query=query,
            collected=collected,
            **self.get_extra_context()
        ))

    def collect_related_fields(self, model, accum, path, seen=None):
        seen = seen or set()
        path_str = '__'.join(path)
        for field in model._meta.sorted_fields:
            if isinstance(field, ForeignKeyField) and field not in seen:
                seen.add(field)
                self.collect_related_fields(field.rel_model, accum, path + [field.name], seen)
            elif model != self.model:
                accum.setdefault((model, path_str), [])
                accum[(model, path_str)].append(field)

        return accum

    def export(self):
        query = self.get_query()

        ordering = request.args.get('ordering') or ''
        query = self.apply_ordering(query, ordering)

        # process the filters from the request
        filter_form, query, cleaned, field_tree = self.process_filters(query)
        related = self.collect_related_fields(self.model, {}, [])

        # check for raw id
        id_list = request.args.getlist('id')
        if id_list:
            query = query.where(self.pk << id_list)

        if request.method == 'POST':
            raw_fields = request.form.getlist('fields')
            export = Export(query, related, raw_fields)
            return export.json_response('export-%s.json' % self.get_admin_name())

        return render_template(self.templates['export'],
            model_admin=self,
            model=query.model,
            query=query,
            filter_form=filter_form,
            field_tree=field_tree,
            active_filters=cleaned,
            related_fields=related,
            sql=query.sql(),
            **self.get_extra_context()
        )

    def ajax_list(self):
        field_name = request.args.get('field')
        prev_page = 0
        next_page = 0

        try:
            models = path_to_models(self.model, field_name)
        except AttributeError:
            data = []
        else:
            field = self.model._meta.fields[field_name]
            rel_model = models.pop()
            rel_field = rel_model._meta.fields[self.foreign_key_lookups[field_name]]
            query = rel_model.select().order_by(rel_field)
            query_string = request.args.get('query')
            if query_string:
                query = query.where(rel_field ** ('%%%s%%' % query_string))

            pq = PaginatedQuery(query, self.filter_paginate_by)
            current_page = pq.get_page()
            if current_page > 1:
                prev_page = current_page - 1
            if current_page < pq.get_pages():
                next_page = current_page + 1

            data = []

            # if the field is nullable, include the "None" option at the top of the list
            if field.null:
                data.append({'id': '__None', 'repr': 'None'})

            data.extend([{'id': obj._pk, 'repr': str(obj)} for obj in pq.get_list()])

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
        try:
            attr = getattr(model, field)
        except AttributeError:
            model_admin = self.admin[type(model)]
            try:
                attr = getattr(model_admin, field)
            except AttributeError:
                raise AttributeError('Could not find attribute or method '
                                     'named "%s".' % field)
            else:
                return attr(model)
        else:
            if callable(attr):
                attr = attr()
            return attr

    def get_form_field(self, form, field_name):
        return getattr(form, field_name)

    def fix_underscores(self, s):
        return s.replace('_', ' ').title()

    def update_querystring(self, querystring, key, val):
        if not querystring:
            return '%s=%s' % (key, val)
        else:
            querystring = re.sub('%s(?:[^&]+)?&?' % key, '', querystring.decode('utf8')).rstrip('&')
            return ('%s&%s=%s' % (querystring, key, val)).lstrip('&')

    def get_verbose_name(self, model, column_name):
        try:
            field = model._meta.fields[column_name]
        except KeyError:
            return self.fix_underscores(column_name)
        else:
            return field.verbose_name or self.fix_underscores(field.name)

    def get_model_admins(self):
        return {'model_admins': self.admin.get_model_admins(), 'branding': self.admin.branding}

    def get_admin_url(self, obj):
        model_admin = self.admin.get_admin_for(type(obj))
        if model_admin:
            return url_for(model_admin.get_url_name('edit'), pk=obj._pk)

    def get_model_name(self, model_class):
        model_admin = self.admin.get_admin_for(model_class)
        if model_admin:
            return model_admin.get_display_name()
        return model_class.__name__

    def apply_prefix(self, field_name, prefix_accum, field_prefix, rel_prefix='fr_', rel_sep='-'):
        accum = []
        for prefix in prefix_accum:
            accum.append('%s%s' % (rel_prefix, prefix))
        accum.append('%s%s' % (field_prefix, field_name))
        return rel_sep.join(accum)

    def prepare_environment(self):
        self.app.template_context_processors[None].append(self.get_model_admins)

        self.app.jinja_env.globals['get_model_field'] = self.get_model_field
        self.app.jinja_env.globals['get_form_field'] = self.get_form_field
        self.app.jinja_env.globals['get_verbose_name'] = self.get_verbose_name
        self.app.jinja_env.filters['fix_underscores'] = self.fix_underscores
        self.app.jinja_env.globals['update_querystring'] = self.update_querystring
        self.app.jinja_env.globals['get_admin_url'] = self.get_admin_url
        self.app.jinja_env.globals['get_model_name'] = self.get_model_name

        self.app.jinja_env.filters['apply_prefix'] = self.apply_prefix


class Admin(object):
    def __init__(self, app, auth, template_helper=AdminTemplateHelper,
                 prefix='/admin', name='admin', branding='flask-peewee'):
        self.app = app
        self.auth = auth

        self._admin_models = {}
        self._registry = {}
        self._panels = {}

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix

        self.template_helper = template_helper(self)
        self.template_helper.prepare_environment()

        self.branding = branding

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

        select = []
        joined = set()

        def ensure_join(query, m, p):
            if m not in joined:
                if '__' not in p:
                    next_model = query.model
                else:
                    next, _ = p.rsplit('__', 1)
                    next_model = self.alias_to_model[next]
                    query = ensure_join(query, next_model, next)

                joined.add(m)
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

            field = model._meta.fields[column]
            select.append(field)

        clone._select = select
        return clone

    def json_response(self, filename='export.json'):
        serializer = Serializer()
        prepared_query = self.prepare_query()
        field_dict = {}
        for field in prepared_query._select:
            field_dict.setdefault(field.model, [])
            field_dict[field.model].append(field.name)

        def generate():
            i = prepared_query.count()
            yield b'[\n'
            for obj in prepared_query:
                i -= 1
                obj_data = serializer.serialize_object(obj, field_dict)
                yield json.dumps(obj_data).encode('utf-8')
                if i > 0:
                    yield b',\n'
            yield b'\n]'
        headers = Headers()
        headers.add('Content-Type', 'application/javascript')
        headers.add('Content-Disposition', 'attachment; filename=%s' % filename)
        return Response(generate(), mimetype='text/javascript', headers=headers, direct_passthrough=True)
