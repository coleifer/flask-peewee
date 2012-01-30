import datetime

from flask_peewee.serializer import Serializer, Deserializer
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User, Message, Note


class SerializerTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(SerializerTestCase, self).setUp()
        self.s = Serializer()
        self.d = Deserializer()
    
    def test_serializer(self):
        users = self.create_users()
        serialized = self.s.serialize_object(self.admin)
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
            'password': self.admin.password,
            'join_date': self.admin.join_date.strftime('%Y-%m-%d %H:%M:%S'),
            'active': True,
            'admin': True,
            'email': '',
        })
        
        serialized = self.s.serialize_object(self.admin, fields={User: ['id', 'username']})
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
        })
        
        serialized = self.s.serialize_object(self.admin, exclude={User: ['password', 'join_date']})
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
            'active': True,
            'admin': True,
            'email': '',
        })
    
    def test_deserializer(self):
        users = self.create_users()
        
        deserialized, models = self.d.deserialize_object(User(), {
            'id': self.admin.id,
            'username': 'admin',
            'password': self.admin.password,
            'join_date': self.admin.join_date.strftime('%Y-%m-%d %H:%M:%S'),
            'active': True,
            'admin': True,
        })
        
        for attr in ['id', 'username', 'password', 'active', 'admin']:
            self.assertEqual(
                getattr(deserialized, attr),
                getattr(self.admin, attr),
            )
        
        self.assertEqual(
            deserialized.join_date.strftime('%Y-%m-%d %H:%M:%S'),
            self.admin.join_date.strftime('%Y-%m-%d %H:%M:%S'),
        )
            
        admin_pk = self.admin.id
        
        deserialized, models = self.d.deserialize_object(self.admin, {
            'username': 'edited',
            'active': False,
            'admin': False,
        })
        
        self.assertEqual(deserialized.username, 'edited')
        self.assertEqual(deserialized.admin, False)
        self.assertEqual(deserialized.active, False)
        self.assertEqual(deserialized.id, admin_pk)
        
        deserialized.save()
        
        self.assertEqual(User.select().count(), 3)
        edited = User.get(username='edited')
        self.assertEqual(edited.id, admin_pk)
    
    def test_s_and_d(self):
        self.create_users()
        
        s = self.s.serialize_object(self.admin)
        d, model_list = self.d.deserialize_object(User(), s)
        self.assertEqual(d, self.admin)
