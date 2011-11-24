try:
    import simplejson as json
except ImportError:
    import json

import datetime

from flask import request
from werkzeug.exceptions import NotFound

from flask_peewee.utils import get_object_or_404, make_password, check_password
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User, Message, Note, app as flask_app


class UtilsTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(UtilsTestCase, self).setUp()
    
    def test_get_object_or_404(self):
        user = self.create_user('test', 'test')
        
        # test with model as first arg
        self.assertRaises(NotFound, get_object_or_404, User, username='not-here')
        self.assertEqual(user, get_object_or_404(User, username='test'))
        
        # test with query as first arg
        active = User.select().where(active=True)
        inactive = User.select().where(active=False)
        self.assertRaises(NotFound, get_object_or_404, active, username='not-here')
        self.assertRaises(NotFound, get_object_or_404, inactive, username='test')
        self.assertEqual(user, get_object_or_404(active, username='test'))
    
    def test_passwords(self):
        p = make_password('testing')
        self.assertTrue(check_password('testing', p))
        self.assertFalse(check_password('testing ', p))
        self.assertFalse(check_password('Testing', p))
        self.assertFalse(check_password('', p))
        
        p2 = make_password('Testing')
        self.assertFalse(p == p2)
