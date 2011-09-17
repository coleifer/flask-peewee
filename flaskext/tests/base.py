import unittest

from flaskext.tests import test_app
from flaskext.tests.test_app import User, Message, Note


class FlaskPeeweeTestCase(unittest.TestCase):
    def setUp(self):
        Note.drop_table(True)
        Message.drop_table(True)
        User.drop_table(True)
        User.create_table()
        Message.create_table()
        Note.create_table()
        self.app = test_app.app.test_client() 
    
    def create_user(self, username, password, **kwargs):
        user = User(username=username, **kwargs)
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
