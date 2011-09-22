.. _rest-api:

REST Api
========

flask-peewee comes with some tools for exposing your project's models via a
RESTful API.  There are several components to the ``rest`` module, but the basic
setup is to create an instance of :py:class:`RestAPI` and then register your
project's models with subclasses of :py:class:`RestResource`.

Each :py:class:`RestResource` you expose via the API will support, by default,
the following:

* `/api/<model name>/` -- GET and POST requests
* `/api/<model name>/<primary key>/` -- GET, PUT and DELETE requests

Also, you can filter results by columns on the model using django-style syntax,
for example:

* `/api/blog/?name=Some%20Blog`
* `/api/blog/?author__username=some_blogger`


Getting started with the API
----------------------------

In this documentation we'll start with a very simple API and build it out.  The
complete version of this API is included in the :ref:`example-app`, so feel free
to refer there.

The project will be a simple 'twitter-like' app where users can post short messages
and "follow" other users.


Project models
^^^^^^^^^^^^^^

There are three main models - ``User``, ``Relationship`` and ``Message`` - which
we will expose via the API.  Here is a truncated version of what they look like:

.. code-block:: python

    class User(db.Model):
        username = CharField()
        password = CharField()
        email = CharField()
        join_date = DateTimeField(default=datetime.datetime.now)
        active = BooleanField(default=True)
        admin = BooleanField(default=False)
    
    class Relationship(db.Model):
        from_user = ForeignKeyField(User, related_name='relationships')
        to_user = ForeignKeyField(User, related_name='related_to')
    
    class Message(db.Model):
        user = ForeignKeyField(User)
        content = TextField()
        pub_date = DateTimeField(default=datetime.datetime.now)


Creating a RestAPI
^^^^^^^^^^^^^^^^^^

The :py:class:`RestAPI` acts as a container for the various :py:class:`RestResource`
objects we will expose.  By default it binds all resources to ``/api/<model-name>/``.

Here we'll create a simple api and register our models:

.. code-block:: python

    from flaskext.rest import RestAPI
    
    from app import app # our project's Flask app
    
    # instantiate our api wrapper
    api = RestAPI(app)
    
    # register our models so they are exposed via /api/<model>/
    api.register(User)
    api.register(Relationship)
    api.register(Message)
    
    # configure the urls
    api.setup()


Now if we hit our project at ``/api/message/`` we should get something like the following:

.. code-block:: javascript

    {
      "meta": {
        "model": "message", 
        "next": "", 
        "page": 1, 
        "previous": ""
      }, 
      "objects": [
        {
          "content": "flask and peewee, together at last!", 
          "pub_date": "2011-09-16 18:36:15", 
          "user_id": 1, 
          "id": 1
        }, 
        {
          "content": "Hey, I'm just some user", 
          "pub_date": "2011-09-16 18:46:59", 
          "user_id": 2, 
          "id": 2
        }
      ]
    }

Say we're interested in the first message, we can hit ``/api/message/1/`` to view
just the details on that object:

.. code-block:: javascript

    {
      content: "flask and peewee, together at last!"
      pub_date: "2011-09-16 18:36:15"
      user_id: 1
      id: 1
    }


Customizing what is returned
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you access the ``User`` API endpoint, we quickly notice a problem:

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/user/
    
    {
      "meta": {
        "model": "user", 
        "next": "", 
        "page": 1, 
        "previous": ""
      }, 
      "objects": [
        {
          "username": "admin", 
          "admin": true, 
          "email": "", 
          "join_date": "2011-09-16 18:34:49", 
          "active": true, 
          "password": "d033e22ae348aeb5660fc2140aec35850c4da997", 
          "id": 1
        }, 
        {
          "username": "coleifer", 
          "admin": false, 
          "email": "coleifer@gmail.com", 
          "join_date": "2011-09-16 18:35:56", 
          "active": true, 
          "password": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3", 
          "id": 2
        }
      ]
    }

Passwords and email addresses are being exposed.  In order to exclude these fields
from serialization, subclass :py:class:`RestResource`:

.. code-block:: python

    from flaskext.rest import RestAPI, RestResource
    
    from app import app # our project's Flask app
    
    # instantiate our api wrapper
    api = RestAPI(app)
    
    # create a special resource for users that excludes email and password
    class UserResource(RestResource):
        exclude = ('password', 'email',)

    # register our models so they are exposed via /api/<model>/
    api.register(User, UserResource) # specify the UserResource
    api.register(Relationship)
    api.register(Message)

Now emails and passwords are no longer returned by the API.


Allowing users to post messages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

What if we want to create new messages via the Api?  Or modify/delete existing messages?

.. code-block:: console

    $ curl -i -d '' http://127.0.0.1:5000/api/message/
    
    HTTP/1.0 401 UNAUTHORIZED
    WWW-Authenticate: Basic realm="Login Required"
    Content-Type: text/html; charset=utf-8
    Content-Length: 21
    Server: Werkzeug/0.8-dev Python/2.6.6
    Date: Thu, 22 Sep 2011 16:14:21 GMT

    Authentication failed

