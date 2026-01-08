import peewee
from peewee import *

from flask_peewee.exceptions import ImproperlyConfigured
from flask_peewee.utils import load_class


class Database(object):
    def __init__(self, app=None, database=None):
        self.database = None
        self.init_app(app, database)

    def init_app(self, app, database=None):
        if app is None:
            self.database = database or Proxy()
            self.Model = self.get_model_class()
            return

        if isinstance(self.database, Proxy):
            # We deferred initialization, now initialize the proxy.
            self.database.initialize(database or self.load_database(app))
        elif self.database is None:
            self.database = database or self.load_database(app)
            self.Model = self.get_model_class()
        elif database:
            raise ImproperlyConfigured('Database plugin has already been initialized.')

        self.register_handlers(app)

    def load_database(self, app):
        self.database_config = dict(app.config['DATABASE'])
        try:
            self.database_name = self.database_config.pop('name')
            self.database_engine = self.database_config.pop('engine')
        except KeyError:
            raise ImproperlyConfigured('Please specify a "name" and "engine" for your database')

        try:
            self.database_class = load_class(self.database_engine)
            assert issubclass(self.database_class, peewee.Database)
        except ImportError:
            raise ImproperlyConfigured('Unable to import: "%s"' % self.database_engine)
        except AttributeError:
            raise ImproperlyConfigured('Database engine not found: "%s"' % self.database_engine)
        except AssertionError:
            raise ImproperlyConfigured('Database engine not a subclass of peewee.Database: "%s"' % self.database_engine)

        return self.database_class(self.database_name, **self.database_config)

    def get_model_class(self):
        class BaseModel(Model):
            class Meta:
                database = self.database

        return BaseModel

    def connect_db(self):
        if self.database.is_closed():
            self.database.connect()

    def close_db(self, exc):
        if not self.database.is_closed():
            self.database.close()

    def register_handlers(self, app):
        app.before_request(self.connect_db)
        app.teardown_request(self.close_db)
