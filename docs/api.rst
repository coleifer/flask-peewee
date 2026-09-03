.. _api:

API
===

Admin
-----

.. py:class:: Admin(app, auth[, prefix[, name[, branding[, theme]]]])

    Class used to expose an admin area at a certain url in your application. The
    Admin object implements a flask blueprint and is the central registry
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
    :param prefix: url to bind admin to, defaults to ``/admin``
    :param name: name of the admin blueprint, defaults to ``admin``
    :param branding: display name shown in the navbar and page titles
    :param theme: name of an admin theme stylesheet. ``'<theme>'`` loads
        ``static/css/admin-<theme>.css`` on top of the base ``admin.css``,
        e.g. ``theme='crisp'``. Defaults to ``None``, which serves the base
        stylesheet only. For full control (e.g. a stylesheet hosted outside
        the admin's static folder), override the ``theme_css`` block in
        ``admin/base.html`` instead.

    .. py:method:: register(model[, admin_class=ModelAdmin])

        Register a model to expose in the admin area. A :py:class:`ModelAdmin`
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

    .. py:method:: register_panel(title, panel, *args, **kwargs)

        Register a :py:class:`AdminPanel` subclass for display in the admin
        dashboard. Extra arguments are passed through to the panel's
        constructor.

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
        Flask application. Use this method when you have finished registering
        all the models and panels with the admin object, but before starting
        the WSGI application. For a sample implementation, check out ``main.py``
        in the `example application
        <https://github.com/coleifer/flask-peewee/tree/master/example>`_ supplied
        with flask-peewee.

        .. code-block:: python

            # register all models, etc
            admin.register(BlogModel)

            # finish up initialization of the admin object
            admin.setup()

            if __name__ == '__main__':
                # run the WSGI application
                app.run()

        .. note::
            call ``setup()`` after registering your models and panels

    .. py:method:: check_user_permission(user)

        Check whether the given user has permission to access the admin area. The
        default implementation checks whether the ``admin`` field is set,
        but you can provide your own logic.

        This method controls access to the admin area as a whole. In the
        event the user is not permitted to access the admin (this function
        returns ``False``), they will receive a HTTP Response Forbidden (403).

        Default implementation:

        .. code-block:: python

            def check_user_permission(self, user):
                return user.admin

        :param user: the currently logged-in user, exposed by the :py:class:`Auth` instance
        :rtype: Boolean

    .. py:method:: auth_required(func)

        Decorator that ensures the requesting user has permission. The implementation
        first checks whether the requesting user is logged in, and if not redirects
        to the login view. If the user is logged in, it calls :py:meth:`~Admin.check_user_permission`.
        Only if this call returns ``True`` is the actual view function called.

    .. py:method:: get_urls()

        Get a tuple of 2-tuples mapping urls to view functions that will be
        exposed by the admin. The default implementation looks like this:

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

    Class that determines how a peewee ``Model`` is exposed in the admin area. Provides
    a way of encapsulating model-specific configuration and behaviors. Provided
    when registering a model with the :py:class:`Admin` instance (see :py:meth:`Admin.register`).

    .. py:attribute:: columns

        List or tuple of columns should be displayed in the list index. By default if no
        columns are specified the ``Model``'s ``__str__()`` will be used.

        .. note::

            Valid values for columns are the following:

            * field on a model
            * attribute on a model instance
            * callable on a model instance (called with no parameters)
            * method on the ``ModelAdmin`` (called with the model instance)

            If a column is a model field, it will be sortable.

        .. code-block:: python

            class EntryAdmin(ModelAdmin):
                columns = ['title', 'pub_date', 'blog']

    .. py:attribute:: filter_exclude

        Exclude certain fields from being exposed as filters. Related fields can
        be excluded using "__" notation, e.g. ``user__password``

    .. py:attribute:: filter_fields

        Only allow filtering on the given fields

    .. py:attribute:: max_filter_depth = 3

        How many foreign-key hops the filter and export field trees may
        traverse into related models

    .. py:attribute:: search_fields

        Char/text field names for the quick-search box, with ``__`` traversal
        into related models. Empty (the default) hides the search box

    .. py:attribute:: foreign_key_lookups

        Mapping of foreign-key field name to the related field to search and
        display on, e.g. ``{'user': 'username'}``. Replaces the plain
        ``<select>`` with a paginated type-ahead picker

    .. py:attribute:: actions

        List of :py:class:`Action` instances to offer in the list view's
        "With selected..." dropdown

    .. py:attribute:: export_fields

        Whitelist of field names that may be exported

    .. py:attribute:: export_exclude

        Blacklist of field names withheld from export. Related models are
        restricted by their own registered ModelAdmin's settings

    .. py:attribute:: exclude

        A list of field names to exclude from the "add" and "edit" forms

    .. py:attribute:: fields

        Only display the given fields on the "add" and "edit" form

    .. py:attribute:: field_args = None

        Per-field keyword arguments passed through to wtf-peewee's
        ``model_form``, e.g. ``{'content': {'label': 'Body'}}``. See
        :ref:`admin-interface` for form customization recipes.

    .. py:attribute:: readonly_fields

        List or tuple of field names to display without editing. Readonly
        fields are removed from the generated form entirely, so they can
        never be posted. The edit page renders them as inert values and
        the add page omits them.

    .. py:attribute:: fieldsets

        List of ``(label, options)`` tuples grouping the add and edit forms
        into sections, rendered in order. ``options`` is a dict with a
        ``fields`` list and an optional ``collapsed`` flag. A ``None`` label
        renders an unlabeled section, and fields missing from every section
        render in a trailing unlabeled one.

    .. py:attribute:: paginate_by = 20

        Number of records to display on index pages

    .. py:attribute:: paginate_count = True

        Set to ``False`` to skip ``COUNT()`` queries on huge tables. The list
        view then paginates with previous/next links alone, and the dashboard
        and tab record counts are hidden

    .. py:attribute:: filter_paginate_by = 15

        Default pagination when filtering in a modal dialog

    .. py:attribute:: delete_collect_objects = True

        Collect and display a list of "dependencies" when deleting

    .. py:attribute:: delete_recursive = True

        Delete "dependencies" recursively

    .. py:attribute:: can_add = True

        Allow new instances to be added through the admin

    .. py:attribute:: can_edit = True

        Allow instances to be edited through the admin

    .. py:attribute:: can_delete = True

        Allow instances to be deleted through the admin

    .. py:method:: get_query()

        Determines the list of objects that will be exposed in the admin. By
        default this will be all objects, but you can use this method to further
        restrict the query.

        This method is called within the context of a request, so you can access
        the ``Flask.request`` object or use the :py:class:`Auth` instance to
        determine the currently-logged-in user.

        Here's an example showing how the query is restricted based on whether
        the given user is a "super user" or not:

        .. code-block:: python

            class UserAdmin(ModelAdmin):
                def get_query(self):
                    # ask the auth system for the currently logged-in user
                    current_user = self.admin.auth.get_logged_in_user()

                    # if they are not a superuser, only show them their own
                    # account in the admin
                    if not current_user.is_superuser:
                        return User.select().where(User.id==current_user.id)

                    # otherwise, show them all users
                    return User.select()

        :rtype: A ``SelectQuery`` that represents the list of objects to expose

    .. py:method:: get_object(pk)

        This method retrieves the object matching the given primary key. The
        implementation uses :py:meth:`~ModelAdmin.get_query` to retrieve the
        base list of objects, then queries within that for the given primary key.

        :rtype: The model instance with the given pk, raising a ``DoesNotExist``
                in the event the model instance does not exist.

    .. py:method:: get_form([adding=False])

        Provides a useful extension point in the event you want to define custom
        fields or custom validation behavior.

        :param boolean adding: indicates whether adding a new instance or editing existing
        :rtype: A `wtf-peewee <https://github.com/coleifer/wtf-peewee>`_ Form subclass that
                will be used when adding or editing model instances in the admin.

    .. py:method:: get_add_form()

        Allows you to specify a different form when adding new instances versus
        editing existing instances. The default implementation calls
        :py:meth:`~ModelAdmin.get_form`.

    .. py:method:: get_edit_form(instance)

        Allows you to specify a different form when editing existing instances versus
        adding new instances. Receives the instance being edited. The default
        implementation calls :py:meth:`~ModelAdmin.get_form`.

    .. py:method:: get_filter_form()

        Provide a special form for use when filtering the list of objects in the model admin's
        index/export views. This form is slightly different in that it is tailored for use
        when filtering the list of models.

        :rtype: A special Form instance (:py:class:`FilterForm`) that will be used
                when filtering the list of objects in the index view.

    .. py:method:: save_model(instance, form, adding=False)

        Method responsible for persisting changes to the database. Called by both
        the add and the edit views.

        Here is the implementation from the default ``auth.User``
        :py:class:`ModelAdmin`, which re-hashes a changed password before the
        single save so the raw password is never written to the database:

        .. code-block:: python

            def save_model(self, instance, form, adding=False):
                orig_password = instance.password
                form.populate_obj(instance)

                if form.password.data != orig_password:
                    instance.set_password(form.password.data)

                instance.save(force_insert=adding)
                return instance

        :param instance: an unsaved model instance
        :param form: a validated form instance
        :param adding: boolean to indicate whether we are adding a new instance
                or saving an existing

    .. py:method:: check_add(user)

        Returns whether ``user`` may add instances, checking
        :py:attr:`~ModelAdmin.can_add` by default. Denials abort the add
        view with a 403, and the templates hide the corresponding links.

        :rtype: boolean

    .. py:method:: check_edit(user)

        Returns whether ``user`` may edit instances, checking
        :py:attr:`~ModelAdmin.can_edit` by default. Checked in the edit
        view before the row is fetched. Override for user-aware rules:

        .. code-block:: python

            class PageAdmin(ModelAdmin):
                def check_edit(self, user):
                    return user.username == 'admin'

        :rtype: boolean

    .. py:method:: check_delete(user)

        Returns whether ``user`` may delete instances, checking
        :py:attr:`~ModelAdmin.can_delete` by default. Enforced in the
        delete views and in the index delete action.

        :rtype: boolean

    .. py:method:: get_template_overrides()

        Hook for specifying template overrides. Should return a dictionary containing
        view names as keys and template names as values. Possible choices for keys are:

        * index
        * add
        * edit
        * delete
        * action_confirm
        * export

        .. code-block:: python

            class UserModelAdmin(ModelAdmin):
                def get_template_overrides(self):
                    return {'index': 'users/admin/index_override.html'}

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

    .. py:method:: process_filters(query)

        Applies any filters specified by the user to the given query, returning
        metadata about the filters.

        Returns a 4-tuple containing:

        * special ``Form`` instance containing fields for filtering
        * filtered query
        * a list containing the currently selected filters
        * a tree-structure containing the fields available for filtering (:py:class:`FieldTreeNode`)

        :rtype: A tuple as described above


Bulk actions with Action
^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: Action([name=None[, description=None[, confirm=False[, form_class=None]]]])

    A custom bulk operation offered in the list view's "With selected..."
    dropdown. Subclass it, implement :py:meth:`~Action.callback`, and list
    an instance in :py:attr:`ModelAdmin.actions`. See :ref:`admin-interface`
    for worked examples.

    :param name: dropdown label, defaults to the class name minus the
        "Action" suffix
    :param description: heading shown on the confirmation page and in the
        success message, defaults to a title-cased version of ``name``
    :param confirm: when ``True``, run the callback only after the user
        approves a confirmation page listing the selected rows
    :param form_class: a wtforms form class to render on the confirmation
        page. Setting it implies confirmation.

    .. py:method:: callback(id_list[, form])

        Perform the action on the selected rows. Receives the primary keys
        the user checked, restricted to those matching
        :py:meth:`ModelAdmin.get_query`. When ``form_class`` is set, the
        validated form is passed as a second argument.

        If the return value is a flask ``Response``, it is sent to the user
        as-is. Any other return value redirects back to the list view.


Extending admin functionality using AdminPanel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: AdminPanel

    Class that provides a simple interface for providing arbitrary extensions to
    the admin. These are displayed as "panels" on the admin dashboard with a customizable
    template. They may additionally, however, define any views and urls. These
    views will automatically be protected by the same authentication used throughout
    the admin area. See :ref:`admin-interface` for example use-cases and a
    worked panel.

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

        Return the template used to render this panel in the dashboard. By default
        returns the template stored under :py:attr:`AdminPanel.template_name`.

    .. py:method:: get_context()

        Return the context to be used when rendering the dashboard template.

        :rtype: Dictionary

    .. py:method:: render()

        Render the panel template with the context. This is what gets displayed
        in the admin dashboard.

``flask_peewee.panels`` ships one ready-made subclass.

.. py:class:: RecentRowsPanel(admin, title, model[, columns[, limit[, order_by]]])

    Display the newest rows of ``model``. See :ref:`admin-interface`.


Auth
----

.. py:class:: Auth(app, db[, user_model[, prefix[, name[, clear_session[, default_next_url[, db_table[, reset]]]]]]])

    The class that provides methods for authenticating users and tracking
    users across requests. It also provides a model for persisting users to
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
    ``setup()`` method call when using the Auth system. Creation of the auth
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
    :param prefix: url to bind authentication views to, defaults to ``/accounts``
    :param name: name of the auth blueprint, defaults to ``auth``
    :param clear_session: wipe the entire session on logout, rather than just
        the auth keys
    :param default_next_url: where to redirect after login or logout when no
        ``?next=`` is given, defaults to ``/``
    :param db_table: table name for the default ``User`` model (``user`` is a
        reserved word in postgres)
    :param reset: enable the ``/forgot/`` and ``/reset/<token>/`` password
        reset views (requires overriding :py:meth:`Auth.send_reset_email`)

    .. py:attribute:: default_next_url = '/'

        The url to redirect to upon successful login in the event a ``?next=<xxx>``
        is not provided.

    .. py:attribute:: reset_token_max_age = 3600

        Number of seconds a password reset token remains valid.

    .. py:method:: get_logged_in_user()

        .. note:: Since this method relies on the session storage to
            track users across requests, this method must be called while
            within a ``RequestContext``.

        :rtype: returns the currently logged-in ``User``, or ``None`` if session is anonymous

    .. py:method:: login_required(func)

        Function decorator that ensures a view is only accessible by authenticated
        users. If the user is not authed they are redirected to the login view.

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
        model. Specifically addresses the need to re-hash passwords when changing
        them via the admin.

        The default implementation overrides :py:meth:`ModelAdmin.save_model`
        to hash a changed password before the save:

        .. code-block:: python

            class UserAdmin(model_admin):
                columns = ['username', 'email', 'active', 'admin']
                export_exclude = ('password',)

                def save_model(self, instance, form, adding=False):
                    orig_password = instance.password
                    form.populate_obj(instance)

                    if form.password.data != orig_password:
                        instance.set_password(form.password.data)

                    instance.save(force_insert=adding)
                    return instance

        ``password`` is added to the ``export_exclude`` of the ``model_admin``
        passed in, along with the ``session_field`` when one is configured.
        Its ``columns`` are used as-is.

        :param model_admin: subclass of :py:class:`ModelAdmin` to use as the base class
        :rtype: a subclass of :py:class:`ModelAdmin` suitable for use with the ``User`` model

    .. py:method:: get_urls()

        A mapping of url to view. The default implementation provides views for
        login and logout, plus the forgot and reset views when password reset
        is enabled. You might extend this to add registration or password
        change views.

        Default implementation:

        .. code-block:: python

            def get_urls(self):
                urls = (
                    ('/logout/', self.logout),
                    ('/login/', self.login),
                )
                if self.reset_enabled:
                    urls += (
                        ('/forgot/', self.forgot),
                        ('/reset/<token>/', self.reset),
                    )
                return urls

        :rtype: a tuple of 2-tuples mapping url to view function.

    .. py:method:: get_login_form()

        :rtype: a ``wtforms.Form`` subclass to use for retrieving any user info required for login

    .. py:method:: get_forgot_form()

        :rtype: a ``wtforms.Form`` subclass used by the forgot view to collect the email address

    .. py:method:: get_reset_form()

        :rtype: a ``wtforms.Form`` subclass used by the reset view to collect the new password

    .. py:method:: authenticate(username, password)

        Given the ``username`` and ``password``, retrieve the user with the matching
        credentials if they exist. No exceptions should be raised by this method.

        :rtype: ``User`` model if successful, otherwise ``False``

    .. py:method:: login_user(user)

        Mark the given user as "logged-in". In the default implementation, this
        entails storing data in the ``Session`` to indicate the successful login.

        :param user: ``User`` instance

    .. py:method:: logout_user()

        Mark the requesting user as logged-out, removing the auth keys from
        the session (or the whole session with ``clear_session``)

    .. py:method:: get_reset_user(form)

        Find the user a reset link should be sent to. The default
        implementation matches the submitted email address against active
        users.

        :param form: the validated forgot-password form
        :rtype: ``User`` instance, or ``None`` if no active user matched

    .. py:method:: make_reset_token(user)

        Create a signed reset token for the given user. The token embeds the
        user's primary key and is bound to their current password hash, so
        changing the password invalidates outstanding tokens.

        :param user: ``User`` instance
        :rtype: url-safe token string

    .. py:method:: send_reset_email(user, reset_url)

        Deliver the reset link to the user. The default implementation raises
        ``NotImplementedError``, so enabling ``reset=True`` means overriding
        this method.

        :param user: ``User`` instance the reset was requested for
        :param reset_url: absolute url containing the signed reset token

    .. py:method:: parse_reset_token(token)

        Validate a token produced by :py:meth:`Auth.make_reset_token`.

        :rtype: the matching active ``User``, or ``None`` if the token is
            invalid, expired, or issued before a password change


The BaseUser mixin
^^^^^^^^^^^^^^^^^^

.. py:class:: BaseUser()

    Provides default implementations for password hashing and validation. The
    auth framework requires two methods be implemented by the ``User`` model. A
    default implementation of these methods is provided by the ``BaseUser`` mixin.

    .. py:method:: set_password(password)

        Encrypts the given password and stores the encrypted version on the model.
        This method is useful when registering a new user and storing the password,
        or modifying the password when a user elects to change.

    .. py:method:: check_password(password)

        Verifies if the given plaintext password matches the encrypted version stored
        on the model. This method on the User model is called specifically by
        the :py:meth:`Auth.authenticate` method.

        :rtype: Boolean


Database
--------

.. py:class:: Database([app=None[, database=None]])

    The database wrapper provides integration between the peewee ORM and flask.
    It reads database configuration information from the flask app configuration
    and manages connections across requests.

    The db wrapper also provides a ``Model`` subclass which is configured to work
    with the database specified by the application's config.

    :param app: a ``Flask`` instance or ``None`` (for deferred initialization).
    :param database: a peewee database instance or ``None``. If None then the
        database can be configured via the ``app.config`` settings.

    To configure the database specify a database engine and name:

    .. code-block:: python

        DATABASE = {
            'name': 'example.db',
            'engine': 'peewee.SqliteDatabase',
        }

    The database may also be given as a connection URL, using any scheme
    ``playhouse.db_url`` understands, or as a pre-configured peewee
    database instance (a ``Proxy`` works too):

    .. code-block:: python

        DATABASE = 'sqlite:///example.db'

        DATABASE = PostgresqlDatabase('app', user='postgres')

    Here is an example of how you might use the database wrapper:

    .. code-block:: python

        # instantiate the db wrapper
        db = Database(app)

        # start creating models
        class Blog(db.Model):
            # this model will automatically work with the database specified
            # in the application's config.
            name = CharField()

    Here is how to defer initialization via ``init_app``:

    .. code-block:: python

        db = Database()

        class Blog(db.Model):
            name = CharField()  # ...

        # Some time later, we can initialize the database wrapper.
        app = Flask(__name__)
        app.config.update(DATABASE={'engine': 'peewee.SqliteDatabase',
                                    'name': 'example.db'})
        db.init_app(app)

        # Alternately, we can specify the peewee database instance directly:
        app = Flask(__name__)
        sqlite_db = SqliteDatabase('example.db')
        db.init_app(app, sqlite_db)

    .. py:method:: init_app(app[, database=None])

        :param app: a ``Flask`` instance.
        :param database: a peewee database instance or ``None``. If None then the
            database will be configured via the ``app.config`` settings.

        Initialize the Database wrapper with a Flask app you intend to use,
        optionally specifying a Peewee database instance. If ``database`` is
        None then the database will be loaded from ``app.config``.

    .. py:method:: get_models()

        Returns every model subclassing :py:attr:`~Database.Model`,
        including subclasses of subclasses. The :ref:`CLI <cli>` uses this
        for table creation and schema diffs.

        :rtype: list of Model classes

    .. py:attribute:: Model

        Model subclass that works with the database specified by the app's config


REST API
--------

.. py:class:: RestAPI(app[, prefix='/api'[, default_auth=None[, name='api']]])

    The :py:class:`RestAPI` holds the :py:class:`RestResource` objects. By
    default it binds all resources to ``/api/<model-name>/``. Much like
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
    :param name: the name for the API blueprint

    .. py:method:: register(model[, provider=RestResource[, auth=None[, allowed_methods=None]]])

        Register a model to expose via the API.

        :param model: ``Model`` to expose via API
        :param provider: subclass of :py:class:`RestResource` to use for this model
        :param auth: authentication type to use for this resource, falling back to :py:attr:`RestAPI.default_auth`
        :param allowed_methods: ``list`` of HTTP verbs to allow, defaults to ``['GET', 'POST', 'PUT', 'PATCH', 'DELETE']``

    .. py:method:: setup()

        Register the API ``BluePrint`` and configure urls.

        .. warning:: This must be called after registering your resources.


RESTful Resources and their subclasses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: RestResource(rest_api, model, authentication[, allowed_methods=None])

    Class that determines how a peewee ``Model`` is exposed by the Rest API. Provides
    a way of encapsulating model-specific configuration and behaviors. Provided
    when registering a model with the :py:class:`RestAPI` instance (see :py:meth:`RestAPI.register`).

    Should not be instantiated directly in most cases. Instead should be "registered" with
    a ``RestAPI`` instance.

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

        The default page size for a given API query.

        .. note:: A different page size can be requested by specifying a
            ``limit``. ``paginate_by`` is only the default, not a maximum.
            Use ``max_paginate_by`` to cap what a client may request.

    .. py:attribute:: max_paginate_by = None

        When set, caps the page size a client may request with ``limit``.

    .. py:attribute:: fields = None

        A list or tuple of fields to expose when serializing

    .. py:attribute:: exclude = None

        A list or tuple of fields to omit when serializing

    .. py:attribute:: filter_exclude

        A list of fields that may never be used to filter API results

    .. py:attribute:: filter_fields

        A list of fields that can be used to filter the API results

    .. py:attribute:: filter_recursive = False

        Make every column of a related model filterable through its foreign
        key. Off by default, since a filter reveals a column's value even when
        the column is not serialized. List related columns explicitly
        (``user__username``) instead

    .. py:attribute:: max_filter_depth = 3

        How many foreign-key hops filtering may traverse into related models

    .. py:attribute:: readonly_fields = None

        A list or tuple of field names that clients may never write. They are
        stripped from incoming ``POST``/``PUT`` payloads at every level,
        protecting against mass assignment. The primary key is always
        read-only.

    .. py:attribute:: reject_unknown_fields = False

        When ``True``, a write payload containing unrecognized keys is
        rejected with a 400 listing them, instead of the keys being silently
        ignored. Read-only fields are stripped, not rejected, and a foreign
        key may be written by field name or column name (``user`` / ``user_id``).

    .. py:attribute:: reject_unknown_filters = False

        When ``True``, a query-string filter that matches no filterable field
        is rejected with a 400 naming it, instead of being silently ignored.
        Stray non-filter query parameters get the same 400, so enable this
        only for APIs whose clients send clean query strings.

    .. py:attribute:: include_resources

        A mapping of field name to resource class for handling of foreign-keys.
        When provided, foreign keys will be "nested".

        .. code-block:: python

            class UserResource(RestResource):
                exclude = ('password', 'email')

            class MessageResource(RestResource):
                include_resources = {'user': UserResource} # 'user' is a foreign key field

        .. code-block:: javascript

            /* messages without "include_resources" */
            {
              "content": "flask and peewee, together at last!",
              "pub_date": "2026-09-16T18:36:15",
              "id": 1,
              "user": 2
            },

            /* messages with "include_resources = {'user': UserResource} */
            {
              "content": "flask and peewee, together at last!",
              "pub_date": "2026-09-16T18:36:15",
              "id": 1,
              "user": {
                "username": "coleifer",
                "active": true,
                "join_date": "2026-09-16T18:35:56",
                "admin": false,
                "id": 2
              }
            }

    .. py:attribute:: nested_writes = True

        Whether a nested object in a write payload may create or update the
        related row. When ``False`` a nested object is ignored, though the
        foreign key may still be assigned by bare id.

    .. py:attribute:: allow_bulk = False

        When ``True``, POST also accepts a JSON list of objects, created in
        one transaction. An object that fails validation rolls the whole
        batch back with a 400 naming its index.

    .. py:attribute:: max_bulk = 100

        Maximum number of objects accepted in one bulk POST.

    .. py:attribute:: delete_recursive = True

        Recursively delete dependencies

    .. py:method:: get_query()

        Returns the list of objects to be exposed by the API. Provides an easy
        hook for restricting objects:

        .. code-block:: python

            class UserResource(RestResource):
                def get_query(self):
                    # only return "active" users
                    return self.model.select().where(self.model.active == True)

        :rtype: a ``SelectQuery`` containing the model instances to expose

    .. py:method:: prepare_data(obj, data)

        This method provides a hook for modifying outgoing data. The default
        implementation no-ops, but you could do any kind of munging here. The
        data returned by this method is passed to the serializer before being
        returned as a json response.

        :param obj: the object being serialized
        :param data: the dictionary representation of a model returned by the ``Serializer``
        :rtype: a dictionary of data to hand off

    .. py:method:: save_object(instance, raw_data)

        Persist the instance to the database. The raw data supplied by the request
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
        * PUT, PATCH or POST: :py:meth:`~RestResource.edit`
        * DELETE: :py:meth:`~RestResource.delete`

        ``POST /<pk>/delete/`` is also accepted as an alias for DELETE, for
        clients that cannot issue PUT or DELETE requests.

        :rtype: ``Response``

    .. py:method:: object_list()

        Returns a serialized list of ``Model`` instances. These objects may be
        filtered, ordered, and/or paginated.

        :rtype: ``Response``

    .. py:method:: object_detail()

        Returns a serialized ``Model`` instance.

        :rtype: ``Response``

    .. py:method:: create()

        Creates a new ``Model`` instance based on the deserialized POST body.

        :rtype: ``Response`` containing serialized new object

    .. py:method:: edit()

        Edits an existing ``Model`` instance, updating it with the deserialized
        PUT or PATCH body.

        :rtype: ``Response`` containing serialized edited object

    .. py:method:: delete()

        Deletes an existing ``Model`` instance from the database.

        :rtype: ``Response`` indicating number of objects deleted, i.e. ``{'deleted': 1}``

    .. py:method:: get_api_name()

        :rtype: URL-friendly name to expose this resource as, defaults to the model's name

    .. py:method:: get_urls()

        The url patterns the resource exposes, as a tuple of 2-tuples
        mapping url fragment to view. Extend to add custom endpoints
        alongside the standard list and detail views (see :ref:`rest-api`).

    .. py:method:: check_get([obj=None])

        A hook for pre-authorizing a GET request. By default returns ``True``.

        :rtype: Boolean indicating whether to allow the request to continue

    .. py:method:: check_post([obj=None])

        A hook for pre-authorizing a POST request. By default returns ``True``.
        ``obj`` is provided when the POST addresses an existing object (a
        detail-url edit or a nested write), and is ``None`` for a create.

        :rtype: Boolean indicating whether to allow the request to continue

    .. py:method:: check_put(obj)

        A hook for pre-authorizing a PUT request. By default returns ``True``.

        :rtype: Boolean indicating whether to allow the request to continue

    .. py:method:: check_patch(obj)

        A hook for pre-authorizing a PATCH request. Delegates to
        :py:meth:`~RestResource.check_put`, so overriding that covers both.

        :rtype: Boolean indicating whether to allow the request to continue

    .. py:method:: check_delete(obj)

        A hook for pre-authorizing a DELETE request. By default returns ``True``.

        :rtype: Boolean indicating whether to allow the request to continue


.. py:class:: RestrictOwnerResource(RestResource)

    This subclass of :py:class:`RestResource` allows only the "owner" of an object
    to make changes via the API. It works by verifying that the authenticated user
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

        Mark the object as being owned by the provided user. The default implementation
        calls ``setattr``.

        :param obj: the ``Model`` instance being accessed via the API
        :param user: an authenticated ``User`` instance


Authenticating requests to the API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:class:: Authentication([protected_methods=None])

    Not to be confused with the :py:class:`Auth` class in ``flask_peewee.auth``,
    this class provides a single method, ``authorize``, which is used to
    determine whether to allow a given request to the API.

    :param protected_methods: A list or tuple of HTTP verbs to require auth for

    .. py:method:: authorize()

        This single method is called per-API-request.

        :rtype: Boolean indicating whether to allow the given request through or not


.. py:class:: UserAuthentication(auth[, protected_methods=None])

    Authenticates API requests by requiring the requesting user be a registered
    ``auth.User``. Credentials are supplied using HTTP basic auth.

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
    users are allowed through. The default implementation checks whether the
    requesting user is an "admin" by checking whether the admin attribute is set
    to ``True``.

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


.. py:class:: BearerAuthentication(model[, protected_methods=None])

    Authenticates requests by a token in the ``Authorization: Bearer <token>``
    header, looked up in ``model``'s ``token`` field. The matched row is
    stored on ``g.api_key``. See :ref:`rest-api` for examples.

    :param model: model persisting the tokens
    :param protected_methods: A list or tuple of HTTP verbs to require auth for

    .. py:attribute:: token_field = 'token'

        Name of the column holding the token.

    .. py:method:: get_key(token)

        Look the token up and return the matching row, or ``None``. See
        :py:class:`HashedBearerAuthentication` for tokens hashed at rest.


.. py:class:: UserBearerAuthentication(model[, protected_methods=None])

    :py:class:`BearerAuthentication` that resolves the token to a user and
    sets ``g.user``, so it works with :py:class:`RestrictOwnerResource`. The
    token model carries a foreign key to the user in :py:attr:`user_field`.

    .. py:attribute:: user_field = 'user'

        Name of the token model's foreign key to the user. Set to ``None``
        when the token lives on the user model itself.


.. py:class:: HashedBearerAuthentication(model[, protected_methods=None])

    :py:class:`BearerAuthentication` for tokens stored hashed at rest, as
    created by :py:func:`make_token_model`. The presented token is hashed
    with sha256 and looked up in the ``token_hash`` column, skipping revoked
    and expired rows. The matching row is stored on ``g.api_key``, and
    ``g.user`` is set to the row's user when the model has a user foreign
    key.


.. py:function:: make_token_model(db, user_model=None, db_table='api_token')

    Create an ``ApiToken`` model bound to the given :py:class:`Database`
    wrapper, with ``token_hash``, ``created``, ``expires`` and ``revoked``
    columns, plus a foreign key to ``user_model`` when one is given. Its
    ``create_token(**kwargs)`` classmethod generates a token, stores only the
    sha256 hash (passing ``kwargs`` through to ``create()``), and returns
    ``(instance, raw_token)``.


.. py:data:: ALL_METHODS

    ``('GET', 'POST', 'PUT', 'PATCH', 'DELETE')``. Pass as ``protected_methods``
    to require authentication on reads as well as writes.


Utilities
---------

.. py:function:: get_object_or_404(query_or_model, *query)

    Provides a handy way of getting an object or 404ing if not found, useful
    for urls that match based on ID.

    :param query_or_model: a query or model to filter using the given expressions
    :param query: a list of query expressions

    .. code-block:: python

        @app.route('/blog/<title>/')
        def blog_detail(title):
            blog = get_object_or_404(Blog.select().where(Blog.active==True), Blog.title==title)
            return render_template('blog/detail.html', blog=blog)

.. py:function:: object_list(template_name, qr[, var_name='object_list'[, **kwargs]])

    Wraps the given query and handles pagination automatically. Pagination defaults to ``20``
    but can be changed by passing in ``paginate_by=XX``.

    :param template_name: template to render
    :param qr: a select query
    :param var_name: the template variable name to use for the paginated query
    :param kwargs: arbitrary context to pass in to the template

    .. code-block:: python

        @app.route('/blog/')
        def blog_list():
            active = Blog.select().where(Blog.active==True)
            return object_list('blog/index.html', active)

    .. code-block:: jinja

        <!-- template -->
        {% for blog in object_list %}
          {# render the blog here #}
        {% endfor %}

        {% if page > 1 %}
          <a href="./?page={{ page - 1 }}">Prev</a>
        {% endif %}
        {% if page < pagination.get_pages() %}
          <a href="./?page={{ page + 1 }}">Next</a>
        {% endif %}

.. py:function:: get_next()

    :rtype: a URL suitable for redirecting to

.. py:function:: slugify(s)

    Use a regular expression to make arbitrary string ``s`` URL-friendly

    :param s: any string to be slugified
    :rtype: url-friendly version of string ``s``

.. py:class:: PaginatedQuery(query_or_model, paginate_by[, use_count=True])

    A wrapper around a query (or model class) that handles pagination. Pass
    ``use_count=False`` to skip counting. :py:meth:`~PaginatedQuery.get_list`
    then fetches one extra row and sets :py:attr:`~PaginatedQuery.has_next`
    instead.

    .. py:attribute:: page_var = 'page'

        The URL variable used to store the current page

    .. py:attribute:: has_next

        Whether rows remain beyond the current page. Set by
        :py:meth:`~PaginatedQuery.get_list` when ``use_count=False``

    .. py:attribute:: max_page = 1000000

        Upper bound on the requested page when ``use_count=False`` and there
        is no page count to clamp to

    Example:

    .. code-block:: python

        query = Blog.select().where(Blog.active==True)
        pq = PaginatedQuery(query, 20)

        # assume url was /?page=3
        obj_list = pq.get_list()  # returns 3rd page of results

        pq.get_page() # returns 3

        pq.get_pages() # returns total objects / objects-per-page

    .. py:method:: get_list()

        :rtype: a list of objects for the request page

    .. py:method:: get_page()

        Clamped to the last page, so an out-of-range ``page`` does not
        overflow the query's ``OFFSET``.

        :rtype: an integer representing the currently requested page

    .. py:method:: get_pages()

        :rtype: the number of pages in the entire result set
