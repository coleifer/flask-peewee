.. _api:

API
===

Admin
-----

.. py:class:: Admin(app, auth[, blueprint_factory[, template_helper[, prefix]]])

    Class used to expose an admin area at a certain url in your application.  The
    Admin object implements a flask blueprint and acts as the central registry
    for models and panels you wish to expose in the admin.
    
    The Admin object coordinates the registration of models and panels and provides
    a method for ensuring a user has permission to access the admin area.
    
    The Admin object requires an :py:class:`Auth` instance when being instantiated,
    which in turn requires a Flask app and a py:class:`Database` wrapper.
    
    Here is an example of how you might instantiate an Admin object:
    
    .. code-block:: python
    
        from flask import Flask
        
        from flask_peewee.admin import Admin
        from flask_peewee.auth import Auth
        from flask_peewee.db import Database
        
        app = Flask(__name__)
        db = Database(app)
        
        # needed for authentication
        auth = Auth(app, db)
        
        # instantiate the Admin object for our project
        admin = Admin(app, auth)

    :param app: flask application to bind admin to
    :param auth: :py:class:`Auth` instance which will provide authentication
    :param blueprint_factory: an object that will create the ``BluePrint`` used by the admin
    :param template_helper: a subclass of :py:class:`AdminTemplateHelper` that provides helpers
        and context to used by the admin templates
    :param prefix: url to bind admin to, defaults to ``/admin``

    .. py:method:: register(model[, admin_class=ModelAdmin])
    
        Register a model to expose in the admin area.  A :py:class:`ModelAdmin`
        subclass can be provided along with the model, allowing for customization
        of the model's display and behavior.
        
        Example usage:
        
        .. code-block:: python
        
            # will use the default ModelAdmin subclass to display model
            admin.register(BlogModel)
            
            class EntryAdmin(ModelAdmin):
                columns = ('title', 'blog', 'pub_date',)
            
            admin.register(EntryModel, EntryAdmin)
        
        .. warning:: All models must be registered before calling :py:meth:`~Admin.setup`
    
        :param model: peewee model to expose via the admin
        :param admin_class: :py:class:`ModelAdmin` or subclass to use with given model
    
    .. py:method:: register_panel(title, panel)
    
        Register a :py:class:`AdminPanel` subclass for display in the admin dashboard.
        
        Example usage:
        
        .. code-block:: python
        
            class HelloWorldPanel(AdminPanel):
                template_name = 'admin/panels/hello.html'
                
                def get_context(self):
                    return {
                        'message': 'Hello world',
                    }
            
            admin.register_panel('Hello world', HelloWorldPanel)
        
        .. warning:: All panels must be registered before calling :py:meth:`~Admin.setup`
    
        :param title: identifier for panel, example might be "Site Stats"
        :param panel: subclass of :py:class:`AdminPanel` to display

    .. py:method:: setup()
    
        Configures urls for models and panels, then registers blueprint with the
        Flask application.  Use this method when you have finished registering
        all the models and panels with the admin object, but before starting
        the WSGI application.  For a sample implementation, check out ``example/main.py``
        in the example application supplied with flask-peewee.
        
        .. code-block:: python
        
            # register all models, etc
            admin.register(...)
        
            # finish up initialization of the admin object
            admin.setup()

            if __name__ == '__main__':
                # run the WSGI application
                app.run()
        
        .. note::
            call ``setup()`` **after** registering your models and panels
    
    .. py:method:: check_user_permission(user)
    
        Check whether the given user has permission to access to the admin area.  The
        default implementation simply checks whether the ``admin`` field is checked,
        but you can provide your own logic.
        
        This method simply controls access to the admin area as a whole.  In the
        event the user is **not** permitted to access the admin (this function
        returns ``False``), they will receive a HTTP Response Forbidden (403).
        
        Default implementation:
        
        .. code-block:: python
        
            def check_user_permission(self, user):
                return user.admin
    
        :param user: the currently logged-in user, exposed by the :py:class:`Auth` instance
        :rtype: Boolean
    
    .. py:method:: auth_required(func)
    
        Decorator that ensures the requesting user has permission.  The implementation
        first checks whether the requesting user is logged in, and if not redirects
        to the login view.  If the user *is* logged in, it calls :py:meth:`~Admin.check_user_permission`.
        Only if this call returns ``True`` is the actual view function called.
    
    .. py:method:: get_urls()
    
        Get a tuple of 2-tuples mapping urls to view functions that will be
        exposed by the admin.  The default implementation looks like this:
        
        .. code-block:: python
        
            def get_urls(self):
                return (
                    ('/', self.auth_required(self.index)),
                )
        
        This method provides an extension point for providing any additional
        "global" urls you would like to expose.
        
        .. note:: Remember to decorate any additional urls you might add
            with :py:meth:`~Admin.auth_required` to ensure they are not accessible
            by unauthenticated users.


