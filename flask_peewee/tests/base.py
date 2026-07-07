import unittest

from flask_peewee import utils
from flask_peewee.tests import test_app
from flask_peewee.tests.test_app import AModel
from flask_peewee.tests.test_app import BDetails
from flask_peewee.tests.test_app import BModel
from flask_peewee.tests.test_app import CModel
from flask_peewee.tests.test_app import Comment
from flask_peewee.tests.test_app import DModel
from flask_peewee.tests.test_app import EModel
from flask_peewee.tests.test_app import FModel
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import User


class FlaskPeeweeTestCase(unittest.TestCase):
    # use a cheap hashing method so the suite is not dominated by scrypt.
    def setUp(self):
        utils.PASSWORD_HASH_METHOD = 'pbkdf2:sha256:1'

        # drop_tables/create_tables resolve foreign-key ordering for us.
        models = [User, Message, Note, Comment, EModel, FModel]
        test_app.db.database.drop_tables(models)
        test_app.db.database.create_tables(models)

        self.flask_app = test_app.app
        self.flask_app._template_context = {}

        self.app = test_app.app.test_client()

    def create_user(self, username, password, **kwargs):
        user = User(username=username, email=kwargs.pop('email', ''), **kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_message(self, user, content, **kwargs):
        return Message.create(user=user, content=content, **kwargs)

    def create_users(self):
        users = [
            self.create_user('admin', 'admin', admin=True),
            self.create_user('normal', 'normal'),
            self.create_user('inactive', 'inactive', active=False),
        ]
        self.admin, self.normal, self.inactive = users
        return users

    def get_context(self, var_name):
        if var_name not in self.flask_app._template_context:
            raise KeyError('%s not in template context' % var_name)
        return self.flask_app._template_context[var_name]

    def assertContext(self, key, value):
        self.assertEqual(self.get_context(key), value)
