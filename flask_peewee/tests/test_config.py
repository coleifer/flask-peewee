# config

class Configuration(object):
    DATABASE = {
        'name': 'test.db',
        'engine': 'peewee.SqliteDatabase',
    }
    DEBUG = True
    SECRET_KEY = 'shhhh'
    TESTING = True