Exposing Models with the ModelAdmin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: ModelAdmin

    Class that determines how a peewee ``Model`` is exposed in the admin area.  Provides
    a way of encapsulating model-specific configuration and behaviors.  Provided
    when registering a model with the :py:class:`Admin` instance (see :py:meth:`Admin.register`).
    
    .. py:attribute:: columns
    
        List or tuple of columns should be displayed in the list index.  By default if no
        columns are specified the ``Model``'s ``__unicode__()`` will be used.
        
        .. note::
        
            Valid values for columns are the following:
            
            * field on a model
            * attribute on a model instance
            * callable on a model instance (called with no parameters)
            
            If a column is a model field, it will be sortable.
        
        .. code-block:: python
        
            class EntryAdmin(ModelAdmin):
                columns = ['title', 'pub_date', 'blog']
    
    .. py:attribute:: paginate_by

        How many records to paginate by when viewing lists of models, defaults to 20.

    .. py:method:: get_query()
    
        Determines the list of objects that will be exposed in the admin.  By
        default this will be all objects, but you can use this method to further
        restrict the query.
        
        This method is called within the context of a request, so you can access
        the ``Flask.request`` object or use the :py:class:`Auth` instance to
        determine the currently-logged-in user.
        
        Here's an example showing how the query is restricted based on whether
        the given user is a "super user" or not:
        
        .. code-block:: python
        
            class UserAdmin(ModelAdmin):
                def get_query():
                    # ask the auth system for the currently logged-in user
                    current_user = self.auth.get_logged_in_user()
                    
                    # if they are not a superuser, only show them their own
                    # account in the admin
                    if not current_user.is_superuser:
                        return User.filter(id=current_user.id)
                    
                    # otherwise, show them all users
                    return User.select()
    
        :rtype: A ``SelectQuery`` that represents the list of objects to expose

    .. py:method:: get_object(pk)
    
        This method retrieves the object matching the given primary key.  The
        implementation uses :py:meth:`~ModelAdmin.get_query` to retrieve the
        base list of objects, then queries within that for the given primary key.
    
        :rtype: The model instance with the given pk, raising a ``DoesNotExist``
                in the event the model instance does not exist.

    .. py:method:: get_form()
    
        Provides a useful extension point in the event you want to define custom
        fields or custom validation behavior.
    
        :rtype: A `wtf-peewee <http://github.com/coleifer/wtf-peewee>`_ Form subclass that
                will be used when adding or editing model instances in the admin.
    
    .. py:method:: get_add_form()
    
        Allows you to specify a different form when adding new instances versus
        editing existing instances.  The default implementation simply calls
        :py:meth:`~ModelAdmin.get_form`.
    
    .. py:method:: get_edit_form()
    
        Allows you to specify a different form when editing existing instances versus
        adding new instances.  The default implementation simply calls
        :py:meth:`~ModelAdmin.get_form`.
    
    .. py:method:: get_filter_form()
    
        Provide a form for use when filtering the list of objects in the model admin's
        index view.  This form is slightly different in that it is tailored for use
        when filtering the list of models.
    
        :rtype: A `wtf-peewee <http://github.com/coleifer/wtf-peewee>`_ Form subclass that
                will be used when filtering the list of objects in the index view.
    
    .. py:method:: save_model(instance, form, adding=False)
    
        Method responsible for persisting changes to the database.  Called by both
        the add and the edit views.  
        
        Here is an example from the default ``auth.User`` :py:class:`ModelAdmin`,
        in which the password is displayed as a sha1, but if the user is adding
        or edits the existing password, it re-hashes:
        
        .. code-block:: python
        
            def save_model(self, instance, form, adding=False):
                orig_password = instance.password
                
                user = super(UserAdmin, self).save_model(instance, form, adding)
                
                if orig_password != form.password.data:
                    user.set_password(form.password.data)
                    user.save()
                
                return user
        
        :param instance: an unsaved model instance
        :param form: a validated form instance
        :param adding: boolean to indicate whether we are adding a new instance
                or saving an existing
        
    .. py:method:: get_urls()
    
        Useful as a hook for extending :py:class:`ModelAdmin` functionality
        with additional urls.
        
        .. note::
            It is not necessary to decorate the views specified by this method
            since the :py:class:`Admin` instance will handle this during registration
            and setup.
    
        :rtype: tuple of 2-tuples consisting of a mapping between url and view
    
    .. py:method:: get_url_name(name)
    
        Since urls are namespaced, this function provides an easy way to get
        full urls to views provided by this ModelAdmin


