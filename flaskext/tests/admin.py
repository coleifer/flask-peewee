from hashlib import sha1
import datetime

from flask import request, session, url_for

from flaskext.admin import ModelAdmin, AdminPanel
from flaskext.tests.base import FlaskPeeweeTestCase
from flaskext.tests.test_app import User, Message, Note, admin


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
