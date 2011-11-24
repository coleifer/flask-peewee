import functools
import os

from flask import Blueprint, render_template, abort, request, session, flash, redirect, url_for, g
from peewee import *
from wtforms import Form, TextField, PasswordField, validators

from flask_peewee.utils import get_next, make_password, check_password


current_dir = os.path.dirname(__file__)



class LoginForm(Form):
    username = TextField('Username', validators=[validators.Required()])
    password = PasswordField('Password', validators=[validators.Required()])


class BaseUser(object):
    def set_password(self, password):
        self.password = make_password(password)

    def check_password(self, password):
        return check_password(password, self.password)


class Auth(object):
    default_next_url = 'homepage'
    
    def __init__(self, app, db, user_model=None, prefix='/accounts', name='auth'):
        self.app = app
        self.db = db
        
        self.User = user_model or self.get_user_model()
        
        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix
        
        self.setup()
    
    def get_context_user(self):
        return {'user': self.get_logged_in_user()}
    
    def get_user_model(self):
        class User(self.db.Model, BaseUser):
            username = CharField()
            password = CharField()
            email = CharField()
            active = BooleanField()
            admin = BooleanField()
            
            def __unicode__(self):
                return self.username
        
        return User
    
    def get_model_admin(self, model_admin=None):
        if model_admin is None:
            from flask_peewee.admin import ModelAdmin
            model_admin = ModelAdmin
        
        class UserAdmin(model_admin):
            columns = ['username', 'email', 'active', 'admin']
            
            def save_model(self, instance, form, adding=False):
                orig_password = instance.password
                
                user = super(UserAdmin, self).save_model(instance, form, adding)
                
                if orig_password != form.password.data:
                    user.set_password(form.password.data)
                    user.save()
                
                return user
                
        
        return UserAdmin
    
    def register_admin(self, admin_site, model_admin=None):
        admin_site.register(self.User, self.get_model_admin(model_admin))
    
    def get_blueprint(self, blueprint_name):
        return Blueprint(
            blueprint_name,
            __name__,
            static_folder=os.path.join(current_dir, 'static'),
            template_folder=os.path.join(current_dir, 'templates'),
        )
    
    def get_urls(self):
        return (
            ('/logout/', self.logout),
            ('/login/', self.login),
        )
    
    def get_login_form(self):
        return LoginForm
    
    def login_required(self, func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            user = self.get_logged_in_user()
            
            if not user:
                login_url = url_for('%s.login' % self.blueprint.name, next=get_next())
                return redirect(login_url)
            
            return func(*args, **kwargs)
        return inner
    
    def authenticate(self, username, password):
        active = self.User.select().where(active=True)
        try:
            user = active.get(
                username=username,
            )
        except self.User.DoesNotExist:
            return False
        else:
            if not user.check_password(password):
                return False
        
        return user
    
    def login_user(self, user):
        session['logged_in'] = True
        session['user_pk'] = user.get_pk()
        session.permanent = True
        g.user = user
        flash('You are logged in as %s' % user.username, 'success')
    
    def logout_user(self, user):
        session.pop('logged_in', None)
        g.user = None
        flash('You are now logged out', 'success')
    
    def get_logged_in_user(self):
        if session.get('logged_in'):
            if getattr(g, 'user', None):
                return g.user
            
            try:
                return self.User.select().where(active=True).get(id=session.get('user_pk'))
            except self.User.DoesNotExist:
                pass
    
    def login(self):
        error = None
        Form = self.get_login_form()
        
        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                authenticated_user = self.authenticate(
                    form.username.data,
                    form.password.data,
                )
                if authenticated_user:
                    self.login_user(authenticated_user)
                    return redirect(
                        request.args.get('next') or \
                        url_for(self.default_next_url)
                    )
                else:
                    flash('Incorrect username or password')
        else:
            form = Form()
        
        return render_template('auth/login.html', error=error, form=form)

    def logout(self):
        self.logout_user(self.get_logged_in_user())
        return redirect(
            request.args.get('next') or \
            url_for(self.default_next_url)
        )
    
    def configure_routes(self):
        for url, callback in self.get_urls():
            self.blueprint.route(url, methods=['GET', 'POST'])(callback)
    
    def register_blueprint(self, **kwargs):
        self.app.register_blueprint(self.blueprint, url_prefix=self.url_prefix, **kwargs)
    
    def load_user(self):
        g.user = self.get_logged_in_user()
    
    def register_handlers(self):
        self.app.before_request(self.load_user)
    
    def register_context_processors(self):
        self.app.template_context_processors[None].append(self.get_context_user)
    
    def setup(self):
        self.configure_routes()
        self.register_blueprint()
        self.register_handlers()
        self.register_context_processors()
