# config

class Configuration(object):
    # Specify example.db in the current working directory. See docs for more:
    # https://docs.peewee-orm.com/en/latest/peewee/db_tools.html#db-url
    DATABASE = 'sqlite:///example.db'

    # Or, specify path and additional connection settings:
    #DATABASE = {
    #    'name': 'example.db',
    #    'engine': 'peewee.SqliteDatabase',
    #    'check_same_thread': False,
    #}

    # Or, specify a peewee database instance directly.
    #from peewee import SqliteDatabase
    #DATABASE = SqliteDatabase('example.db')

    DEBUG = True
    SECRET_KEY = 'shhhh'
