import peewee
from peewee import *

from flask_peewee.exceptions import ImproperlyConfigured
from flask_peewee.utils import load_class


class Database(object):
    def __init__(self, app):
        self.app = app
        
        self.load_database()
        self.register_handlers()
        
        self.Model = self.get_model_class()
    
    def load_database(self):
        self.database_config = self.app.config['DATABASE']
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
    
        self.database = self.database_class(self.database_name, **self.database_config)
    
    def get_model_class(self):
        class BaseModel(Model):
            class Meta:
                database = self.database
        
        return BaseModel
    
    def connect_db(self):
        self.database.connect()
    
    def close_db(self, resp):
        self.database.close()
        return resp
    
    def register_handlers(self):
        self.app.before_request(self.connect_db)
        self.app.after_request(self.close_db)