Extending admin functionality using AdminPanel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: AdminPanel

    Class that provides a simple interface for providing arbitrary extensions to
    the admin.  These are displayed as "panels" on the admin dashboard with a customizable
    template.  They may additionally, however, define any views and urls.  These
    views will automatically be protected by the same authentication used throughout
    the admin area.
    
    Some example use-cases for AdminPanels might be:
    
    * Display some at-a-glance functionality in the dashboard, like stats on new
      user signups.
    * Provide a set of views that should only be visible to site administrators,
      for example a mailing-list app.
    * Control global site settings, turn on and off features, etc.
    
    .. py:attribute:: template_name
    
        What template to use to render the panel in the admin dashboard, defaults
        to ``'admin/panels/default.html'``.
    
    .. py:method:: get_urls()
    
        Useful as a hook for extending :py:class:`AdminPanel` functionality
        with custom urls and views.
        
        .. note::
            It is not necessary to decorate the views specified by this method
            since the :py:class:`Admin` instance will handle this during registration
            and setup.
    
        :rtype: Returns a tuple of 2-tuples mapping url to view
    
    .. py:method:: get_url_name(name)
    
        Since urls are namespaced, this function provides an easy way to get
        full urls to views provided by this panel
    
        :param name: string representation of the view function whose url you want
        :rtype: String representing url
        
        .. code-block:: html
        
            <!-- taken from example -->
            <!-- will return something like /admin/notes/create/ -->
            {{ url_for(panel.get_url_name('create')) }}
    
    .. py:method:: get_template_name()
    
        Return the template used to render this panel in the dashboard.  By default
        simply returns the template stored under :py:attr:`AdminPanel.template_name`.
    
    .. py:method:: get_context()
    
        Return the context to be used when rendering the dashboard template.
        
        :rtype: Dictionary
    
    .. py:method:: render()
    
        Render the panel template with the context -- this is what gets displayed
        in the admin dashboard.


Auth
----

