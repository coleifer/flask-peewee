from __future__ import with_statement

import datetime

from flask import request, session, url_for, get_flashed_messages

from flask_peewee.auth import Auth, LoginForm
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User, app, db, auth


class TestAuth(Auth):
    def setup(self):
        pass


class AuthTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(AuthTestCase, self).setUp()
        
        self.test_auth = TestAuth(app, db)
    
    def login(self, username='admin', password='admin', context=None):
        context = context or self.app
        return context.post('/accounts/login/', data={
            'username': username,
            'password': password,
        })
    
    def logout(self, context=None):
        context = context or self.app
        return context.post('/accounts/logout/')
    
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
            self.assertEqual(frm.errors, {'username': [u'This field is required.']})
            
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
            self.assertEqual(resp.status_code, 302)
            
            # check that we now have a logged-in user
            self.assertEqual(auth.get_logged_in_user(), self.normal)
    
    def test_login_redirect(self):
        self.create_users()
        
        with self.flask_app.test_client() as c:
            resp = c.post('/accounts/login/?next=/foo-baz/', data={
                'username': 'normal',
                'password': 'normal',
            })
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp.headers['location'].endswith('/foo-baz/'))
    
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
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp.headers['location'].endswith('/accounts/login/?next=%2Fprivate%2F'))
            
            self.login('normal', 'normal', c)
            
            resp = c.get('/private/')
            self.assertEqual(resp.status_code, 200)

            self.assertEqual(auth.get_logged_in_user(), self.normal)
            
            self.login('admin', 'admin', c)
            
            resp = c.get('/private/')
            self.assertEqual(resp.status_code, 200)
            
            self.assertEqual(auth.get_logged_in_user(), self.admin)