The authentication failed because the default authentication mechanism only
allows read-only access.

In order to allow users to create messages via the API, we need to use a subclass
of :py:class:`Authentication` that allows ``POST`` requests.  We also want to ensure
that the requesting user is a member of the site.

For this we will use the :py:class:`UserAuthentication` class as the default auth
mechanism.

.. code-block:: python

    from auth import auth # import the Auth object used by our project
    
    from flaskext.rest import RestAPI, RestResource, UserAuthentication
    
    # create an instance of UserAuthentication
    user_auth = UserAuthentication(auth)

    # instantiate our api wrapper, specifying user_auth as the default
    api = RestAPI(app, default_auth=user_auth)
    
    # create a special resource for users that excludes email and password
    class UserResource(RestResource):
        exclude = ('password', 'email',)

    # register our models so they are exposed via /api/<model>/
    api.register(User, UserResource) # specify the UserResource
    api.register(Relationship)
    api.register(Message)
    
    # configure the urls
    api.setup()

Now we should be able to POST new messages.

.. code-block:: python

    import json
    import httplib2
    
    sock = httplib2.Http()
    sock.add_credentials('admin', 'admin') # use basic auth
    
    message = {'user_id': 1, 'content': 'hello api'}
    msg_json = json.dumps(message)
    
    headers, resp = sock.request('http://localhost:5000/api/message/', 'POST', body=msg_json)
    
    response = json.loads(resp)

The response object will look something like this:

.. code-block:: javascript

    {
      'content': 'hello api',
      'user_id': 1,
      'pub_date': '2011-09-22 11:25:02',
      'id': 3
    }

There is a problem with this, however.  Notice how the ``user_id`` was passed in
with the POST data?  This effectively will let a user post a message as another user.
It also means a user can use PUT requests to modify another user's message:

.. code-block:: python

    # continued from above script
    update = {'content': 'haxed you, bro'}
    update_json = json.dumps(update)
    
    headers, resp = sock.request('http://127.0.0.1:5000/api/message/2/', 'PUT', body=update_json)
    
    response = json.loads(resp)

The response will look like this:

.. code-block:: javascript

    {
      'content': 'haxed you, bro',
      'pub_date': '2011-09-16 18:36:15',
      'user_id': 2,
      'id': 2
    }

This is a problem -- we need a way of ensuring that users can only edit their
own messages.  Furthermore, when they create messages we need to make sure the
message is assigned to them.


Restricting API access on a per-model basis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

flask-peewee comes with a special subclass of :py:class:`RestResource` that
restricts POST/PUT/DELETE requests to prevent users from modifying another user's
content.

.. code-block:: python

    from flaskext.rest import RestrictOwnerResource


    class MessageResource(RestrictOwnerResource):
        owner_field = 'user'

    api.register(Message, MessageResource)

Now, if we try and modify the message, we get a 403 Forbidden:

.. code-block:: python

    headers, resp = sock.request('http://127.0.0.1:5000/api/message/2/', 'PUT', body=update_json)
    print headers['status']
    
    # prints 403

It is fine to modify our own message, though (message with id=1):

.. code-block:: python

    headers, resp = sock.request('http://127.0.0.1:5000/api/message/1/', 'PUT', body=update_json)
    print headers['status']
    
    # prints 200

Under-the-hood, the `implementation <https://github.com/coleifer/flask-peewee/blob/master/flaskext/rest.py#L284>`_ of the :py:class:`RestrictOwnerResource` is pretty simple.

* PUT / DELETE -- verify the authenticated user is the owner of the object
* POST -- assign the authenticated user as the owner of the new object


Locking down a resource
^^^^^^^^^^^^^^^^^^^^^^^

Suppose we want to restrict normal users from modifying ``User`` resources.  For this
we can use a special subclass of :py:class:`UserAuthentication` that restricts access
to administrators:

.. code-block:: python

    from flaskext.rest import AdminAuthentication
    
    # instantiate our user-based auth
    user_auth = UserAuthentication(auth)
    
    # instantiate admin-only auth
    admin_auth = AdminAuthentication(auth)

    # instantiate our api wrapper, specifying user_auth as the default
    api = RestAPI(app, default_auth=user_auth)
    
    # register the UserResource with admin auth
    api.register(User, UserResource, auth=admin_auth)


Filtering records and querying
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A REST Api is not very useful if it cannot be queried in a meaningful fashion.  To
this end, the flask-peewee :py:class:`RestResource` objects support "django-style"
filtering:

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/message/?user=2

This call will return only messages by the ``User`` with id=2:

