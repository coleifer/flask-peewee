from hashlib import sha1
import datetime

from flask import request, session, url_for

from flaskext.admin import ModelAdmin, AdminPanel
from flaskext.tests.base import FlaskPeeweeTestCase
from flaskext.tests.test_app import User, Message, Note, admin

from wtfpeewee.orm import model_form


class AdminTestCase(FlaskPeeweeTestCase):
    def login(self):
        self.app.post('/accounts/login/', data={
            'username': 'admin',
            'password': 'admin',
        })
    
    def logout(self):
        self.app.post('/accounts/logout/')
    
    def test_admin_auth(self):
        self.create_users()
        
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['location'], 'http://localhost/accounts/login/?next=%2Fadmin%2F')
        
        resp = self.app.post('/accounts/login/?next=%2Fadmin%2F', data={
            'username': 'normal',
            'password': 'normal',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['location'], 'http://localhost/admin/')
        
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 403)
        
        resp = self.app.get('/accounts/logout/')
        
        resp = self.app.post('/accounts/login/?next=%2Fadmin%2F', data={
            'username': 'admin',
            'password': 'admin',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['location'], 'http://localhost/admin/')
        
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 200)
    
    def test_url_resolution(self):
        # need to be in a 'request' context to use ``url_for``
        with self.flask_app.test_request_context('/'):
            # admin urls
            self.assertEqual(url_for('admin.index'), '/admin/')
            
            # modeladmin urls
            self.assertEqual(url_for('admin.user_index'), '/admin/user/')
            self.assertEqual(url_for('admin.user_add'), '/admin/user/add/')
            self.assertEqual(url_for('admin.user_edit', pk=1), '/admin/user/1/')
            self.assertEqual(url_for('admin.user_delete'), '/admin/user/delete/')
            
            # panel urls
            self.assertEqual(url_for('admin.panel_notes_create'), '/admin/notes/create/')
    
    def test_index_view(self):
        self.create_users()
        self.login()
        
        # check for context in the index view
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        
        self.assertContext('user', self.admin)
        self.assertContext('model_admins', [
            admin._registry['message'],
            admin._registry['note'],
            admin._registry['user'],
        ])
        self.assertContext('panels', [
            admin._panels['Notes'],
        ])


class TemplateHelperTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(TemplateHelperTestCase, self).setUp()
        self.create_users()
        self.create_message(self.admin, 'admin message')
        self.create_message(self.admin, 'admin message 2')
        self.create_message(self.normal, 'normal message')
        
        self.th = admin.template_helper
    
    def test_get_model_field(self):
        self.assertEqual(self.th.get_model_field(self.admin, 'username'), 'admin')
        self.assertEqual(self.th.get_model_field(self.admin, 'message_count'), 2)
        self.assertRaises(AttributeError, self.th.get_model_field, self.admin, 'missing_attr')
    
    def test_get_form_field(self):
        form = model_form(User)(obj=self.admin)
        self.assertEqual(self.th.get_form_field(form, 'username'), form.username)
        self.assertEqual(self.th.get_form_field(form, 'username').data, 'admin')
    
    def test_fix_underscores(self):
        self.assertEqual(self.th.fix_underscores('some_model'), 'Some Model')
        self.assertEqual(self.th.fix_underscores('test'), 'Test')
    
    def test_update_querystring(self):
        self.assertEqual(self.th.update_querystring('', 'page', 1), 'page=1')
        self.assertEqual(self.th.update_querystring('page=1', 'page', 2), 'page=2')
        self.assertEqual(self.th.update_querystring('session=3&page=1', 'page', 2), 'session=3&page=2')
        self.assertEqual(self.th.update_querystring('page=1&session=3', 'page', 2), 'session=3&page=2')
        self.assertEqual(self.th.update_querystring('session=3&page=1&ordering=id', 'page', 2), 'session=3&ordering=id&page=2')
        self.assertEqual(self.th.update_querystring('session=3&ordering=id', 'page', 2), 'session=3&ordering=id&page=2')
    
    def test_get_verbose_name(self):
        self.assertEqual(self.th.get_verbose_name(User, 'username'), 'Username')
        self.assertEqual(self.th.get_verbose_name(User, 'join_date'), 'Join Date')
        self.assertEqual(self.th.get_verbose_name(User, 'admin'), 'Can access admin')
        self.assertEqual(self.th.get_verbose_name(User, 'some_field'), 'Some Field')
    
    def test_get_model_admins(self):
        self.assertEqual(self.th.get_model_admins(), {'model_admins': [
            admin._registry['message'],
            admin._registry['note'],
            admin._registry['user'],
        ]})
