import datetime
import json

from flask import request
from werkzeug.exceptions import NotFound

from flask_peewee.utils import check_password
from flask_peewee.utils import get_hexdigest
from flask_peewee.utils import get_model_from_dictionary
from flask_peewee.utils import get_object_or_404
from flask_peewee.utils import is_legacy_password
from flask_peewee.utils import is_safe_url
from flask_peewee.utils import make_password
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import User
from flask_peewee.tests.test_app import app as flask_app
from peewee import *


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

    def make_legacy_password(self, raw_password):
        salt = get_hexdigest('salt', 'salt')[:5]
        return '%s$%s' % (salt, get_hexdigest(salt, raw_password))

    def test_legacy_password_verify(self):
        legacy = self.make_legacy_password('testing')
        self.assertTrue(is_legacy_password(legacy))
        self.assertFalse(is_legacy_password(make_password('testing')))

        # legacy salted-sha1 hashes still verify.
        self.assertTrue(check_password('testing', legacy))
        self.assertFalse(check_password('wrong', legacy))

    def test_legacy_password_upgraded_on_login(self):
        from flask_peewee.tests.test_app import auth

        user = self.create_user('legacy', 'placeholder')
        user.password = self.make_legacy_password('sekret')
        user.save()
        self.assertTrue(is_legacy_password(user.password))

        # wrong password does not authenticate or rehash.
        self.assertFalse(auth.authenticate('legacy', 'nope'))
        self.assertTrue(is_legacy_password(User.get(User.id == user.id).password))

        # correct login verifies and transparently rehashes.
        self.assertTrue(auth.authenticate('legacy', 'sekret'))
        stored = User.get(User.id == user.id).password
        self.assertFalse(is_legacy_password(stored))
        self.assertTrue(check_password('sekret', stored))

    def test_is_safe_url(self):
        for good in ('/', '/admin/', '/a/b/?x=1', 'relative/path'):
            self.assertTrue(is_safe_url(good), good)
        for bad in ('', None, 'http://evil.com', 'https://evil.com/x',
                    '//evil.com', 'javascript:alert(1)'):
            self.assertFalse(is_safe_url(bad), bad)

    def test_get_model_from_dictionary(self):
        class User(Model):
            username = CharField()
            is_admin = BooleanField()

        class Tweet(Model):
            user = ForeignKeyField(User)
            content = TextField()

        user, _ = get_model_from_dictionary(User, {'username': 'cl', 'is_admin': 'false'})
        self.assertEqual(user.username, 'cl')
        self.assertFalse(user.is_admin)

        user, _ = get_model_from_dictionary(User, {'username': 'cl2', 'is_admin': True})
        self.assertEqual(user.username, 'cl2')
        self.assertTrue(user.is_admin)

        _, rel = get_model_from_dictionary(Tweet, {
            'user': {'username': 'cl', 'is_admin': False},
            'content': 'asdf'})
        tweet, user = rel
        self.assertEqual(tweet.content, 'asdf')
        self.assertEqual(tweet.user.username, 'cl')
        self.assertFalse(tweet.user.is_admin)

        self.assertEqual(user.username, 'cl')
        self.assertFalse(user.is_admin)
