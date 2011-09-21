.. _authentication:

Authentication
==============

The :py:class:`Authentication` class provides a means of authenticating users
of the site.  It is designed to work out-of-the-box with a simple ``User`` model,
but can be heavily customized.

The auth system is also designed to work closely with the :ref:`admin-interface`.


Getting started
---------------

In order to provide a method for users to authenticate with your site, instantiate
an :py:class:`Auth` backend for your project:

.. code-block:: python

    from flask import Flask
    
    from flaskext.auth import Auth
    from flaskext.db import Peewee
    
    app = Flask(__name__)
    db = Peewee(app)
    
    # needed for authentication
    auth = Auth(app, db)


Marking areas of the site as login required
-------------------------------------------

If you want to mark specific areas of your site as requiring auth, you can
decorate views using the :py:meth:`Auth.login_required` decorator:

.. code-block:: python

    @app.route('/private/')
    @auth.login_required
    def private_timeline():
        user = auth.get_logged_in_user()
        
        # ... display the private timeline for the logged-in user

If the request comes from someone who has not logged-in with the site, they are
redirected to the :py:meth:`Auth.login` view, which allows the user to authenticate.


Retrieving the current user
---------------------------

Whenever in a `request context <http://flask.pocoo.org/docs/reqcontext/>`_, the
currently logged-in user is available by calling :py:meth:`Auth.get_logged_in_user`,
which will return ``None`` if the requesting user is not logged in.

The auth system also registers a pre-request hook that stores the currently logged-in
user in the special flask variable ``g``.


Accessing the user in the templates
-----------------------------------

The auth system registers a template context processor which makes the logged-in
user available in any template:

.. code-block:: html

    {% if user %}
      <p>Hello {{ user.username }}</p>
    {% else %}
      <p>Please <a href="{{ url_for('auth.login') }}?next={{ request.path }}">log in</a></p>
    {% endif %}


Components of the auth system
-----------------------------

The :py:class:`Auth` system is comprised of a single class which is responsible
for coordinating incoming requests to your project with known users.  It provides
the following:

* views for login and logout
* model to store user data (or you can provide your own)
* mechanism for identifying users across requests (uses session storage)

All of these pieces can be customized, but the default out-of-box implementation
aims to provide a good starting place.

So, without further ado here's a look at the auth class:

.. py:class:: Auth

    .. py:method:: __init__(app, db[, user_model=None[, prefix='/accounts']])
