import csv
import functools
import io
import json
import operator
import os
import re
from urllib.parse import parse_qsl
from urllib.parse import urlencode

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
from flask_peewee.forms import AjaxSelectWidget
from flask_peewee.forms import LimitedModelSelectField
from flask_peewee.forms import ScopedModelSelectField
from flask_peewee.serializer import Serializer
from flask_peewee.utils import PaginatedQuery
from flask_peewee.utils import alias_field
from flask_peewee.utils import alias_join_path
from flask_peewee.utils import get_next
from flask_peewee.utils import order_query
from flask_peewee.utils import path_to_models
from flask_peewee.utils import slugify
from peewee import ForeignKeyField
from peewee import JOIN
from werkzeug.datastructures import CombinedMultiDict
from werkzeug.datastructures import Headers
from wtforms import fields
from wtfpeewee.fields import ModelHiddenField
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
            query = self.model_admin.admin.get_query_for(field.rel_model)
            form_field = ScopedModelSelectField(query=query, **kwargs)
        return field.name, form_field


class AdminFilterModelConverter(FilterModelConverter):
    def __init__(self, model_admin, additional=None):
        super(AdminFilterModelConverter, self).__init__(additional)
        self.model_admin = model_admin

    def handle_foreign_key(self, model, field, **kwargs):
        if field.name in (self.model_admin.foreign_key_lookups or ()):
            data_source = url_for(self.model_admin.get_url_name('ajax_list'))
            kwargs['widget'] = AjaxSelectWidget(data_source, field.name)
        query = self.model_admin.admin.get_query_for(field.rel_model)
        form_field = LimitedModelSelectField(query=query, **kwargs)
        return field.name, form_field


class Action(object):
    def __init__(self, name=None, description=None, confirm=False,
                 form_class=None):
        self.name = name or (type(self).__name__.replace('Action', ''))
        self.description = description or re.sub(r'[\-_]', ' ', self.name).title()
        self.confirm = confirm or form_class is not None
        self.form_class = form_class

    def callback(self, id_list):
        """
        Perform an action on the list of IDs specified. If the return value is
        a Response object, then that will be returned to the user. Otherwise,
        the return value is ignored and the user is redirected to the index.

        With confirm=True the callback runs after a confirmation page. A
        form_class action gets the validated form as callback(id_list, form).
        """
        raise NotImplementedError


