.. _authentication:

Authentication
==============

The :py:class:`Authentication` class provides a means of authenticating users
of the site.  It is designed to work out-of-the-box with a simple ``User`` model,
but can be heavily customized.

The :py:class:`Auth` system is comprised of a single class which is responsible
for coordinating incoming requests to your project with known users.  It provides
the following:

* views for login and logout
* model to store user data (or you can provide your own)
* mechanism for identifying users across requests (uses session storage)

All of these pieces can be customized, but the default out-of-box implementation
aims to provide a good starting place.

The auth system is also designed to work closely with the :ref:`admin-interface`.


Getting started
---------------

In order to provide a method for users to authenticate with your site, instantiate
an :py:class:`Auth` backend for your project:

.. code-block:: python

    from flask import Flask
    
    from flask_peewee.auth import Auth
    from flask_peewee.db import Database
    
    app = Flask(__name__)
    db = Database(app)
    
    # needed for authentication
    auth = Auth(app, db)

.. note::
    ``user`` is reserverd keyword in Postgres. Pass db_table to Auth to override db table.

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
After successfully logging-in, they will be redirected to the page they requested
initially.


Requiring specific permissions
------------------------------

:py:meth:`Auth.login_required` only checks that *someone* is logged in.  When a
view should be restricted further, two more decorators are available:

* :py:meth:`Auth.admin_required` -- additionally requires the user's ``admin``
  flag to be set.
* :py:meth:`Auth.test_user` -- takes a predicate ``fn(user)`` and builds a
  decorator that requires a logged-in user for whom it returns a truthy value.

In fact ``login_required`` and ``admin_required`` are nothing more than
``test_user(lambda user: True)`` and ``test_user(lambda user: user.admin)``.  Use
``test_user`` to express any rule you like:

.. code-block:: python

    @app.route('/staff/')
    @auth.test_user(lambda user: user.is_staff)
    def staff_area():
        # only reachable by a logged-in user whose is_staff attribute is truthy
        ...

A request that fails the check is redirected to the login view, exactly like
``login_required``.


Retrieving the current user
---------------------------

Whenever in a `request context <https://flask.palletsprojects.com/en/stable/reqcontext/>`_, the
currently logged-in user is available by calling :py:meth:`Auth.get_logged_in_user`,
which will return ``None`` if the requesting user is not logged in.

The auth system also registers a pre-request hook that stores the currently logged-in
user in the special flask variable ``g``.


Logging users in and out programmatically
-----------------------------------------

Sometimes you need to establish the session yourself -- for instance, logging a
user in immediately after they register.  :py:meth:`Auth.login_user` and
:py:meth:`Auth.logout_user` do exactly that from within a request:

.. code-block:: python

    user = User.create(username='huey', email='huey@example.com', ...)
    user.set_password('meow')
    user.save()

    auth.login_user(user)   # huey is now logged in for subsequent requests

``logout_user()`` ends the session.  By default it removes only flask-peewee's
own session keys, leaving any other data you've stored in the session intact.
Pass ``clear_session=True`` when constructing :py:class:`Auth` to have logout
wipe the *entire* session instead -- a simple hardening step against session
fixation:

.. code-block:: python

    auth = Auth(app, db, clear_session=True)


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


Using a custom "User" model
---------------------------

It is easy to use your own model for the ``User``, though depending on the amount
of changes it may be necessary to override methods in both the :py:class:`Auth` and
:py:class:`Admin` classes.

Unless you want to override the default behavior of the :py:class:`Auth` class' mechanism
for actually authenticating users (which you may want to do if relying on a 3rd-party
for auth) -- you will want to be sure your ``User`` model implements two methods:

* ``set_password(password)`` -- takes a raw password and stores an encrypted version on model
* ``check_password(password)`` -- returns whether or not the supplied password matches
  the one stored on the model instance

.. note::
    The :py:class:`BaseUser` mixin provides default implementations of these two methods.

Here's a simple example of extending the auth system to use a custom user model:

.. code-block:: python

    from flask_peewee.auth import BaseUser # <-- implements set_password and check_password

    app = Flask(__name__)
    db = Database(app)
    
    # create our custom user model. note that we're mixing in BaseUser in order to
    # use the default auth methods it implements, "set_password" and "check_password"
    class User(db.Model, BaseUser):
        username = CharField()
        password = CharField()
        email = CharField()
        
        # ... our custom fields ...
        is_superuser = BooleanField()
    
    
    # create a modeladmin for it
    class UserAdmin(ModelAdmin):
        columns = ('username', 'email', 'is_superuser',)

        # Make sure the user's password is hashed, after it's been changed in
        # the admin interface. If we don't do this, the password will be saved
        # in clear text inside the database and login will be impossible.
        def save_model(self, instance, form, adding=False):
            orig_password = instance.password

            user = super(UserAdmin, self).save_model(instance, form, adding)

            if orig_password != form.password.data:
                user.set_password(form.password.data)
                user.save()

            return user
    
    
    # subclass Auth so we can return our custom classes
    class CustomAuth(Auth):
        def get_user_model(self):
            return User

        def get_model_admin(self, model_admin=None):
            return UserAdmin
    
    # instantiate the auth
    auth = CustomAuth(app, db)


Here's how you might integrate the custom auth with the admin area of your site:

.. code-block:: python
    
    # subclass Admin to check for whether the user is a superuser
    class CustomAdmin(Admin):
        def check_user_permission(self, user):
            return user.is_superuser
    
    # instantiate the admin
    admin = CustomAdmin(app, auth)
    
    admin.register(User, UserAdmin)
    admin.setup()