.. py:class:: Auth(app, db[, user_model=None[, prefix='/accounts']])

    The class that provides methods for authenticating users and tracking
    users across requests.  It also provides a model for persisting users to
    the database, though this can be customized.
    
    The auth framework is used by the :py:class:`Admin` and can also be integrated
    with the :py:class:`RestAPI`.
    
    Here is an example of how to use the Auth framework:
    
    .. code-block:: python
    
        from flask import Flask
        
        from flask_peewee.auth import Auth
        from flask_peewee.db import Database
        
        app = Flask(__name__)
        db = Database(app)
        
        # needed for authentication
        auth = Auth(app, db)
        
        # mark a view as requiring login
        @app.route('/private/')
        @auth.login_required
        def private_timeline():
            # get the currently-logged-in user
            user = auth.get_logged_in_user()
    
    Unlike the :py:class:`Admin` or the :py:class:`RestAPI`, there is no explicit
    ``setup()`` method call when using the Auth system.  Creation of the auth
    blueprint and registration with the Flask app happen automatically during
    instantiation.
    
    .. note:: A context processor is automatically registered that provides
        the currently logged-in user across all templates, available as "user".
        If no user is logged in, the value of this will be ``None``.
    
    .. note:: A pre-request handler is automatically registered which attempts
        to retrieve the current logged-in user and store it on the global flask
        variable ``g``.

    :param app: flask application to bind admin to
    :param db: :py:class:`Database` database wrapper for flask app
    :param user_model: ``User`` model to use
    :param prefix: url to bind authentication views to, defaults to /accounts/
    
    .. py:attribute:: default_next_url = 'homepage'
    
        The url to redirect to upon successful login in the event a ``?next=<xxx>``
        is not provided.
    
    .. py:method:: get_logged_in_user()

        .. note:: Since this method relies on the session storage to
            track users across requests, this method must be called while 
            within a ``RequestContext``.
    
        :rtype: returns the currently logged-in ``User``, or ``None`` if session is anonymous

    .. py:method:: login_required(func)

        Function decorator that ensures a view is only accessible by authenticated
        users.  If the user is not authed they are redirected to the login view.

        .. note:: this decorator should be applied closest to the original view function
        
        .. code-block:: python
        
            @app.route('/private/')
            @auth.login_required
            def private():
                # this view is only accessible by logged-in users
                return render_template('private.html')    

        :param func: a view function to be marked as login-required
        :rtype: if the user is logged in, return the view as normal, otherwise
            returns a redirect to the login page
    
    .. py:method:: get_user_model()
    
        :rtype: Peewee model to use for persisting user data and authentication
    
    .. py:method:: get_model_admin([model_admin=None])
    
        Provide a :py:class:`ModelAdmin` class suitable for use with the User
        model.  Specifically addresses the need to re-hash passwords when changing
        them via the admin.
        
        The default implementation includes an override of the :py:meth:`ModelAdmin.save_model`
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

        :param model_admin: subclass of :py:class:`ModelAdmin` to use as the base class
        :rtype: a subclass of :py:class:`ModelAdmin` suitable for use with the ``User`` model
    
    .. py:method:: get_urls()
    
        A mapping of url to view.  The default implementation provides views for
        login and logout only, but you might extend this to add registration and
        password change views.
        
        Default implementation:
        
        .. code-block:: python
        
            def get_urls(self):
                return (
                    ('/logout/', self.logout),
                    ('/login/', self.login),
                )

        :rtype: a tuple of 2-tuples mapping url to view function.
    
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


The BaseUser mixin
^^^^^^^^^^^^^^^^^^

.. py:class:: BaseUser()

    Provides default implementations for password hashing and validation.  The
    auth framework requires two methods be implemented by the ``User`` model.  A
    default implementation of these methods is provided by the ``BaseUser`` mixin.

    .. py:method:: set_password(password)
        
        Encrypts the given password and stores the encrypted version on the model.
        This method is useful when registering a new user and storing the password,
        or modifying the password when a user elects to change.

    .. py:method:: check_password(password)

        Verifies if the given plaintext password matches the encrypted version stored
        on the model.  This method on the User model is called specifically by
        the :py:meth:`Auth.authenticate` method.
        
        :rtype: Boolean


Database
--------

.. py:class:: Database(app)

    The database wrapper provides integration between the peewee ORM and flask.
    It reads database configuration information from the flask app configuration
    and manages connections across requests.
    
    The db wrapper also provides a ``Model`` subclass which is configured to work
    with the database specified by the application's config.
    
    To configure the database specify a database engine and name:
    
    .. code-block:: python
        
        DATABASE = {
            'name': 'example.db',
            'engine': 'peewee.SqliteDatabase',
        }
    
    Here is an example of how you might use the database wrapper:
    
    .. code-block:: python
    
        # instantiate the db wrapper
        db = Database(app)
        
        # start creating models
        class Blog(db.Model):
            # this model will automatically work with the database specified
            # in the application's config.
            
    
    :param app: flask application to bind admin to

    .. py:attribute:: Model
    
        Model subclass that works with the database specified by the app's config


REST API
--------

