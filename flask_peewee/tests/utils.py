try:
    import simplejson as json
except ImportError:
    import json

import datetime

from flask import request
from werkzeug.exceptions import NotFound

from flask_peewee.utils import check_password
from flask_peewee.utils import get_object_or_404
from flask_peewee.utils import make_password
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import User
from flask_peewee.tests.test_app import app as flask_app


class UtilsTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(UtilsTestCase, self).setUp()

    def test_get_object_or_404(self):
        user = self.create_user('test', 'test')

        # test with model as first arg
        self.assertRaises(NotFound, get_object_or_404, User, User.username=='not-here')
        self.assertEqual(user, get_object_or_404(User, User.username=='test'))

        # test with query as first arg
        active = User.select().where(User.active==True)
        inactive = User.select().where(User.active==False)
        self.assertRaises(NotFound, get_object_or_404, active, User.username=='not-here')
        self.assertRaises(NotFound, get_object_or_404, inactive, User.username=='test')
        self.assertEqual(user, get_object_or_404(active, User.username=='test'))

    def test_passwords(self):
        p = make_password('testing')
        self.assertTrue(check_password('testing', p))
        self.assertFalse(check_password('testing ', p))
        self.assertFalse(check_password('Testing', p))
        self.assertFalse(check_password('', p))

        p2 = make_password('Testing')
        self.assertFalse(p == p2)