class ModelAdmin(object):
    """
    ModelAdmin provides create/edit/delete functionality for a peewee Model.
    """
    paginate_by = 20
    filter_paginate_by = 15

    # columns to display in the list index - can be field names, model
    # attributes, or callables on a model instance or the ModelAdmin.
    columns = None

    # set False to skip COUNT(*) on huge tables. the list view then paginates
    # with prev/next links only and the dashboard and tab counts are hidden.
    paginate_count = True

    # exclude certian fields from being exposed as filters -- for related fields
    # use "__" notation, e.g. user__password
    filter_exclude = None
    filter_fields = None

    # char/text field names for the quick-search box. supports "__" traversal
    # into related models, e.g. 'user__username'. empty -> no search box.
    search_fields = None

    # max related-model hops when auto-building the filter and export field
    # trees, so a long or densely linked fk graph cannot explode them.
    max_filter_depth = 3

    # form parameters, lists of fields
    exclude = None
    fields = None

    # field names to render as readonly values, shown only on the edit page.
    # Can be field names, model attributes, callables or ModelAdmin methods.
    readonly_fields = None

    # ((label, {'fields': [...], 'collapsed': True}), ...) groups the add and
    # edit forms into sections. label None for an unlabeled section. Fields
    # left out of every entry render in a trailing unlabeled section.
    fieldsets = None

    # per-field wtforms kwargs passed through to wtf-peewee's model_form,
    # e.g. {'content': {'label': 'Body', 'validators': [...]}}
    field_args = None

    form_converter = AdminModelConverter

    # User-defined bulk actions. List or tuple of Action instances.
    actions = None

    # foreign_key_field --> related field to search on, e.g. {'user': 'username'}
    foreign_key_lookups = None

    # delete behavior
    delete_collect_objects = True
    delete_recursive = True

    # per-model permissions, consulted via check_add/check_edit/check_delete.
    can_add = True
    can_edit = True
    can_delete = True

    # restrict which fields may be exported. export_fields is a whitelist of
    # field names, export_exclude a blacklist. Related models are restricted
    # by their own registered ModelAdmin's settings.
    export_fields = None
    export_exclude = None

    filter_mapping = FilterMapping
    filter_converter = AdminFilterModelConverter

    # templates, to override see get_template_overrides()
    base_templates = {
        'index': 'admin/models/index.html',
        'add': 'admin/models/add.html',
        'edit': 'admin/models/edit.html',
        'delete': 'admin/models/delete.html',
        'action_confirm': 'admin/models/action_confirm.html',
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
            self.max_filter_depth,
        )

    def process_filters(self, query):
        filter_form = self.get_filter_form()
        form, query, cleaned = filter_form.process_request(query)
        return form, query, cleaned, filter_form._field_tree

    def get_form(self, adding=False):
        allow_pk = adding and not self.model._meta.auto_increment
        only, exclude = self.fields, self.exclude
        readonly = self.readonly_fields or ()
        if readonly:
            if only:
                only = [f for f in only if f not in readonly]
                if not only:
                    # model_form treats an empty "only" as no whitelist at
                    # all, which would expose every field.
                    only = None
                    exclude = [f.name for f in self.model._meta.sorted_fields]
            else:
                exclude = list(exclude or ()) + list(readonly)
        return model_form(self.model,
            allow_pk=allow_pk,
            only=only,
            exclude=exclude,
            field_args=self.field_args,
            converter=self.form_converter(self),
        )

    def get_add_form(self):
        return self.get_form(adding=True)

    def get_edit_form(self, instance):
        return self.get_form()

    def get_form_sections(self, form, instance=None):
        """
        Group the form into (label, collapsed, rows) sections for rendering.
        A row is (field, label, value), a bound form field or, with field
        None, an inert readonly value. Readonly rows are dropped when
        instance is None (the add page).
        """
        readonly = self.readonly_fields or ()

        def rows(names):
            accum = []
            for name in names:
                if name in form:
                    accum.append((form[name], None, None))
                elif name in readonly and instance is not None:
                    accum.append((
                        None,
                        self.admin.get_verbose_name(self.model, name),
                        self.admin.get_model_field(instance, name)))
            return accum

        # form fields and readonly names interleaved in model-field order,
        # with readonly names that are not columns (methods) at the end.
        names = [f.name for f in self.model._meta.sorted_fields
                 if f.name in form or f.name in readonly]
        names += [f.name for f in form if f.name not in names]
        names += [n for n in readonly if n not in names]

        if not self.fieldsets:
            return [(None, False, rows(names))]

        sections, seen = [], set()
        for label, options in self.fieldsets:
            seen.update(options['fields'])
            sections.append((label, options.get('collapsed', False),
                             rows(options['fields'])))
        leftover = [n for n in names if n not in seen]
        if leftover:
            sections.append((None, False, rows(leftover)))
        return sections

    def get_query(self):
        return self.model.select()

    def get_object(self, pk):
        return self.get_query().where(self.pk==pk).get()

    def get_urls(self):
        return (
            ('/', self.index),
            ('/add/', self.add),
            ('/delete/', self.delete),
            ('/action/', self.action_confirm),
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
        return order_query(query, self.model, ordering, self.column_is_sortable)

    def get_extra_context(self):
        return {}

    def get_search_fields(self):
        return self.search_fields or []

    def _resolve_search_field(self, name):
        # resolve a possibly-dotted search field to its Field object plus the
        # foreign keys that must be joined to reach it.
        model = self.model
        fks = []
        parts = name.split('__')
        for attr in parts[:-1]:
            fk = model._meta.fields[attr]
            fks.append(fk)
            model = fk.rel_model
        return model._meta.fields[parts[-1]], fks

    def apply_search(self, query, term):
        term = (term or '').strip()
        search_fields = self.get_search_fields()
        if not term or not search_fields:
            return query

        # search LEFT OUTER joins each path so a row whose foreign key is null
        # still appears when it matches a direct field. filters INNER join.
        alias_map = {}
        clauses = []
        for name in search_fields:
            field, fks = self._resolve_search_field(name)
            query, field = alias_field(
                query, self.model, fks, field, alias_map, JOIN.LEFT_OUTER)
            clauses.append(field.contains(term))

        return query.where(functools.reduce(operator.or_, clauses))

    def get_form_data(self):
        # combine files with form data so file-upload fields (e.g. blobs)
        # receive their uploads.
        if request.files:
            return CombinedMultiDict((request.files, request.form))
        return request.form

    def check_add(self, user):
        return self.can_add

    def check_edit(self, user):
        return self.can_edit

    def check_delete(self, user):
        return self.can_delete

    def _abort_unless(self, check):
        # views run behind auth_required, so a user is always present.
        if not check(self.admin.auth.get_logged_in_user()):
            abort(403)

    def _selected(self):
        # honor get_query() so a scoped admin only acts on, and the confirm
        # pages only disclose, rows the user is allowed to see.
        return self.get_query().where(self.pk << request.values.getlist('id'))

    def index(self):
        if request.method == 'POST':
            id_list = request.form.getlist('id')
            action = request.form['action']
            if action == 'delete':
                self._abort_unless(self.check_delete)
                return redirect(url_for(self.get_url_name('delete'), id=id_list))
            elif action == 'export':
                return redirect(url_for(self.get_url_name('export'), id=id_list))
            elif action in self.action_map:
                if not id_list:
                    flash('Please select one or more rows.', 'warning')
                else:
                    action_obj = self.action_map[action]
                    if action_obj.confirm:
                        return redirect(url_for(
                            self.get_url_name('action_confirm'),
                            name=action, id=id_list))
                    maybe_response = action_obj.callback(
                        [obj._pk for obj in self._selected()])
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

        # apply the quick-search term, if any
        search_query = request.args.get('q') or ''
        query = self.apply_search(query, search_query)

        # create a paginated query out of our filtered results
        pq = PaginatedQuery(query, self.paginate_by, use_count=self.paginate_count)

        return render_template(self.templates['index'],
            admin=self.admin,
            model_admin=self,
            query=pq,
            ordering=ordering,
            search_query=search_query,
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
        self._abort_unless(self.check_add)
        Form = self.get_add_form()
        instance = self.model()

        if request.method == 'POST':
            form = Form(self.get_form_data())
            if form.validate():
                instance = self.save_model(instance, form, True)
                flash('New %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form()

        return render_template(self.templates['add'],
            admin=self.admin,
            model_admin=self,
            form=form,
            instance=instance,
            **self.get_extra_context()
        )

    def edit(self, pk):
        self._abort_unless(self.check_edit)
        try:
            instance = self.get_object(pk)
        except self.model.DoesNotExist:
            abort(404)

        Form = self.get_edit_form(instance)

        if request.method == 'POST':
            form = Form(self.get_form_data(), obj=instance)
            if form.validate():
                self.save_model(instance, form, False)
                flash('Changes to %s saved successfully' % self.get_display_name(), 'success')
                return self.dispatch_save_redirect(instance)
        else:
            form = Form(obj=instance)

        return render_template(self.templates['edit'],
            admin=self.admin,
            model_admin=self,
            instance=instance,
            form=form,
            **self.get_extra_context()
        )

    def collect_objects(self, obj):
        objects = []

        for query, fk in obj.dependencies():
            if not fk.null:
                sq = fk.model.select().where(query)
                collected = list(sq.execute().iterator())
                if collected:
                    objects.append((0, fk.model, collected))

        return sorted(objects, key=lambda i: i[1].__name__)

    def delete(self):
        self._abort_unless(self.check_delete)
        query = self._selected()

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
            admin=self.admin,
            model_admin=self,
            query=query,
            collected=collected,
            **self.get_extra_context()
        ))

    def action_confirm(self):
        action = self.action_map.get(request.values.get('name'))
        if action is None or not action.confirm:
            abort(404)

        query = self._selected()

        form = None
        if action.form_class:
            # an empty-but-present formdata makes wtforms clobber field
            # defaults, so the GET render passes None.
            data = request.form if request.method == 'POST' else None
            form = action.form_class(data)

        if request.method == 'POST' and (form is None or form.validate()):
            id_list = [obj._pk for obj in query]
            args = (id_list,) if form is None else (id_list, form)
            maybe_response = action.callback(*args)
            if isinstance(maybe_response, Response):
                return maybe_response
            flash('Successfully applied %s to %s %ss' % (
                action.description, len(id_list), self.get_display_name()),
                'success')
            return self._index_redirect()

        return render_template(self.templates['action_confirm'],
            admin=self.admin,
            model_admin=self,
            action=action,
            form=form,
            query=query,
            **self.get_extra_context()
        )

    def get_export_fields(self, model=None):
        # the set of field names that may be exported for `model` -- the base
        # model uses this admin's settings, related models defer to their own
        # registered ModelAdmin (falling back to all fields when unregistered).
        model = model or self.model
        if model is self.model:
            include, exclude = self.export_fields, self.export_exclude
        else:
            rel_admin = self.admin.get_admin_for(model)
            if rel_admin is not None:
                include, exclude = rel_admin.export_fields, rel_admin.export_exclude
            else:
                include, exclude = None, None

        names = list(include) if include else list(model._meta.sorted_field_names)
        exclude = set(exclude or ())
        return [name for name in names if name not in exclude]

    def get_export_field_objects(self, model=None):
        model = model or self.model
        allowed = self.get_export_fields(model)
        return [model._meta.fields[name] for name in allowed]

    def collect_related_fields(self, model, accum, path, seen=None):
        # `seen` is the fk path to this model (breaks cycles without collapsing
        # two paths to one model), and len(path) bounds the walk to
        # max_filter_depth hops.
        seen = seen or frozenset()
        path_str = '__'.join(path)
        for field in model._meta.sorted_fields:
            if isinstance(field, ForeignKeyField) and field not in seen \
                    and len(path) < self.max_filter_depth:
                self.collect_related_fields(
                    field.rel_model, accum, path + [field.name], seen | {field})
            elif model != self.model and field.name in self.get_export_fields(model):
                accum.setdefault((model, path_str), [])
                accum[(model, path_str)].append(field)

        return accum

    def get_exportable_lookups(self, related):
        # every field lookup ("content", "user__username") the current
        # configuration permits -- used to reject anything else on POST.
        allowed = set(self.get_export_fields(self.model))
        for (model, path), fields in related.items():
            for field in fields:
                allowed.add('%s__%s' % (path, field.name))
        return allowed

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
            # enforce the export allowlist server-side so restricted fields
            # cannot be dumped by posting field names directly.
            allowed = self.get_exportable_lookups(related)
            raw_fields = [f for f in request.form.getlist('fields') if f in allowed]
            if not raw_fields:
                # an empty or fully-excluded selection exports identities only.
                # an empty field list otherwise leaves the query columns
                # unrestricted and the serializer defaulting to every field, so
                # it would dump excluded columns such as the password hash.
                raw_fields = [self.pk.name]
            export = Export(query, related, raw_fields)
            if request.form.get('format') == 'csv':
                return export.csv_response('export-%s.csv' % self.get_admin_name())
            return export.json_response('export-%s.json' % self.get_admin_name())

        return render_template(self.templates['export'],
            admin=self.admin,
            model_admin=self,
            model=query.model,
            query=query,
            filter_form=filter_form,
            field_tree=field_tree,
            active_filters=cleaned,
            export_fields=self.get_export_field_objects(),
            related_fields=related,
            sql=query.sql(),
            **self.get_extra_context()
        )

    def ajax_list(self):
        field_name = request.args.get('field')
        prev_page = 0
        next_page = 0

        data = []
        lookups = self.foreign_key_lookups or {}
        try:
            models = path_to_models(self.model, field_name)
        except (AttributeError, TypeError):
            # field is missing or not a relation on this model.
            models = None

        if models is not None and field_name in lookups:
            field = self.model._meta.fields[field_name]
            rel_model = models.pop()
            rel_field = rel_model._meta.fields[lookups[field_name]]
            # enumerate candidates through the related admin's get_query() so the
            # picker respects that admin's row visibility.
            query = self.admin.get_query_for(rel_model).order_by(rel_field)
            query_string = request.args.get('query')
            if query_string:
                query = query.where(rel_field.contains(query_string))

            pq = PaginatedQuery(query, self.filter_paginate_by)
            current_page = pq.get_page()
            if current_page > 1:
                prev_page = current_page - 1
            if current_page < pq.get_pages():
                next_page = current_page + 1

            # if the field is nullable, include the "None" option at the top.
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


class Admin(object):
    def __init__(self, app, auth, prefix='/admin', name='admin', branding='flask-peewee', theme=None):
        self.app = app
        self.auth = auth

        self._registry = {}
        self._panels = {}

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix
        self.branding = branding
        self.theme = theme

        self.prepare_template_environment()

    def get_url_name(self, name):
        return '%s.%s' % (self.blueprint.name, name)

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
        self._registry[model] = model_admin

    def unregister(self, model):
        del(self._registry[model])

    def register_panel(self, title, panel, *args, **kwargs):
        panel_instance = panel(self, title, *args, **kwargs)
        self._panels[title] = panel_instance

    def unregister_panel(self, title):
        del(self._panels[title])

    def get_admin_for(self, model):
        return self._registry.get(model)

    def get_query_for(self, model):
        # the base query for a model, scoped by its registered admin's
        # get_query() when it has one. Falls back to the bare model select so an
        # unregistered related model still resolves.
        model_admin = self.get_admin_for(model)
        return model_admin.get_query() if model_admin else model.select()

    def get_model_admins(self):
        return sorted(self._registry.values(), key=lambda o: o.get_admin_name())

    def get_panels(self):
        return sorted(self._panels.values(), key=lambda o: o.slug)

    def index(self):
        return render_template('admin/index.html',
                               admin=self,
                               model_admins=self.get_model_admins(),
                               panels=self.get_panels())

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

    def get_model_field(self, model, field):
        # a ModelAdmin method with the same name as a column overrides its
        # display. Methods inherited from ModelAdmin itself do not count, since
        # a column may share a name with one (export, add).
        model_admin = self.get_admin_for(type(model))
        if model_admin is not None:
            attr = getattr(type(model_admin), field, None)
            if callable(attr) and attr is not getattr(ModelAdmin, field, None):
                return getattr(model_admin, field)(model)

        try:
            attr = getattr(model, field)
        except AttributeError:
            raise AttributeError('Could not find attribute or method '
                                 'named "%s".' % field)
        return attr() if callable(attr) else attr

    def get_form_field(self, form, field_name):
        return getattr(form, field_name)

    def fix_underscores(self, s):
        return s.replace('_', ' ').title()

    def update_querystring(self, querystring, key, val):
        if isinstance(querystring, bytes):
            querystring = querystring.decode('utf8')
        parsed = parse_qsl(querystring or '', keep_blank_values=True)
        pairs = [(k, v) for k, v in parsed if k != key]
        pairs.append((key, val))
        return urlencode(pairs)

    def get_verbose_name(self, model, column_name):
        try:
            field = model._meta.fields[column_name]
        except KeyError:
            return self.fix_underscores(column_name)
        else:
            return field.verbose_name or self.fix_underscores(field.name)

    def get_admin_url(self, obj):
        model_admin = self.get_admin_for(type(obj))
        if model_admin:
            return url_for(model_admin.get_url_name('edit'), pk=obj._pk)

    def get_logout_url(self):
        return url_for('%s.logout' % self.auth.blueprint.name)

    def get_model_name(self, model_class):
        model_admin = self.get_admin_for(model_class)
        if model_admin:
            return model_admin.get_display_name()
        return model_class.__name__

    def apply_prefix(self, field_name, prefix_accum, field_prefix, rel_prefix='fr_', rel_sep='-'):
        accum = []
        for prefix in prefix_accum:
            accum.append('%s%s' % (rel_prefix, prefix))
        accum.append('%s%s' % (field_prefix, field_name))
        return rel_sep.join(accum)

    def prepare_template_environment(self):
        self.app.jinja_env.filters['apply_prefix'] = self.apply_prefix


class Export(object):
    def __init__(self, query, related, fields):
        self.query = query
        self.related = related
        self.fields = fields

    def prepare_query(self):
        clone = self.query.clone()
        base = self.query.model
        select = []
        field_dict = {}
        alias_map = {}

        # field_dict is keyed by path (see get_dictionary_from_model), the
        # tuple of fk names from the base, so two fks to one model do not share
        # a field set.
        def want(path, name):
            names = field_dict.setdefault(path, [])
            if name not in names:
                names.append(name)

        def pick(field):
            if not any(f is field for f in select):
                select.append(field)

        for lookup in self.fields:
            if '__' not in lookup:
                want((), lookup)
                pick(base._meta.fields[lookup])
                continue

            path, column = lookup.rsplit('__', 1)
            fks, model = [], base
            for part in path.split('__'):
                fk = model._meta.fields[part]
                fks.append(fk)
                model = fk.rel_model

            clone, alias = alias_join_path(clone, base, fks, alias_map, bind=True)

            # serializing a related column needs get_dictionary_from_model to
            # recurse into each fk on the path, which requires the fk name in the
            # field list and its id at every hop. under a bound join peewee reads
            # that id from the aliased row's primary key, so select each alias pk.
            prefix = ()
            for fk in fks:
                want(prefix, fk.name)
                prefix += (fk.name,)
                dest = alias_map[prefix]
                pick(getattr(dest, fk.rel_field.name))
            want(prefix, column)
            pick(getattr(alias, column))

        if select:
            clone = clone.columns(*select)
        return clone, field_dict

    def _response(self, generate, filename, mimetype):
        headers = Headers()
        headers.add('Content-Disposition', 'attachment; filename=%s' % filename)
        return Response(generate(), mimetype=mimetype, headers=headers, direct_passthrough=True)

    def rows(self):
        # a generator function, not a generator expression. an expression over
        # the ModelSelect would execute it while the response is being built,
        # and the request teardown then closes the connection before the body
        # is streamed.
        serializer = Serializer()
        prepared_query, field_dict = self.prepare_query()
        for obj in prepared_query:
            yield serializer.serialize_object(obj, field_dict)

    def json_response(self, filename='export.json'):
        def generate():
            # prefix the separator from the second row on, rather than keying
            # commas off a pre-count. a count taken before iteration can
            # disagree with the rows actually streamed (a concurrent insert or
            # delete), producing a missing or trailing comma and invalid JSON.
            yield b'[\n'
            first = True
            for obj_data in self.rows():
                if not first:
                    yield b',\n'
                first = False
                yield json.dumps(obj_data).encode('utf-8')
            yield b'\n]'
        return self._response(generate, filename, 'application/json')

    def flatten_object(self, obj_data):
        # a null fk yields None, which csv.writer renders as an empty cell.
        row = []
        for lookup in self.fields:
            value = obj_data
            for part in lookup.split('__'):
                value = value.get(part) if isinstance(value, dict) else None
            if isinstance(value, dict):
                # an fk selected alongside a related lookup through it nests,
                # so it has no scalar of its own.
                value = None
            row.append(value)
        return row

    def csv_response(self, filename='export.csv'):
        def generate():
            buf = io.StringIO()
            writer = csv.writer(buf)

            def emit(row):
                writer.writerow(row)
                data = buf.getvalue()
                buf.seek(0)
                buf.truncate()
                return data.encode('utf-8')

            yield emit(self.fields)
            for obj_data in self.rows():
                yield emit(self.flatten_object(obj_data))
        return self._response(generate, filename, 'text/csv')
