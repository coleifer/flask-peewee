import functools
import os

from flask import Blueprint
from flask import abort
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from peewee import *
from wtforms import Form
from wtforms import PasswordField
from wtforms import TextField
from wtforms import validators

from flask_peewee.utils import check_password
from flask_peewee.utils import get_next
from flask_peewee.utils import make_password


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
    def __init__(self, app, db, user_model=None, prefix='/accounts', name='auth',
                 clear_session=False, default_next_url='/', db_table='user'):
        self.app = app
        self.db = db

        self.db_table = db_table
        self.User = user_model or self.get_user_model()

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix

        self.clear_session = clear_session
        self.default_next_url = default_next_url

        self.setup()

    def get_context_user(self):
        return {'user': self.get_logged_in_user()}

    def get_user_model(self):
        class User(self.db.Model, BaseUser):
            username = CharField(unique=True)
            password = CharField()
            email = CharField(unique=True)
            active = BooleanField()
            admin = BooleanField(default=False)

            def __unicode__(self):
                return self.username

            class Meta:
                table_name = self.db_table

        return User

    def get_model_admin(self, model_admin=None):
        if model_admin is None:
            from flask_peewee.admin import ModelAdmin
            model_admin = ModelAdmin

        class UserAdmin(model_admin):
            columns = getattr(model_admin, 'columns') or (
                    ['username', 'email', 'active', 'admin'])

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

    def test_user(self, test_fn):
        def decorator(fn):
            @functools.wraps(fn)
            def inner(*args, **kwargs):
                user = self.get_logged_in_user()

                if not user or not test_fn(user):
                    login_url = url_for('%s.login' % self.blueprint.name, next=get_next())
                    return redirect(login_url)
                return fn(*args, **kwargs)
            return inner
        return decorator

    def login_required(self, func):
        return self.test_user(lambda u: True)(func)

    def admin_required(self, func):
        return self.test_user(lambda u: u.admin)(func)

    def authenticate(self, username, password):
        active = self.User.select().where(self.User.active==True)
        try:
            user = active.where(self.User.username==username).get()
        except self.User.DoesNotExist:
            return False
        else:
            if not user.check_password(password):
                return False

        return user

    def login_user(self, user):
        session['logged_in'] = True
        session['user_pk'] = user._pk
        session.permanent = True
        g.user = user
        flash('You are logged in as %s' % user, 'success')

    def logout_user(self):
        if self.clear_session:
            session.clear()
        else:
            session.pop('logged_in', None)
        g.user = None
        flash('You are now logged out', 'success')

    def get_logged_in_user(self):
        if session.get('logged_in'):
            if getattr(g, 'user', None):
                return g.user

            try:
                return self.User.select().where(
                    self.User.active==True,
                    self.User.id==session.get('user_pk')
                ).get()
            except self.User.DoesNotExist:
                pass

    def login(self):
        error = None
        Form = self.get_login_form()

        if request.method == 'POST':
            form = Form(request.form)
            next_url = request.form.get('next') or self.default_next_url
            if form.validate():
                authenticated_user = self.authenticate(
                    form.username.data,
                    form.password.data,
                )
                if authenticated_user:
                    self.login_user(authenticated_user)
                    return redirect(next_url)
                else:
                    flash('Incorrect username or password')
        else:
            form = Form()
            next_url = request.args.get('next')

        return render_template(
            'auth/login.html',
            error=error,
            form=form,
            login_url=url_for('%s.login' % self.blueprint.name),
            next=next_url)

    def logout(self):
        self.logout_user()
        return redirect(request.args.get('next') or self.default_next_url)

    def configure_routes(self):
        for url, callback in self.get_urls():
            self.blueprint.route(url, methods=['GET', 'POST'])(callback)

    def register_blueprint(self, **kwargs):
        self.app.register_blueprint(self.blueprint, url_prefix=self.url_prefix, **kwargs)

    def load_user(self):
        g.user = self.get_logged_in_user()

    def register_handlers(self):
        self.app.before_request_funcs.setdefault(None, [])
        self.app.before_request_funcs[None].append(self.load_user)

    def register_context_processors(self):
        self.app.template_context_processors[None].append(self.get_context_user)

    def setup(self):
        self.configure_routes()
        self.register_blueprint()
        self.register_handlers()
        self.register_context_processors()