.. py:class:: RestAPI(app[, prefix='/api'[, default_auth=None]])

    The :py:class:`RestAPI` acts as a container for the various :py:class:`RestResource`
    objects.  By default it binds all resources to ``/api/<model-name>/``.  Much like
    the :py:class:`Admin`, it is a centralized registry of resources.
    
    Example of creating a ``RestAPI`` instance for a flask app:
    
    .. code-block:: python
    
        from flask_peewee.rest import RestAPI
        
        from app import app # our project's Flask app
        
        # instantiate our api wrapper
        api = RestAPI(app)
        
        # register a model with the API
        api.register(SomeModel)
        
        # configure URLs
        api.setup()

    .. note:: Like the flask admin, the ``RestAPI`` has a ``setup()`` method which
        must be called after all resources have been registered.

    :param app: flask application to bind API to
    :param prefix: url to serve REST API from
    :param default_auth: default :py:class:`Authentication` type to use with registered resources
    
    .. py:method:: register(model[, provider=RestResource[, auth=None[, allowed_methods=None]]])
    
        Register a model to expose via the API.
        
        :param model: ``Model`` to expose via API
        :param provider: subclass of :py:class:`RestResource` to use for this model
        :param auth: authentication type to use for this resource, falling back to :py:attr:`RestAPI.default_auth`
        :param allowed_methods: ``list`` of HTTP verbs to allow, defaults to ``['GET', 'POST', 'PUT', 'DELETE']``
    
    .. py:method:: setup()
    
        Register the API ``BluePrint`` and configure urls.
        
        .. warning:: This must be called **after** registering your resources.


RESTful Resources and their subclasses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: RestResource

    Class that determines how a peewee ``Model`` is exposed by the Rest API.  Provides
    a way of encapsulating model-specific configuration and behaviors.  Provided
    when registering a model with the :py:class:`RestAPI` instance (see :py:meth:`RestAPI.register`).
    
    Example usage:
    
    .. code-block:: python
    
        # instantiate our api wrapper, passing in a reference to the Flask app
        api = RestAPI(app)

        # create a RestResource subclass
        class UserResource(RestResource):
            exclude = ('password', 'email',)
        
        # assume we have a "User" model, register it with the custom resource
        api.register(User, UserResource)

    .. py:attribute:: paginate_by = 20
    
        Determines how many results to return for a given API query.
        
        .. note:: *Fewer* results can be requested by specifying a ``limit``,
            but ``paginate_by`` is the upper bound.
    
    .. py:attribute:: fields = None
    
        A list or tuple of fields to expose when serializing
        
    .. py:attribute:: exclude = None
    
        A list or tuple of fields to **not** expose when serializing
    
    .. py:attribute:: ignore_filters = ('ordering', 'page', 'limit', 'key', 'secret',)
    
        A list or tuple of GET arguments to ignore when applying filters.  Generally
        these are special url arguments that have special meaning.
    
    .. py:method:: get_query()
    
        Returns the list of objects to be exposed by the API.  Provides an easy
        hook for restricting objects:
        
        .. code-block:: python
        
            class UserResource(RestResource):
                def get_query(self):
                    # only return "active" users
                    return self.model.select().where(active=True)
        
        :rtype: a ``SelectQuery`` containing the model instances to expose
    
    .. py:method:: prepare_data(obj, data)
    
        This method provides a hook for modifying outgoing data.  The default
        implementation no-ops, but you could do any kind of munging here.  The
        data returned by this method is passed to the serializer before being
        returned as a json response.
    
        :param obj: the object being serialized
        :param data: the dictionary representation of a model returned by the ``Serializer``
        :rtype: a dictionary of data to hand off
    
    .. py:method:: save_object(instance, raw_data)
    
        Persist the instance to the database.  The raw data supplied by the request
        is also available, but at the time this method is called the instance has
        already been updated and populated with the incoming data.
    
        :param instance: ``Model`` instance that has already been updated with the incoming ``raw_data``
        :param raw_data: data provided in the request
        :rtype: a saved instance
    
    .. py:method:: api_list()
    
        A view that dispatches based on the HTTP verb to either:
        
        * GET: :py:meth:`~RestResource.object_list`
        * POST: :py:meth:`~RestResource.create`
        
        :rtype: ``Response``
    
    .. py:method:: api_detail(pk)
    
        A view that dispatches based on the HTTP verb to either:
        
        * GET: :py:meth:`~RestResource.object_detail`
        * PUT: :py:meth:`~RestResource.edit`
        * DELETE: :py:meth:`~RestResource.delete`
        
        :rtype: ``Response``
    
    .. py:method:: object_list()
    
        Returns a serialized list of ``Model`` instances.  These objects may be
        filtered, ordered, and/or paginated.
        
        :rtype: ``Response``
    
    .. py:method:: object_detail()
    
        Returns a serialized ``Model`` instance.
        
        :rtype: ``Response``
    
    .. py:method:: create()
    
        Creates a new ``Model`` instance based on the deserialized POST body.
        
        :rtype: ``Response`` containing serialized new object
    
    .. py:method:: edit()
        
        Edits an existing ``Model`` instance, updating it with the deserialized PUT body.
        
        :rtype: ``Response`` containing serialized edited object
    
    .. py:method:: delete()
    
        Deletes an existing ``Model`` instance from the database.
        
        :rtype: ``Response`` indicating number of objects deleted, i.e. ``{'deleted': 1}``
    
    .. py:method:: get_api_name()
    
        :rtype: URL-friendly name to expose this resource as, defaults to the model's name
    
    .. py:method:: check_get([obj=None])
    
        A hook for pre-authorizing a GET request.  By default returns ``True``.
    
        :rtype: Boolean indicating whether to allow the request to continue
    
    .. py:method:: check_post()
    
        A hook for pre-authorizing a POST request.  By default returns ``True``.
    
        :rtype: Boolean indicating whether to allow the request to continue
    
    .. py:method:: check_put(obj)
    
        A hook for pre-authorizing a PUT request.  By default returns ``True``.
    
        :rtype: Boolean indicating whether to allow the request to continue
    
    .. py:method:: check_delete(obj)
    
        A hook for pre-authorizing a DELETE request.  By default returns ``True``.
    
        :rtype: Boolean indicating whether to allow the request to continue


