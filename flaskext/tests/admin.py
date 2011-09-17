from hashlib import sha1
import datetime

from flask import request, session

from flaskext.admin import ModelAdmin, AdminPanel
from flaskext.tests.base import FlaskPeeweeTestCase
from flaskext.tests.test_app import User, Message, Note


class AdminTestCase(FlaskPeeweeTestCase):
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
