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

.. note:: If you're using apache with mod_wsgi and would like to use any of
    the auth backends that use basic auth, you will need to add the following
    directive: ``WSGIPassAuthorization On``


Project models
^^^^^^^^^^^^^^

There are three main models - ``User``, ``Relationship`` and ``Message`` - which
we will expose via the API.  Here is a truncated version of what they look like:

.. code-block:: python

    from flask_peewee.auth import BaseUser

    class User(db.Model, BaseUser):
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
------------------

The :py:class:`RestAPI` acts as a container for the various :py:class:`RestResource`
objects we will expose.  By default it binds all resources to ``/api/<model-name>/``.

Here we'll create a simple api and register our models:

.. code-block:: python

    from flask_peewee.rest import RestAPI
    
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
----------------------------

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

    from flask_peewee.rest import RestAPI, RestResource
    
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


Allowing users to post objects
------------------------------

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
-------------------------------------------

flask-peewee comes with a special subclass of :py:class:`RestResource` that
restricts POST/PUT/DELETE requests to prevent users from modifying another user's
content.

.. code-block:: python

    from flask_peewee.rest import RestrictOwnerResource


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

Under-the-hood, the `implementation <https://github.com/coleifer/flask-peewee/blob/master/flask_peewee/rest.py#L284>`_ of the :py:class:`RestrictOwnerResource` is pretty simple.

* PUT / DELETE -- verify the authenticated user is the owner of the object
* POST -- assign the authenticated user as the owner of the new object


Locking down a resource
-----------------------

Suppose we want to restrict normal users from modifying ``User`` resources.  For this
we can use a special subclass of :py:class:`UserAuthentication` that restricts access
to administrators:

.. code-block:: python

    from flask_peewee.rest import AdminAuthentication
    
    # instantiate our user-based auth
    user_auth = UserAuthentication(auth)
    
    # instantiate admin-only auth
    admin_auth = AdminAuthentication(auth)

    # instantiate our api wrapper, specifying user_auth as the default
    api = RestAPI(app, default_auth=user_auth)
    
    # register the UserResource with admin auth
    api.register(User, UserResource, auth=admin_auth)


Filtering records and querying
------------------------------

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

It is also supported to use different comparison operators with the same double-underscore notation:

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/user/?user__lt=2

.. code-block:: javascript

    {
      "meta": {
        "model": "user",
        "next": "",
        "page": 1,
        "previous": ""
        }, 
    "objects": [{
        "username": "admin",
        "admin": true,
        "email": "admin@admin",
        "active": true,
        "password": "214de$25",
        "id": 1
        }]
    }


Valid Comparison Operators are: 
    'eq', 'lt', 'lte', 'gt', 'gte', 'ne', 'in', 'is', 'like', 'ilike'


Sorting results
---------------

Results can be sorted by specifying an ``ordering`` as a GET argument.  The ordering
must be a column on the model.

`/api/message/?ordering=pub_date`

If you would like to order objects "descending", place a "-" (hyphen character) before the column name:

`/api/message/?ordering=-pub_date`


Limiting results and pagination
-------------------------------

By default, resources are paginated 20 per-page.  If you want to return less, you
can specify a ``limit`` in the querystring.

`/api/message/?limit=2`

In the "meta" section of the response, URIs for the "next" and "previous" sets
of results are available:

.. code-block:: javascript

    meta: {
      model: "message"
      next: "/api/message/?limit=1&page=3"
      page: 2
      previous: "/api/message/?limit=1&page=1"
    }
