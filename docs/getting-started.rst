.. _getting-started:

Getting Started
===============

The goal of this document is to help get you up and running quickly.  So without
further ado, let's get started.

.. note::
    Hopefully you have some familiarity with the `flask framework <http://flask.pocoo.org/>`_ and
    the `peewee orm <http://charlesleifer.com/docs/peewee/>`_, but if not those links
    should help you get started.

.. note::
    For a complete example project, check the `example app <https://github.com/coleifer/flask-peewee/tree/master/example>`_
    that ships with flask-peewee.


Creating a flask app
--------------------

First, be sure you have :ref:`installed flask-peewee and its dependencies <installation>`.
You can verify by running the test suite: ``python setup.py test``.

After ensuring things are installed, open a new file called "app.py" and enter the
following code:

.. code-block:: python

    from flask import Flask
        
    app = Flask(__name__)
    app.config.from_object(__name__)
    
    if __name__ == '__main__':
        app.run()

This isn't very exciting, but we can check out our project by running the app:

.. code-block:: console

    $ python app.py
     * Running on http://127.0.0.1:5000/
     * Restarting with reloader


Navigating to the url listed will show a simple 404 page, because we haven't
configured any templates or views yet.


Creating a simple model
-----------------------

Let's add a simple model.  Before we can do that, though, it is necessary to
initialize the peewee database wrapper and configure the database:

.. code-block:: python

    from flask import Flask

    # flask-peewee bindings
    from flaskext.db import Database

    # configure our database
    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }
    DEBUG = True
    SECRET_KEY = 'ssshhhh'

    app = Flask(__name__)
    app.config.from_object(__name__)

    # instantiate the db wrapper
    db = Database(app)

    if __name__ == '__main__':
        app.run()


What this does is provides us with request handlers which connect to the database
on each request and close it when the request is finished.  It also provides a
base model class which is configured to work with the database specified in the
configuration.

Now we can create a model:

.. code-block:: python

    import datetime
    from peewee import *
    
    
    class Note(db.Model):
        message = TextField()
        created = DateTimeField(default=datetime.datetime.now)


.. note::
    The model we created, ``Note``, subclasses ``db.Model``, which in turn is a subclass
    of ``peewee.Model`` that is pre-configured to talk to our database.


Setting up a simple base template
---------------------------------

We'll need a simple template to serve as the base template for our app, so create
a folder named ``templates``.  In the ``templates`` folder create a file ``base.html``
and add the following:

.. code-block:: html

    <!doctype html>
    <html>
    <title>Test site</title>
    <body>
      <h2>{% block content_title %}{% endblock %}</h2>
      {% block content %}{% endblock %}
    </body>
    </html>


Editing models in the admin
---------------------------

Before we can edit these ``Note`` models in the admin, we'll need to have some
way of authenticating users on the site.  This is where :py:class:`Auth` comes in.
:py:class:`Auth` provides a ``User`` model and views for logging in and logging out,
among other things, and is required by the :py:class:`Admin`.

.. code-block:: python

    from flaskext.auth import Auth
    
    # create an Auth object for use with our flask app and database wrapper
    auth = Auth(app, db)

Let's also modify the code that runs our app to ensure our tables get created
if need be:

.. code-block:: python

    if __name__ == '__main__':
        auth.User.create_table(fail_silently=True)
        Note.create_table(fail_silently=True)
        
        app.run()

After cleaning up the imports and declarations, you should have something like
the following:

.. code-block:: python

    import datetime
    from flask import Flask
    from flaskext.auth import Auth
    from flaskext.db import Database
    from peewee import *

    # configure our database
    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }

    app = Flask(__name__)
    app.config.from_object(__name__)

    # instantiate the db wrapper
    db = Database(app)


    class Note(db.Model):
        message = TextField()
        created = DateTimeField(default=datetime.datetime.now)


    # create an Auth object for use with our flask app and database wrapper
    auth = Auth(app, db)


    if __name__ == '__main__':
        auth.User.create_table(fail_silently=True)
        Note.create_table(fail_silently=True)
        
        app.run()

**Now** we're ready to add the admin.  Place the following lines of code after
the initialization of the ``Auth`` class:

.. code-block:: python

    from flaskext.admin import Admin

    admin = Admin(app, auth)
    admin.register(Note)

    admin.setup()


We now have a functioning admin site!  Of course, you'll need a user log in with,
so open up an interactive terminal in the directory alongside the app and run
the following:

.. code-block:: python

    from app import auth
    admin = auth.User(username='admin', admin=True, active=True)
    admin.set_password('admin')
    admin.save()

You should now be able to:

1. navigate to http://127.0.0.1:5000/admin/ 
2. enter in the username and password ("admin", "admin")
3. be redirected to the admin dashboard

.. image:: fp-getting-started.jpg