.. py:class:: RestrictOwnerResource(RestResource)

    This subclass of :py:class:`RestResource` allows only the "owner" of an object
    to make changes via the API.  It works by verifying that the authenticated user
    matches the "owner" of the model instance, which is specified by setting :py:attr:`~RestrictOwnerResource.owner_field`.
    
    Additionally, it sets the "owner" to the authenticated user whenever saving
    or creating new instances.

    .. py:attribute:: owner_field = 'user'
    
        Field on the model to use to verify ownership of the given instance.
    
    .. py:method:: validate_owner(user, obj)
    
        :param user: an authenticated ``User`` instance
        :param obj: the ``Model`` instance being accessed via the API
        :rtype: Boolean indicating whether the user can modify the object
    
    .. py:method:: set_owner(obj, user)
    
        Mark the object as being owned by the provided user.  The default implementation
        simply calls ``setattr``.
    
        :param obj: the ``Model`` instance being accessed via the API
        :param user: an authenticated ``User`` instance


Authenticating requests to the API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: Authentication([protected_methods=None])

    Not to be confused with the ``auth.Authentication`` class, this class provides
    a single method, ``authorize``, which is used to determine whether to allow
    a given request to the API.
        
    :param protected_methods: A list or tuple of HTTP verbs to require auth for
    
    .. py:method:: authorize()
    
        This single method is called per-API-request.
        
        :rtype: Boolean indicating whether to allow the given request through or not


.. py:class:: UserAuthentication(auth[, protected_methods=None])

    Authenticates API requests by requiring the requesting user be a registered
    ``auth.User``.  Credentials are supplied using HTTP basic auth.
    
    Example usage:
    
    .. code-block:: python
    
        from auth import auth # import the Auth object used by our project

        from flask_peewee.rest import RestAPI, RestResource, UserAuthentication

        # create an instance of UserAuthentication
        user_auth = UserAuthentication(auth)

        # instantiate our api wrapper, specifying user_auth as the default
        api = RestAPI(app, default_auth=user_auth)

        # create a special resource for users that excludes email and password
        class UserResource(RestResource):
            exclude = ('password', 'email',)

        # register our models so they are exposed via /api/<model>/
        api.register(User, UserResource) # specify the UserResource

        # configure the urls
        api.setup()

    
    :param auth: an :ref:`authentication` instance
    :param protected_methods: A list or tuple of HTTP verbs to require auth for

    .. py:method:: authorize()
    
        Verifies, using HTTP Basic auth, that the username and password match a
        valid ``auth.User`` model before allowing the request to continue.
        
        :rtype: Boolean indicating whether to allow the given request through or not


