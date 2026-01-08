.. _database:

Database Wrapper
================

The Peewee database wrapper provides a thin layer of integration between flask
apps and the peewee orm.

The database wrapper is important because it ensures that a database connection
is created for every incoming request, and closed upon request completion.  It
also provides a subclass of ``Model`` which works with the database specified
in your app's configuration.

Most features of ``flask-peewee`` require a database wrapper, so you very likely
always create one.

The database wrapper reads its configuration from the Flask application.  The
configuration requires only two arguments, but any additional arguments will
be passed to the database driver when connecting:

`name`
    The name of the database to connect to (or filename if using sqlite3)

`engine`
    The database driver to use, must be a subclass of ``peewee.Database``.

.. code-block:: python

    from flask import Flask
    from peewee import *

    from flask_peewee.db import Database

    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }

    app = Flask(__name__)
    app.config.from_object(__name__)  # Load database configuration from module.

    # Instantiate the db wrapper.
    db = Database(app)

    # Start creating models.
    class Blog(db.Model):
        name = CharField()
        # .. etc.

You can also directly pass the Peewee database instance to the
:py:class:`Database` helper:

.. code-block:: python

    app = Flask(__name__)
    app.config.from_object(__name__)

    sqlite_db = SqliteDatabase('example.db')
    db = Database(app, sqlite_db)

    class Blob(db.Model):
        # ...

The database initialization can be deferred in order to support more dynamic
behavior:

.. code-block:: python

    from flask_peewee.db import Database

    # Defer initialization but define our models.
    db = Database()

    class Blog(db.Model):
        name = CharField()
        # .. etc.

    # Some time later, we can:
    app = Flask(__name__)
    app.config.from_object(__name__)
    db.init_app(app)

    # Or we can also specify the database directly.
    app = Flask(__name__)

    sqlite_db = SqliteDatabase('example.db')
    db.init_app(app, sqlite_db)


Other examples
--------------

To connect to MySQL using authentication:

.. code-block:: python

    DATABASE = {
        'name': 'my_database',
        'engine': 'peewee.MySQLDatabase',
        'user': 'db_user',
        'passwd': 'secret password',
    }

To connect to Postgresql using the playhouse ``PostgresqlExtDatabase``:

.. code-block:: python

    DATABASE = {
        'name': 'pg_database',
        'engine': 'playhouse.PostgresqlExtDatabase',
        'host': '127.0.0.1',
        'user': 'postgres',
        'port': 5432,
    }

We can specify the database directly, as well:

.. code-block:: python

    pg_db = PostgresqlDatabase('pg_database')

    db = Database(app, pg_db)
