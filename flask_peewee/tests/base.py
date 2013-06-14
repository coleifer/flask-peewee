import unittest

from flask_peewee.tests import test_app
from flask_peewee.tests.test_app import AModel
from flask_peewee.tests.test_app import BDetails
from flask_peewee.tests.test_app import BModel
from flask_peewee.tests.test_app import CModel
from flask_peewee.tests.test_app import DModel
from flask_peewee.tests.test_app import EModel
from flask_peewee.tests.test_app import FModel
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import User


class FlaskPeeweeTestCase(unittest.TestCase):
    def setUp(self):
        Note.drop_table(True)
        Message.drop_table(True)
        User.drop_table(True)
        User.create_table()
        Message.create_table()
        Note.create_table()

        FModel.drop_table(True)
        EModel.drop_table(True)
        EModel.create_table()
        FModel.create_table()
        
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
