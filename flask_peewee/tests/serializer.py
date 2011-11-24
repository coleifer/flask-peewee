import datetime

from flask_peewee.serializer import Serializer, ModelSerializer, Deserializer, ModelDeserializer
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User, Message, Note


class SerializerTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(SerializerTestCase, self).setUp()
        self.s = Serializer()
        self.ms = ModelSerializer()
        self.d = Deserializer()
        self.md = ModelDeserializer()
    
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
        
        serialized = self.s.serialize_object(self.admin, fields=('id', 'username',))
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
        })
        
        serialized = self.s.serialize_object(self.admin, exclude=('password', 'join_date',))
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
            'active': True,
            'admin': True,
            'email': '',
        })
    
    def test_deserializer(self):
        users = self.create_users()
        
        deserialized = self.d.deserialize_object({
            'id': self.admin.id,
            'username': 'admin',
            'password': self.admin.password,
            'join_date': self.admin.join_date.strftime('%Y-%m-%d %H:%M:%S'),
            'active': True,
            'admin': True,
        }, User())
        
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
        
        deserialized = self.d.deserialize_object({
            'username': 'edited',
            'active': False,
            'admin': False,
        }, self.admin)
        
        self.assertEqual(deserialized.username, 'edited')
        self.assertEqual(deserialized.admin, False)
        self.assertEqual(deserialized.active, False)
        self.assertEqual(deserialized.id, admin_pk)
        
        deserialized.save()
        
        self.assertEqual(User.select().count(), 3)
        edited = User.get(username='edited')
        self.assertEqual(edited.id, admin_pk)
    
    def test_model_serializer(self):
        users = self.create_users()
        serialized = self.ms.serialize_object(self.admin)
        self.assertEqual(serialized, {
            '__model__': 'User',
            '__module__': 'flask_peewee.tests.test_app',
            'id': self.admin.id,
            'username': 'admin',
            'password': self.admin.password,
            'join_date': self.admin.join_date.strftime('%Y-%m-%d %H:%M:%S'),
            'active': True,
            'admin': True,
            'email': '',
        })
        
        serialized = self.ms.serialize_object(self.admin, fields=('id', 'username',))
        self.assertEqual(serialized, {
            '__model__': 'User',
            '__module__': 'flask_peewee.tests.test_app',
            'id': self.admin.id,
            'username': 'admin',
        })
    
    def test_model_deserializer(self):
        users = self.create_users()
        
        deserialized = self.md.deserialize_object({
            '__model__': 'User',
            '__module__': 'flask_peewee.tests.test_app',
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
        
        deserialized = self.md.deserialize_object({
            '__model__': 'User',
            '__module__': 'flask_peewee.tests.test_app',
            'username': 'edited',
            'active': False,
            'admin': False,
        }, self.admin)
        
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
        d = self.d.deserialize_object(s, User())
        self.assertEqual(d, self.admin)
        
        s = self.ms.serialize_object(self.admin)
        d = self.md.deserialize_object(s)
        self.assertEqual(d, self.admin)
