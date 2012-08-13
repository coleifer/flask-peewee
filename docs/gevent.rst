.. _gevent:

Using gevent
============

If you would like to serve your flask application using gevent, there are two small
settings you will need to add.

Database configuration
----------------------

Instruct peewee to store connection information in a thread local:

.. code-block:: python

    # app configuration
    DATABASE = {
        'name': 'my_db',
        'engine': 'peewee.PostgresqlDatabase',
        'user': 'postgres',
        'threadlocals': True, # <-- this
    }


Monkey-patch the thread module
------------------------------

Some time before instantiating a :py:class:`Database` object (and preferrably at
the very "beginning" of your code) you will want to `monkey-patch <http://www.gevent.org/gevent.monkey.html>`_
the standard library thread module:

.. code-block:: python

    from gevent import monkey; monkey.patch_thread()

If you want to patch everything (recommended):

.. code-block:: python

    from gevent import monkey; monkey.patch_all()

.. note:: Remember to monkey-patch before initializing your app


Rationale
---------

flask-peewee opens a connection-per-request.  Flask stores things, like "per-request"
information, in a special object called a `context local <http://flask.pocoo.org/docs/reqcontext/>`_.
Flask will ensure that this works even in a greened environment.  Peewee does not
automatically work in a "greened" environment, and stores connection state on the
database instance in a local.  Peewee can use a thread local instead, which ensures
connections are not shared across threads.  When using peewee with gevent, it is
necessary to make this "threadlocal" a "greenlet local" by monkeypatching the thread module.
