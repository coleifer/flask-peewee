try:
    import simplejson as json
except ImportError:
    import json

import datetime

from flask import request
from werkzeug.exceptions import NotFound

from flaskext.utils import get_object_or_404
from flaskext.tests.base import FlaskPeeweeTestCase
from flaskext.tests.test_app import User, Message, Note, app as flask_app


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
