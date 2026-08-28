
import datetime
try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse

from flask import g
from flask import get_flashed_messages
from flask import request
from flask import session
from flask import url_for

from peewee import BooleanField
from peewee import CharField

from flask_peewee.auth import Auth
from flask_peewee.auth import BaseUser
from flask_peewee.auth import LoginForm
from flask_peewee.exceptions import ImproperlyConfigured
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User
from flask_peewee.tests.test_app import app
from flask_peewee.tests.test_app import auth
from flask_peewee.tests.test_app import db


class TestAuth(Auth):
    def setup(self):
        pass


class RoutesOnlyAuth(Auth):
    # the shared app already has auth's handlers and context processors, so
    # only the routes are needed.
    def setup(self):
        self.configure_routes()
        self.register_blueprint()


class ResetAuth(RoutesOnlyAuth):
    def send_reset_email(self, user, reset_url):
        self.sent.append((user, reset_url))


reset_auth = ResetAuth(app, db, user_model=User, prefix='/reset-accounts',
                       name='reset_auth', reset=True)


class TokenUser(db.Model, BaseUser):
    username = CharField()
    password = CharField()
    email = CharField(default='')
    active = BooleanField(default=True)
    admin = BooleanField(default=False)
    session_token = CharField(default='')


token_auth = RoutesOnlyAuth(app, db, user_model=TokenUser,
                            prefix='/token-accounts', name='token_auth',
                            session_field='session_token')


class AuthTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(AuthTestCase, self).setUp()

        self.test_auth = TestAuth(app, db)
        reset_auth.sent = []
        db.database.create_tables([TokenUser])

    def tearDown(self):
        db.database.drop_tables([TokenUser])
        super(AuthTestCase, self).tearDown()

    def create_token_user(self):
        user = TokenUser(username='huey')
        user.set_password('meow')
        user.save()
        return user

    def assertNotLoggedIn(self, auth):
        g.user = None
        self.assertIsNone(auth.get_logged_in_user())

    def assertLoggedIn(self, auth, user):
        g.user = None
        self.assertEqual(auth.get_logged_in_user(), user)

    def test_session_field_required(self):
        self.assertRaises(ImproperlyConfigured, TestAuth, app, db,
                          user_model=User, session_field='session_token')

    def test_session_field_default_model(self):
        fake_auth = TestAuth(app, db, db_table='token_users',
                             session_field='session_token')
        self.assertIn('session_token', fake_auth.User._meta.fields)

    def test_session_token(self):
        user = self.create_token_user()
        self.assertEqual(user.session_token, '')

        with self.flask_app.test_request_context():
            token_auth.login_user(user)
            token = session['session_token']
            self.assertTrue(token)
            self.assertEqual(TokenUser.get_by_id(user.id).session_token, token)
            self.assertLoggedIn(token_auth, user)

            # Logging in again reuses the token.
            token_auth.login_user(user)
            self.assertEqual(session['session_token'], token)

            # A cookie carrying a stale token is not logged in.
            session['session_token'] = 'x' * 32
            self.assertNotLoggedIn(token_auth)
            session['session_token'] = token
            self.assertLoggedIn(token_auth, user)

            # Revoking on the row ends the session.
            token_auth.revoke_session_token(user)
            self.assertNotLoggedIn(token_auth)

    def test_session_token_logout(self):
        user = self.create_token_user()
        with self.flask_app.test_request_context():
            token_auth.login_user(user)
            token = session['session_token']

        def other_session():
            ctx = self.flask_app.test_request_context()
            ctx.push()
            session.update(logged_in=True, user_pk=user.id,
                           session_token=token)
            return ctx

        ctx = other_session()
        self.assertLoggedIn(token_auth, user)
        token_auth.logout_user()
        self.assertNotIn('session_token', session)
        self.assertNotIn('logged_in', session)
        self.assertEqual(TokenUser.get_by_id(user.id).session_token, '')
        ctx.pop()

        # Logout cleared the row, so a second session with the same token is
        # ended too.
        ctx = other_session()
        self.assertNotLoggedIn(token_auth)
        ctx.pop()

    def login(self, username='admin', password='admin', context=None):
        context = context or self.app
        return context.post('/accounts/login/', data={
            'username': username,
            'password': password,
        })

    def logout(self, context=None):
        context = context or self.app
        return context.post('/accounts/logout/')

    def assertRedirect(self, resp):
        self.assertTrue(resp.status_code in (302, 303))

    def assertResetRejected(self, token):
        with self.flask_app.test_client() as c:
            resp = c.get('/reset-accounts/reset/%s/' % token)
            self.assertRedirect(resp)
            self.assertTrue(
                resp.headers['location'].endswith('/reset-accounts/forgot/'))
            self.assertEqual(get_flashed_messages(), [
                'The password reset link is invalid or has expired'])

    def test_table(self):
        self.assertEqual(self.test_auth.User._meta.table_name, 'user')

        fake_auth = TestAuth(app, db, db_table='peewee_users')
        self.assertEqual(fake_auth.User._meta.table_name, 'peewee_users')

    def test_login_view(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.get('/accounts/login/')
            self.assertEqual(resp.status_code, 200)

            # check that we have no logged-in user
            self.assertContext('user', None)

            frm = self.get_context('form')
            self.assertTrue(isinstance(frm, LoginForm))
            self.assertEqual(frm.data, {'username': None, 'password': None})

            # make a post missing the username
            resp = c.post('/accounts/login/', data={
                'username': '',
                'password': 'xxx',
            })
            self.assertEqual(resp.status_code, 200)

            # check form for errors
            frm = self.get_context('form')
            self.assertEqual(frm.errors, {'username': ['This field is required.']})

            # check that no messages were generated
            self.assertFalse('_flashes' in session)

            # check that the auth API does not indicate a logged-in user
            self.assertEqual(auth.get_logged_in_user(), None)

            # make a post with a bad username/password combo
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'baz',
            })
            self.assertEqual(resp.status_code, 200)

            # both fields were present so no form errors, but flash the user
            # indicating bad username/password combo
            self.assertTrue('_flashes' in session)
            messages = get_flashed_messages()

            self.assertEqual(messages, [
                'Incorrect username or password',
            ])

            # check that the auth API does not indicate a logged-in user
            self.assertEqual(auth.get_logged_in_user(), None)

            # make a post with an inactive user
            resp = c.post('/accounts/login/', data={
                'username': 'inactive',
                'password': 'inactive',
            })
            self.assertEqual(resp.status_code, 200)

            # still no logged-in user
            self.assertContext('user', None)

            # check that the auth API does not indicate a logged-in user
            self.assertEqual(auth.get_logged_in_user(), None)

            # finally post as a known good user
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
            })
            self.assertRedirect(resp)

            # check that we now have a logged-in user
            self.assertEqual(auth.get_logged_in_user(), self.normal)

    def test_login_redirect_in_depth(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.get('/admin/')
            location = resp.location
            parsed = urlparse.urlparse(location)
            querystring = urlparse.parse_qs(parsed.query)
            self.assertEqual(querystring, {'next': ['/admin/']})

            # Following the redirect, the next url is passed to context.
            location = location.replace('http://localhost', '')
            resp = c.get(location)
            self.assertEqual(self.get_context('next'), '/admin/')

            # Simulate incorrect password.
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'incorrect-password',
                'next': '/admin/',
            })
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(self.get_context('next'), '/admin/')

            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
                'next': '/admin/',
            })
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith('/admin/'))

    def test_login_default_redirect(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
            })
            self.assertRedirect(resp)
            location = resp.location.replace('http://localhost', '')
            self.assertTrue(location, '/')

    def test_login_redirect(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
                'next': '/foo-baz/',
            })
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith('/foo-baz/'))

    def test_login_open_redirect_blocked(self):
        self.create_users()

        for bad in ('http://evil.com/', '//evil.com/', 'https://evil.com'):
            with self.flask_app.test_client() as c:
                resp = c.post('/accounts/login/', data={
                    'username': 'normal',
                    'password': 'normal',
                    'next': bad,
                })
                self.assertRedirect(resp)
                location = resp.location.replace('http://localhost', '')
                self.assertEqual(location, '/')

    def test_logout_open_redirect_blocked(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            c.post('/accounts/login/', data={
                'username': 'normal', 'password': 'normal'})
            resp = c.get('/accounts/logout/?next=//evil.com/')
            self.assertRedirect(resp)
            location = resp.location.replace('http://localhost', '')
            self.assertEqual(location, '/')

    def test_login_logout(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
            })
            self.assertEqual(auth.get_logged_in_user(), self.normal)

            resp = c.post('/accounts/logout/')
            self.assertEqual(auth.get_logged_in_user(), None)

            resp = c.post('/accounts/login/', data={
                'username': 'admin',
                'password': 'admin',
            })
            self.assertEqual(auth.get_logged_in_user(), self.admin)

            # log back in without logging out
            resp = c.post('/accounts/login/', data={
                'username': 'normal',
                'password': 'normal',
            })
            self.assertEqual(auth.get_logged_in_user(), self.normal)

    def test_login_required(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.get('/private/')
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith((
                '/accounts/login/?next=%2Fprivate%2F',
                '/accounts/login/?next=/private/')))

            self.login('normal', 'normal', c)

            resp = c.get('/private/')
            self.assertEqual(resp.status_code, 200)

            self.assertEqual(auth.get_logged_in_user(), self.normal)

            self.login('admin', 'admin', c)

            resp = c.get('/private/')
            self.assertEqual(resp.status_code, 200)

            self.assertEqual(auth.get_logged_in_user(), self.admin)

    def test_admin_required(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            resp = c.get('/secret/')
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith((
                '/accounts/login/?next=%2Fsecret%2F',
                '/accounts/login/?next=/secret/')))

            self.login('normal', 'normal', c)

            resp = c.get('/secret/')
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith((
                '/accounts/login/?next=%2Fsecret%2F',
                '/accounts/login/?next=/secret/')))
            self.assertEqual(auth.get_logged_in_user(), self.normal)

            self.login('admin', 'admin', c)
            resp = c.get('/secret/')
            self.assertEqual(resp.status_code, 200)

            self.assertEqual(auth.get_logged_in_user(), self.admin)

    def test_reset_flow(self):
        user = self.create_user('huey', 'meow', email='huey@example.com')

        with self.flask_app.test_client() as c:
            resp = c.get('/reset-accounts/forgot/')
            self.assertEqual(resp.status_code, 200)

            resp = c.post('/reset-accounts/forgot/', data={
                'email': 'huey@example.com'})
            self.assertRedirect(resp)
            self.assertEqual(get_flashed_messages(), [
                'If the email address matches an account, a password reset '
                'link has been sent'])

            self.assertEqual(len(reset_auth.sent), 1)
            sent_user, reset_url = reset_auth.sent[0]
            self.assertEqual(sent_user, user)

            reset_path = reset_url.replace('http://localhost', '')
            self.assertTrue(reset_path.startswith('/reset-accounts/reset/'))

            resp = c.get(reset_path)
            self.assertEqual(resp.status_code, 200)

            # mismatched confirmation re-renders with an error.
            resp = c.post(reset_path, data={
                'password': 'purr', 'confirm': 'nope'})
            self.assertEqual(resp.status_code, 200)
            frm = self.get_context('form')
            self.assertEqual(frm.errors, {'confirm': ['Passwords must match']})

            resp = c.post(reset_path, data={
                'password': 'purr', 'confirm': 'purr'})
            self.assertRedirect(resp)
            self.assertTrue(
                resp.headers['location'].endswith('/reset-accounts/login/'))

        user = User.get(User.id == user.id)
        self.assertTrue(user.check_password('purr'))
        self.assertFalse(user.check_password('meow'))

        # the new password works through the regular login view.
        with self.flask_app.test_client() as c:
            resp = c.post('/accounts/login/', data={
                'username': 'huey', 'password': 'purr'})
            self.assertRedirect(resp)
            self.assertEqual(auth.get_logged_in_user(), user)

    def test_reset_token_password_change(self):
        user = self.create_user('huey', 'meow', email='huey@example.com')
        token = reset_auth.make_reset_token(user)
        self.assertEqual(reset_auth.parse_reset_token(token), user)

        user.set_password('changed')
        user.save()
        self.assertEqual(reset_auth.parse_reset_token(token), None)
        self.assertResetRejected(token)

    def test_reset_token_expired(self):
        user = self.create_user('huey', 'meow', email='huey@example.com')
        token = reset_auth.make_reset_token(user)

        reset_auth.reset_token_max_age = -1
        self.addCleanup(delattr, reset_auth, 'reset_token_max_age')
        self.assertEqual(reset_auth.parse_reset_token(token), None)
        self.assertResetRejected(token)

    def test_reset_token_garbage(self):
        self.assertEqual(reset_auth.parse_reset_token('garbage'), None)
        self.assertResetRejected('garbage')

    def test_forgot_unknown_email(self):
        self.create_user('huey', 'meow', email='huey@example.com')

        with self.flask_app.test_client() as c:
            resp = c.post('/reset-accounts/forgot/', data={
                'email': 'huey@example.com'})
            self.assertRedirect(resp)
            known = get_flashed_messages()

        with self.flask_app.test_client() as c:
            resp = c.post('/reset-accounts/forgot/', data={
                'email': 'nobody@example.com'})
            self.assertRedirect(resp)
            self.assertEqual(get_flashed_messages(), known)

        # only the known email produced a send.
        self.assertEqual(len(reset_auth.sent), 1)

    def test_reset_disabled_by_default(self):
        self.assertEqual(len(auth.get_urls()), 2)
        self.assertEqual(len(self.test_auth.get_urls()), 2)

        with self.flask_app.test_client() as c:
            self.assertEqual(c.get('/accounts/forgot/').status_code, 404)
            self.assertEqual(c.get('/accounts/reset/xyz/').status_code, 404)
