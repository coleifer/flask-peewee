import unittest

from flask import Flask
from peewee import Proxy
from peewee import SqliteDatabase

from flask_peewee.db import Database
from flask_peewee.exceptions import ImproperlyConfigured


class DatabaseTestCase(unittest.TestCase):
    def test_initialize_config(self):
        app = Flask(__name__)
        app.config.update({'DATABASE': {
            'name': ':memory:',
            'engine': 'peewee.SqliteDatabase'}})

        db = Database(app)
        self.assertTrue(isinstance(db.database, SqliteDatabase))
        self.assertEqual(db.database.database, ':memory:')
        self.assertTrue(db.database is db.Model._meta.database)

    def test_initialize_explicit(self):
        app = Flask(__name__)

        sqlite_db = SqliteDatabase(':memory:')
        db = Database(app, sqlite_db)
        self.assertTrue(isinstance(db.database, SqliteDatabase))
        self.assertTrue(db.database is sqlite_db)
        self.assertTrue(db.database is db.Model._meta.database)
        self.assertEqual(db.database.database, ':memory:')

    def test_defer_initialize_config(self):
        app = Flask(__name__)
        app.config.update({'DATABASE': {
            'name': ':memory:',
            'engine': 'peewee.SqliteDatabase'}})

        db = Database(None)
        self.assertTrue(isinstance(db.database, Proxy))
        self.assertTrue(db.Model._meta.database is db.database)

        db.init_app(app)
        self.assertTrue(isinstance(db.database, Proxy))
        self.assertEqual(db.database.database, ':memory:')
        self.assertEqual(db.Model._meta.database.database, ':memory:')
        self.assertTrue(db.database is db.Model._meta.database)

    def test_initialize_explicit(self):
        app = Flask(__name__)

        db = Database(None)
        self.assertTrue(isinstance(db.database, Proxy))
        self.assertTrue(db.Model._meta.database is db.database)

        sqlite_db = SqliteDatabase(':memory:')
        db.init_app(app, sqlite_db)
        self.assertTrue(isinstance(db.database, Proxy))
        self.assertEqual(db.database.database, ':memory:')
        self.assertEqual(db.Model._meta.database.database, ':memory:')
        self.assertTrue(db.database is db.Model._meta.database)

    def test_initialize_mix(self):
        app = Flask(__name__)

        sqlite_db = SqliteDatabase(':memory:')
        db = Database(None, sqlite_db)
        self.assertTrue(db.database is sqlite_db)
        self.assertTrue(db.Model._meta.database is db.database)

        db.init_app(app)
        self.assertTrue(db.database is sqlite_db)
        self.assertTrue(db.Model._meta.database is sqlite_db)

        self.assertRaises(ImproperlyConfigured, db.init_app, app, db)
