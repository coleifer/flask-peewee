# config


class Configuration(object):
    DATABASE = {
        'name': 'postgres',
        'user': 'postgres',
        'host': 'localhost',
        'port': '5432',
        'engine': 'playhouse.postgres_ext.PostgresqlExtDatabase',
    }
    DEBUG = True
    SECRET_KEY = 'shhhh'
    TESTING = True
