.. _database:

Database Wrapper
================

The Peewee database wrapper provides a thin layer of integration between flask
apps and the peewee orm.

.. code-block:: python

    from flask import Flask
    from peewee import *
    
    from flaskext.db import Database
    
    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }
    
    app = Flask(__name__)
    app.config.from_object(__name__) # load database configuration from this module
    
    # instantiate the db wrapper
    db = Database(app)
    
    # start creating models
    class Blog(db.Model):
        name = CharField()
        # .. etc


The database wrapper is important because it ensures that a database connection
is created for every incoming request, and closed upon request completion.  It
also provides a subclass of ``Model`` which works with the database specified
in your app's configuration.


.. py:class:: Database

    .. py:attribute:: Model
    
        Model subclass that works with the database specified by the app's config

    .. py:method:: __init__(app)
    
        Initializes and configures the peewee database wrapper.  Registers pre-
        and post-request hooks to handle connecting to the database.
        
        :param app: flask application to bind admin to
