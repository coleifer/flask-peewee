import functools
import operator
import os
import re
try:
    import simplejson as json
except ImportError:
    import json

from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, Response
from flask_peewee.filters import BooleanSelectField, QueryFilter
from flask_peewee.serializer import Serializer
from flask_peewee.utils import get_next, PaginatedQuery, slugify
from peewee import BooleanField, ForeignKeyField, TextField, Q
from werkzeug import Headers
from wtforms import fields, widgets
from wtfpeewee.orm import model_form, ModelConverter, ModelSelectField


current_dir = os.path.dirname(__file__)


class CustomModelConverter(ModelConverter):
    def __init__(self, model_admin, additional=None):
        super(CustomModelConverter, self).__init__(additional)
        self.model_admin = model_admin
        self.converters[BooleanField] = self.handle_boolean
    
    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)
    
    def handle_foreign_key(self, model, field, **kwargs):
        if field.descriptor in (self.model_admin.raw_id_fields or ()):
            # use a different widget here
            form_field = ModelSelectField(model=field.to, **kwargs)
        else:
            form_field = ModelSelectField(model=field.to, **kwargs)
        return field.descriptor, form_field


class ModelAdmin(object):
    """
    ModelAdmin provides create/edit/delete functionality for a peewee Model.
    """
    paginate_by = 20
    columns = None
    ignore_filters = ('ordering', 'page',)
    exclude_filter_fields = None
    related_filters = []
    raw_id_fields = None
    
    def __init__(self, admin, model):
        self.admin = admin
        self.model = model
        self.pk_name = self.model._meta.pk_name
    
    def get_url_name(self, name):
        return '%s.%s_%s' % (
            self.admin.blueprint.name,
            self.get_admin_name(),
            name,
        )
    
    def get_form(self):
        return model_form(self.model, converter=CustomModelConverter(self))
    
    def get_add_form(self):
        return self.get_form()
    
    def get_edit_form(self):
        return self.get_form()
    
    def get_query(self):
        return self.model.select()
    
    def get_object(self, pk):
        return self.get_query().get(**{self.pk_name: pk})
    
    def get_query_filter(self, query):
        return QueryFilter(query,
            self.exclude_filter_fields,
            self.ignore_filters,
            self.raw_id_fields,
            self.related_filters,
        )
    
    def get_urls(self):
        return (
            ('/', self.index),
            ('/add/', self.add),
            ('/delete/', self.delete),
            ('/export/', self.export),
            ('/<pk>/', self.edit),
        )
    
    def get_columns(self):
        return self.model._meta.get_field_names()
    
    def column_is_sortable(self, col):
        return col in self.model._meta.fields
    
    def get_display_name(self):
        return self.model.__name__
    
    def get_admin_name(self):
        return slugify(self.model.__name__)
    
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
        
        return render_template('admin/models/index.html',
            model_admin=self,
            query=pq,
            ordering=ordering,
            query_filter=query_filter,
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
        
        return render_template('admin/models/add.html', model_admin=self, form=form)
    
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
        
        return render_template('admin/models/edit.html', model_admin=self, instance=instance, form=form)
    
    def delete(self):
        if request.method == 'GET':
            id_list = request.args.getlist('id')
            query = self.model.select().where(**{
                '%s__in' % self.model._meta.pk_name: id_list
            })
        elif request.method == 'POST':
            id_list = request.form.getlist('id')
            query = self.model.delete().where(**{
                '%s__in' % self.model._meta.pk_name: id_list
            })
            results = query.execute()
            flash('Successfully deleted %s %ss' % (results, self.get_display_name()), 'success')
            return redirect(url_for(self.get_url_name('index')))
        
        return render_template('admin/models/delete.html', model_admin=self, query=query)
    
    def collect_related_fields(self, model, accum, path):
        path_str = '__'.join(path)
        for field in model._meta.get_fields():
            if isinstance(field, ForeignKeyField):
                self.collect_related_fields(field.to, accum, path + [field.descriptor])
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
            export = Export(filtered_query, related, request.form.getlist('fields'))
            return export.json_response()
        
        return render_template('admin/models/export.html',
            model_admin=self,
            model=filtered_query.model,
            query=filtered_query,
            query_filter=query_filter,
            related_fields=related,
        )


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
    
    def prepare_environment(self):
        self.app.template_context_processors[None].append(self.get_model_admins)
        
        self.app.jinja_env.globals['get_model_field'] = self.get_model_field
        self.app.jinja_env.globals['get_form_field'] = self.get_form_field
        self.app.jinja_env.globals['get_verbose_name'] = self.get_verbose_name
        self.app.jinja_env.filters['fix_underscores'] = self.fix_underscores
        self.app.jinja_env.globals['update_querystring'] = self.update_querystring


class Admin(object):
    def __init__(self, app, auth, template_helper=AdminTemplateHelper,
                 prefix='/admin', name='admin'):
        self.app = app
        self.auth = auth
        
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
    
    def register(self, model, admin_class=ModelAdmin):
        model_admin = admin_class(self, model)
        admin_name = model_admin.get_admin_name()
        
        self._registry[admin_name] = model_admin
    
    def unregister(self, model):
        del(self._registry[model])
    
    def register_panel(self, title, panel):
        panel_instance = panel(self, title)
        self._panels[title] = panel_instance
    
    def unregister_panel(self, title):
        del(self._panels[title])
    
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
    
    def prepare_query(self):
        clone = self.query.clone()
        
        alias_to_model = dict([(k[1], k[0]) for k in self.related.keys()])
        select = {}
        
        def ensure_join(query, m, p):
            if m not in query._joined_models:
                if '__' not in p:
                    next_model = query.model
                else:
                    next, _ = p.rsplit('__', 1)
                    next_model = alias_to_model[next]
                    query = ensure_join(query, next_model, next)
                
                return query.switch(next_model).join(m)
            else:
                return query
        
        for field in self.fields:
            # field may be something like "content" or "user__user_name"
            if '__' in field:
                path, column = field.rsplit('__', 1)
                model = alias_to_model[path]
                clone = ensure_join(clone, model, path)
            else:
                model = self.query.model
                column = field
            
            select.setdefault(model, [])
            select[model].append((column, field))

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
                yield json.dumps(serializer.serialize_object(obj, self.fields))
                if i > 0:
                    yield ',\n'
            yield '\n]'
        headers = Headers()
        headers.add('Content-Type', 'application/javascript')
        headers.add('Content-Disposition', 'attachment; filename=export.json') 
        return Response(generate(), mimetype='text/javascript', headers=headers, direct_passthrough=True)
