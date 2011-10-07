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
    from flaskext.db import Database
    
    app = Flask(__name__)
    db = Database(app)
    
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
    The ``flaskext.auth.BaseUser`` mixin provides default implementations of these two methods.

Here's a simple example of extending the auth system to use a custom user model:

.. code-block:: python

    from flaskext.auth import BaseModel # <-- implements set_password and check_password

    app = Flask(__name__)
    db = Database(app)
    
    # create our custom user model note that we're mixing in the BaseModel in order to
    # use the default auth methods it implements, "set_password" and "check_password"
    class User(db.Model, BaseModel):
        username = CharField()
        password = CharField()
        email = CharField()
        
        # ... our custom fields ...
        is_superuser = BooleanField()
    
    
    # create a modeladmin for it
    class UserAdmin(ModelAdmin):
        columns = ('username', 'email', 'is_superuser',)
    
    
    # subclass Auth so we can return our custom classes
    class CustomAuth(Auth):
        def get_user_model(self):
            return User
        
        def get_model_admin(self):
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


Components of the auth system
-----------------------------

Auth
^^^^

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
    
        :param app: flask application to bind admin to
        :param db: :py:class:`Database` database wrapper for flask app
        :param user_model: ``User`` model to use
        :param prefix: url to bind authentication views to, defaults to /accounts/
    
    .. py:method:: get_logged_in_user()
    
        :rtype: returns the currently logged-in ``User``, or ``None`` if session is anonymous
        
        .. note:: this method must be called while within a ``RequestContext``

    .. py:method:: login_required(func)
    
        :param func: a view function to be marked as login-required
        :rtype: if the user is logged in, return the view as normal, otherwise
            returns a redirect to the login page
        
        .. note:: this decorator should be applied closest to the original view function
        
        .. code-block:: python
        
            @app.route('/private/')
            @auth.login_required
            def private():
                # this view is only accessible by logged-in users
                return render_template('private.html')
    
    .. py:method:: get_user_model()
    
        :rtype: Peewee model to use for persisting user data and authentication
    
    .. py:method:: get_model_admin([model_admin=None])
    
        :param model_admin: subclass of :py:class:`ModelAdmin` to use as the base class
        :rtype: a subclass of :py:class:`ModelAdmin` suitable for use with the ``User`` model
    
        .. note:: the default implementation includes an override of the :py:meth:`ModelAdmin.save_model`
            method to intelligently hash passwords:
    
            .. code-block:: python
            
                class UserAdmin(model_admin):
                    columns = ['username', 'email', 'active', 'admin']
                    
                    def save_model(self, instance, form, adding=False):
                        orig_password = instance.password
                        
                        user = super(UserAdmin, self).save_model(instance, form, adding)
                        
                        if orig_password != form.password.data:
                            user.set_password(form.password.data)
                            user.save()
                        
                        return user
    
    .. py:method:: get_urls()
    
        :rtype: a tuple of 2-tuples mapping url to view function.
        
        .. note:: the default implementation provides views for login and logout only
        
            .. code-block:: python
            
                def get_urls(self):
                    return (
                        ('/logout/', self.logout),
                        ('/login/', self.login),
                    )
    
    .. py:method:: get_login_form()
    
        :rtype: a ``wtforms.Form`` subclass to use for retrieving any user info required for login
    
    .. py:method:: authenticate(username, password)
    
        Given the ``username`` and ``password``, retrieve the user with the matching
        credentials if they exist.  No exceptions should be raised by this method.
        
        :rtype: ``User`` model if successful, otherwise ``False``
    
    .. py:method:: login_user(user)
    
        Mark the given user as "logged-in".  In the default implementation, this
        entails storing data in the ``Session`` to indicate the successful login.
    
        :param user: ``User`` instance
    
    .. py:method:: logout_user()
    
        Mark the requesting user as logged-out

BaseUser mixin
^^^^^^^^^^^^^^

.. py:class:: BaseUser(object)

    Provides default implementations for password hashing and validation

    .. py:method:: set_password(password)
        
        Encrypts the given password and stores the encrypted version on the model

    .. py:method:: check_password(password)

        Verifies if the given plaintext password matches the encrypted version stored
        on the model

        :rtype: Boolean
