import datetime

from flask_peewee.serializer import Deserializer
from flask_peewee.serializer import Serializer
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import User


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
            'join_date': self.admin.join_date.isoformat(),
            'active': True,
            'admin': True,
            'email': '',
        })

        # field maps are keyed by path now: () is the root object.
        serialized = self.s.serialize_object(self.admin, fields={(): ['id', 'username']})
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
        })

        serialized = self.s.serialize_object(self.admin, exclude={(): ['password', 'join_date']})
        self.assertEqual(serialized, {
            'id': self.admin.id,
            'username': 'admin',
            'active': True,
            'admin': True,
            'email': '',
        })

    def test_clean_data_nested_lists(self):
        # a field holding a list of scalars or datetimes must serialize without
        # error, converting each element (the old code called .items() on a
        # list element and raised).
        dt = datetime.datetime(2026, 1, 2, 3, 4, 5)
        cleaned = self.s.clean_data({
            'tags': ['a', 'b', 'c'],
            'times': [dt, dt],
            'nested': [{'when': dt}],
            'scalar': dt,
        })
        self.assertEqual(cleaned['tags'], ['a', 'b', 'c'])
        self.assertEqual(cleaned['times'], [dt.isoformat(), dt.isoformat()])
        self.assertEqual(cleaned['nested'], [{'when': dt.isoformat()}])
        self.assertEqual(cleaned['scalar'], dt.isoformat())

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

    def test_deserialize_drops_underscore_keys(self):
        # lenient deserialization sets non-field keys on the instance (the fk
        # column name "user_id", a user property), but drops underscore-prefixed
        # peewee internals like "_pk", which would otherwise retarget the row.
        self.create_users()
        note = Note.create(user=self.admin, message='original')
        other = Note.create(user=self.normal, message='other')

        deserialized, models = self.d.deserialize_object(note, {
            'message': 'edited',
            '_pk': other.id,
            'scratch': 'kept',
        })
        self.assertEqual(deserialized.id, note.id)      # _pk dropped
        self.assertEqual(deserialized.message, 'edited')
        self.assertEqual(deserialized.scratch, 'kept')  # non-underscore set

        # a foreign key written by column name still lands.
        via_column, models = self.d.deserialize_object(Note(), {
            'message': 'via-column',
            'user_id': self.normal.id,
        })
        self.assertEqual(via_column.user_id, self.normal.id)