.. py:class:: AdminAuthentication(auth[, protected_methods=None])

    Subclass of the :py:class:`UserAuthentication` that further restricts which
    users are allowed through.  The default implementation checks whether the
    requesting user is an "admin" by checking whether the admin attribute is set
    to ``True``.
    
    Example usage:
    
    .. code-block:: python
    
    Authenticates API requests by requiring the requesting user be a registered
    ``auth.User``.  Credentials are supplied using HTTP basic auth.
    
    Example usage:
    
    .. code-block:: python
    
        from auth import auth # import the Auth object used by our project

        from flask_peewee.rest import RestAPI, RestResource, UserAuthentication, AdminAuthentication

        # create an instance of UserAuthentication and AdminAuthentication
        user_auth = UserAuthentication(auth)
        admin_auth = AdminAuthentication(auth)

        # instantiate our api wrapper, specifying user_auth as the default
        api = RestAPI(app, default_auth=user_auth)

        # create a special resource for users that excludes email and password
        class UserResource(RestResource):
            exclude = ('password', 'email',)

        # register our models so they are exposed via /api/<model>/
        api.register(SomeModel)
        
        # specify the UserResource and require the requesting user be an admin
        api.register(User, UserResource, auth=admin_auth)

        # configure the urls
        api.setup()

    .. py:method:: verify_user(user)
    
        Verifies whether the requesting user is an administrator
    
        :param user: the ``auth.User`` instance of the requesting user
        :rtype: Boolean indicating whether the user is an administrator


.. py:class:: APIKeyAuthentication(model, protected_methods=None)

    Subclass that allows you to provide an API Key model to authenticate requests
    with.
    
    .. note:: Must provide an API key model with at least the following two
        fields:
        
        * key
        * secret
    
    
    .. code-block:: python
    
        # example API key model
        class APIKey(db.Model):
            key = CharField()
            secret = CharField()
            user = ForeignKeyField(User)
        
        # instantiating the auth
        api_key_auth = APIKeyAuthentication(model=APIKey)

    :param model: a :py:class:`Database.Model` subclass to persist API keys.
    :param protected_methods: A list or tuple of HTTP verbs to require auth for


Utilities
---------

.. py:function:: get_object_or_404(query_or_model, **query)

    Given any number of keyword arguments, retrieve a single instance of the
    ``query_or_model`` parameter or return a 404
    
    :param query_or_model: either a ``Model`` class or a ``SelectQuery``
    :param **query: any number of keyword arguments, e.g. ``id=1``
    :rtype: either a single model instance or raises a ``NotFound`` (404 response)

.. py:function:: object_list(template_name, qr[, var_name='object_list'[, **kwargs]])

    Returns a rendered template, passing in a paginated version of the query.
    
    :param template_name: a string representation of a path to a template
    :param qr: a ``SelectQuery``
    :param var_name: context variable name to use when rendering the template
    :param **kwargs: any arbitrary keyword arguments to pass to the template during rendering
    :rtype: rendered ``Response``

.. py:function:: get_next()

    :rtype: a URL suitable for redirecting to

.. py:function:: slugify(s)

    Use a regular expression to make arbitrary string ``s`` URL-friendly

    :param s: any string to be slugified
    :rtype: url-friendly version of string ``s``

.. py:class:: PaginatedQuery

    Wraps a ``SelectQuery`` with helpers for paginating.
    
    .. py:attribute:: page_var = 'page'
    
        GET argument to use for determining request page
    
    .. py:method:: __init__(query_or_model, paginate_by)
    
        :param query_or_model: either a ``Model`` class or a ``SelectQuery``
        :param paginate_by: number of results to return per-page
    
    .. py:method:: get_list()
    
        :rtype: a list of objects for the request page
    
    .. py:method:: get_page()
    
        :rtype: an integer representing the currently requested page
    
    .. py:method:: get_pages()
    
        :rtype: the number of pages in the entire result set
