import functools
import hashlib
import os
import secrets

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from itsdangerous import BadData
from itsdangerous import URLSafeTimedSerializer
from peewee import *
from wtforms import Form
from wtforms import PasswordField
from wtforms.fields import StringField

from flask_peewee.exceptions import ImproperlyConfigured
from flask_peewee.utils import check_password
from flask_peewee.utils import get_next
from flask_peewee.utils import is_legacy_password
from flask_peewee.utils import is_safe_url
from flask_peewee.utils import make_password
from wtforms.validators import DataRequired
from wtforms.validators import EqualTo


current_dir = os.path.dirname(__file__)



class LoginForm(Form):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class ForgotPasswordForm(Form):
    email = StringField('Email', validators=[DataRequired()])


class ResetPasswordForm(Form):
    password = PasswordField('New password', validators=[DataRequired()])
    confirm = PasswordField('Confirm password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match')])


class BaseUser(object):
    def set_password(self, password):
        self.password = make_password(password)

    def check_password(self, password):
        return check_password(password, self.password)


class Auth(object):
    reset_token_max_age = 3600

    def __init__(self, app, db, user_model=None, prefix='/accounts', name='auth',
                 clear_session=False, default_next_url='/', db_table='user',
                 reset=False, session_field=None):
        self.app = app
        self.db = db

        self.db_table = db_table
        self.session_field = session_field
        self.User = user_model or self.get_user_model()
        if session_field and session_field not in self.User._meta.fields:
            raise ImproperlyConfigured(
                '%s has no field "%s" to hold the session token.' %
                (self.User.__name__, session_field))

        self.blueprint = self.get_blueprint(name)
        self.url_prefix = prefix

        self.clear_session = clear_session
        self.default_next_url = default_next_url
        self.reset_enabled = reset

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

            def __str__(self):
                return self.username

            class Meta:
                table_name = self.db_table

        if self.session_field:
            User._meta.add_field(self.session_field, CharField(default=''))
        return User

    def get_model_admin(self, model_admin=None):
        if model_admin is None:
            from flask_peewee.admin import ModelAdmin
            model_admin = ModelAdmin

        # always exclude credentials from export, in addition to whatever the
        # caller excludes.
        excluded = list(model_admin.export_exclude or ())
        excluded.extend(f for f in ('password', self.session_field)
                        if f and f not in excluded)

        class UserAdmin(model_admin):
            columns = getattr(model_admin, 'columns') or (
                    ['username', 'email', 'active', 'admin'])

            export_exclude = tuple(excluded)

            def save_model(self, instance, form, adding=False):
                orig_password = instance.password
                form.populate_obj(instance)

                # hash before the single save so the raw password is never
                # written to the database. the old order let super() save the
                # plaintext first, then overwrote it with the hash on a second
                # save.
                if form.password.data != orig_password:
                    instance.set_password(form.password.data)

                instance.save(force_insert=adding)
                return instance


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
        urls = (
            ('/logout/', self.logout),
            ('/login/', self.login),
        )
        if self.reset_enabled:
            urls += (
                ('/forgot/', self.forgot),
                ('/reset/<token>/', self.reset),
            )
        return urls

    def get_login_form(self):
        return LoginForm

    def get_forgot_form(self):
        return ForgotPasswordForm

    def get_reset_form(self):
        return ResetPasswordForm

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

        # transparently upgrade legacy password hashes on successful login.
        if is_legacy_password(user.password):
            user.set_password(password)
            user.save()

        return user

    def get_reset_serializer(self):
        return URLSafeTimedSerializer(self.app.config['SECRET_KEY'],
                                      salt='flask-peewee.reset')

    def reset_fingerprint(self, user):
        # binds the token to the current hash, so changing the password
        # invalidates outstanding tokens.
        return hashlib.sha256(user.password.encode('utf-8')).hexdigest()[:12]

    def make_reset_token(self, user):
        return self.get_reset_serializer().dumps(
            [user._pk, self.reset_fingerprint(user)])

    def parse_reset_token(self, token):
        try:
            pk, fingerprint = self.get_reset_serializer().loads(
                token, max_age=self.reset_token_max_age)
        except (BadData, TypeError, ValueError):
            # BadData covers tampered and expired tokens, the others a
            # validly-signed payload of an unexpected shape.
            return None
        user = self.User.get_or_none(
            self.User.active==True,
            self.User._meta.primary_key==pk)
        if user is None or fingerprint != self.reset_fingerprint(user):
            return None
        return user

    def get_reset_user(self, form):
        return self.User.get_or_none(
            self.User.active==True,
            self.User.email==form.email.data)

    def send_reset_email(self, user, reset_url):
        raise NotImplementedError('Applications enabling password reset '
                                  'must override send_reset_email().')

    def get_session_token(self, user):
        # Generated on first login and reused after, so all of a user's sessions
        # share one token. Clearing the field on the row ends every one.
        token = getattr(user, self.session_field)
        if not token:
            token = secrets.token_hex(16)
            setattr(user, self.session_field, token)
            user.save(only=[getattr(self.User, self.session_field)])
        return token

    def revoke_session_token(self, user):
        setattr(user, self.session_field, '')
        user.save(only=[getattr(self.User, self.session_field)])

    def login_user(self, user):
        session['logged_in'] = True
        session['user_pk'] = user._pk
        if self.session_field:
            session['session_token'] = self.get_session_token(user)
        session.permanent = True
        g.user = user
        flash('You are logged in as %s' % user, 'success')

    def logout_user(self):
        if self.session_field:
            user = self.get_logged_in_user()
            if user is not None:
                self.revoke_session_token(user)
        if self.clear_session:
            session.clear()
        else:
            session.pop('logged_in', None)
            session.pop('session_token', None)
        g.user = None
        flash('You are now logged out', 'success')

    def get_logged_in_user(self):
        if not session.get('logged_in'):
            return

        if getattr(g, 'user', None):
            return g.user

        try:
            user = self.User.select().where(
                self.User.active==True,
                self.User._meta.primary_key==session.get('user_pk')
            ).get()
        except self.User.DoesNotExist:
            return

        if self.session_field:
            token = session.get('session_token')
            if not token or token != getattr(user, self.session_field):
                return
        return user

    def login(self):
        error = None
        Form = self.get_login_form()

        if request.method == 'POST':
            form = Form(request.form)
            next_url = request.form.get('next')
            if not is_safe_url(next_url):
                next_url = self.default_next_url
            if form.validate():
                authenticated_user = self.authenticate(
                    form.username.data,
                    form.password.data,
                )
                if authenticated_user:
                    self.login_user(authenticated_user)
                    return redirect(next_url)
                else:
                    flash('Incorrect username or password', 'danger')
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
        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            next_url = self.default_next_url
        return redirect(next_url)

    def forgot(self):
        Form = self.get_forgot_form()

        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                user = self.get_reset_user(form)
                if user is not None:
                    reset_url = url_for(
                        '%s.reset' % self.blueprint.name,
                        token=self.make_reset_token(user),
                        _external=True)
                    self.send_reset_email(user, reset_url)

                # identical response whether or not a user matched, to avoid
                # leaking which emails have accounts.
                flash('If the email address matches an account, a password '
                      'reset link has been sent', 'success')
                return redirect(url_for('%s.login' % self.blueprint.name))
        else:
            form = Form()

        return render_template(
            'auth/forgot.html',
            form=form,
            forgot_url=url_for('%s.forgot' % self.blueprint.name))

    def reset(self, token):
        user = self.parse_reset_token(token)
        if user is None:
            flash('The password reset link is invalid or has expired', 'danger')
            return redirect(url_for('%s.forgot' % self.blueprint.name))

        Form = self.get_reset_form()

        if request.method == 'POST':
            form = Form(request.form)
            if form.validate():
                user.set_password(form.password.data)
                user.save()
                flash('Your password has been reset, please log in', 'success')
                return redirect(url_for('%s.login' % self.blueprint.name))
        else:
            form = Form()

        return render_template(
            'auth/reset.html',
            form=form,
            reset_url=url_for('%s.reset' % self.blueprint.name, token=token))

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
        self.app.extensions.setdefault('flask_peewee', {})['auth'] = self
        self.configure_routes()
        self.register_blueprint()
        self.register_handlers()
        self.register_context_processors()