.. code-block:: javascript

    {
      "meta": {
        "model": "message", 
        "next": "", 
        "page": 1, 
        "previous": ""
      }, 
      "objects": [
        {
          "content": "haxed you, bro", 
          "pub_date": "2011-09-16 18:36:15", 
          "user_id": 2, 
          "id": 2
        }
      ]
    }

Joins can be traversed using the django double-underscore notation:

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/message/?user__username=admin

.. code-block:: javascript

    {
      "meta": {
        "model": "message", 
        "next": "", 
        "page": 1, 
        "previous": ""
      }, 
      "objects": [
        {
          "content": "flask and peewee, together at last!", 
          "pub_date": "2011-09-16 18:36:15", 
          "user_id": 1, 
          "id": 1
        },
        {
          "content": "hello api",
          "pub_date": "2011-09-22 11:25:02",
          "user_id": 1,
          "id": 3
        }
      ]
    }


Sorting results
^^^^^^^^^^^^^^^

Results can be sorted by specifying an ``ordering`` as a GET argument.  The ordering
must be a column on the model.

`/api/messages/?ordering=pub_date`

If you would like to order objects "descending", place a "-" (hyphen character) before the column name:

`/api/messages/?ordering=-pub_date`


Limiting results and pagination
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, resources are paginated 20 per-page.  If you want to return less, you
can specify a ``limit`` in the querystring.

`/api/messages/?limit=2`

In the "meta" section of the response, URIs for the "next" and "previous" sets
of results are available:

.. code-block:: javascript

    meta: {
      model: "message"
      next: "/api/message/?limit=1&page=3"
      page: 2
      previous: "/api/message/?limit=1&page=1"
    }


Components of the rest module
-----------------------------

The ``rest`` module is broken up into three main components:

* :py:class:`RestAPI`, which organizes and exposes resources
* :py:class:`RestResource`, which represents a model
* :py:class:`Authentication`, which controls access to a given resource

RestAPI
^^^^^^^

.. py:class:: RestAPI

    .. py:method:: __init__(app[, prefix='/api'[, default_auth=None]])
    
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
    
        Register API ``BluePrint`` and configure urls
        
        .. warning::
            call this **after** registering your resources


RestResource and related classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A :py:class:`RestResource` is simply a ``Model`` that is exposed via the API, and
encapsulates any logic for restricting which instances to display, controlling
access to instances, etc.

.. py:class:: RestResource

    .. py:attribute:: paginate_by = 20
    
    .. py:attribute:: fields = None
    
        A list or tuple of fields to expose when serializing
        
    .. py:attribute:: exclude = None
    
        A list or tuple of fields to **not** expose when serializing
    
    .. py:attribute:: ignore_filters = ('ordering', 'page', 'limit',)
    
        A list or tuple of GET arguments to ignore when applying filters
    
    .. py:method:: get_query()
    
        :rtype: a ``SelectQuery`` containing the model instances to expose by default
    
    .. py:method:: prepare_data(data)
    
        This method provides a hook for modifying outgoing data.  The default
        implementation no-ops, but you could do any kind of munging here.
    
        :param data: the dictionary representation of a model returned by the ``Serializer``
        :rtype: a dictionary of data to hand off
    
    .. py:method:: save_object(instance, raw_data)
    
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


Authentication
^^^^^^^^^^^^^^

The :py:class:`Authentication` class controls access to :py:class:`RestResource` instances.
The default implementation, which is used if no other auth type is specified, simply
blocks any HTTP request other than a GET:

.. code-block:: python

    class Authentication(object):
        def __init__(self, protected_methods=None):
            if protected_methods is None:
                protected_methods = ['POST', 'PUT', 'DELETE']
            
            self.protected_methods = protected_methods
        
        def authorize(self):
            if request.method in self.protected_methods:
                return False
            
            return True

.. py:class:: Authentication

    .. py:method:: __init__([protected_methods=None])
        
        :param protected_methods: A list or tuple of HTTP verbs to require auth for
    
    .. py:method:: authorize()
    
        This single method is called per-API-request.
        
        :rtype: Boolean indicating whether to allow the given request through or not


.. py:class:: UserAuthentication(Authentication)

    .. py:method:: __init__(auth[, protected_methods=None])
    
        :param auth: an :ref:`authentication` instance
        :param protected_methods: A list or tuple of HTTP verbs to require auth for

    .. py:method:: authorize()
    
        Verifies, using HTTP Basic auth, that the username and password match a
        valid ``auth.User`` model before allowing the request to continue.
        
        :rtype: Boolean indicating whether to allow the given request through or not


.. py:class:: AdminAuthentication(UserAuthentication)

    Subclass of the :py:class:`UserAuthentication` that further restricts which
    users are allowed through.

    .. py:method:: verify_user(user)
    
        Verifies whether the requesting user is an administrator
    
        :param user: the ``auth.User`` instance of the requesting user
        :rtype: Boolean indicating whether the user is an administrator
