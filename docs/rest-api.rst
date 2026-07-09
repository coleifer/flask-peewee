.. _rest-api:

REST API
========

flask-peewee comes with some tools for exposing your project's models via a
REST API.  There are several components to the ``rest`` module, but the basic
setup is to create an instance of :py:class:`RestAPI` and then register your
project's models with subclasses of :py:class:`RestResource`.

Each :py:class:`RestResource` you expose via the API will support, by default,
the following:

* ``/api/<model name>/`` -- GET and POST requests
* ``/api/<model name>/<primary key>/`` -- GET, PUT and DELETE requests

Also, you can filter results by columns on the model using django-style syntax,
for example:

* ``/api/blog/?name=Some%20Blog``
* ``/api/blog/?author__username=some_blogger``

Full operations:

* ``__eq``: equals
* ``__lt``: less-than
* ``__lte``: less-than or equal to
* ``__gt``: greater-than
* ``__gte``: greater-than or equal to
* ``__ne``: not equal to
* ``__in``: in set
* ``__is``: is, ``?field__is=None`` or ``?-field__is=None`` for NOT NULL
* ``__is_not``: is not, ``?field__is_not=None``
* ``__like``: wild-card matching, case-sensitive
* ``__ilike``: wild-card matching, case-insensitive
* ``__regexp``: regular-expression matching (database-specific)

To negate an operation, prefix it with the ``-`` character, e.g. the following
are equivalent:

* ``/api/user/?admin=true``
* ``/api/user/?admin__eq=true``
* ``/api/user/?-admin=false``
* ``/api/user/?admin__ne=false``

Special Python constants are supported when used as querystring parameters:

* ``?value=none`` translates the value to ``None``
* ``?value=true`` translates the value to ``True``
* ``?value=false`` translates the value to ``False``

Getting started with the API
----------------------------

In this documentation we'll start with a very simple API and build it out.  The
complete version of this API is included in the `example app
<https://github.com/coleifer/flask-peewee/tree/master/example>`_, so feel free
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
        from_user = ForeignKeyField(User, backref='relationships')
        to_user = ForeignKeyField(User, backref='related_to')

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
        "page_count": 1,
        "page": 1,
        "previous": ""
      },
      "objects": [
        {
          "content": "flask and peewee, together at last!",
          "pub_date": "2026-09-16T18:36:15",
          "user": 1,
          "id": 1
        },
        {
          "content": "Hey, I'm just some user",
          "pub_date": "2026-09-16T18:46:59",
          "user": 2,
          "id": 2
        }
      ]
    }

Say we're interested in the first message, we can hit ``/api/message/1/`` to view
just the details on that object:

.. code-block:: javascript

    {
      "content": "flask and peewee, together at last!",
      "pub_date": "2026-09-16T18:36:15",
      "user": 1,
      "id": 1
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
        "page_count": 1,
        "previous": ""
      },
      "objects": [
        {
          "username": "admin",
          "admin": true,
          "email": "",
          "join_date": "2026-09-16T18:34:49",
          "active": true,
          "password": "d033e22ae348aeb5660fc2140aec35850c4da997",
          "id": 1
        },
        {
          "username": "coleifer",
          "admin": false,
          "email": "coleifer@gmail.com",
          "join_date": "2026-09-16T18:35:56",
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

``exclude`` is a blacklist; its positive counterpart is ``fields``, a whitelist
of the *only* fields to serialize.  The resource above could instead expose just
the username and id:

.. code-block:: python

    class UserResource(RestResource):
        fields = ('username', 'id')

Reach for whichever is more convenient: ``fields`` when you want to expose a
small, fixed set of columns, ``exclude`` when you want everything but a few.


Nested resources
----------------

By default a foreign key is serialized as the related row's primary key.  Notice
the ``"user": 1`` in the message output above.  To embed the *full* related
object instead, point ``include_resources`` at the resource that should render it:

.. code-block:: python

    class UserResource(RestResource):
        exclude = ('password', 'email',)

    class MessageResource(RestResource):
        include_resources = {'user': UserResource}

    api.register(User, UserResource)
    api.register(Message, MessageResource)

Now each message embeds its author, serialized through ``UserResource`` (so the
password and email are still excluded):

.. code-block:: javascript

    {
      "content": "flask and peewee, together at last!",
      "pub_date": "2026-09-16T18:36:15",
      "user": {
        "username": "admin",
        "admin": true,
        "active": true,
        "join_date": "2026-09-16T18:34:49",
        "id": 1
      },
      "id": 1
    }

``include_resources`` can be nested arbitrarily deep -- an included resource may
itself include resources -- and one model can be embedded through more than one
foreign key.  For example, a ``Relationship`` resource can expand both endpoints:

.. code-block:: python

    class RelationshipResource(RestResource):
        include_resources = {
            'from_user': UserResource,
            'to_user': UserResource,
        }

The whole nested tree is loaded in a single query -- one ``JOIN`` per included
foreign key -- so embedding related objects does *not* incur the N+1 queries you
would get from following each row's relations lazily.

Nested writes
^^^^^^^^^^^^^

Included resources also work on the way *in*: a ``POST`` or ``PUT`` whose body
carries a nested object (instead of a bare id) creates or updates the related row
as part of the same request.  Two rules keep that safe:

* A resource's ``readonly_fields`` are stripped at **every** level of the
  payload, so a nested object cannot smuggle in a field the resource protects
  (e.g. slipping ``"admin": true`` into a nested user).
* Each nested write must pass the child resource's own ``check_post`` /
  ``check_put``, exactly as a direct write to that resource would, so nesting
  can never be used to sidestep a resource's authorization.

The entire object graph is saved in a single transaction, so if any nested write
is rejected the whole request rolls back.  To disable nested writes for a
resource -- silently ignoring any nested object in the payload -- set
``nested_writes = False``; the foreign key can still be assigned with a bare id.


Allowing users to post objects
------------------------------

What if we want to create new messages via the Api?  Or modify/delete existing messages?

.. code-block:: console

    $ curl -i -d '' http://127.0.0.1:5000/api/message/

    HTTP/1.1 401 UNAUTHORIZED
    WWW-Authenticate: Basic realm="Login Required"
    Content-Type: text/html; charset=utf-8

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

    import requests

    # authenticate with HTTP basic auth
    resp = requests.post(
        'http://localhost:5000/api/message/',
        json={'user': 1, 'content': 'hello api'},
        auth=('admin', 'admin'),
    )
    response = resp.json()

The response object will look something like this:

.. code-block:: javascript

    {
      'content': 'hello api',
      'user': 1,
      'pub_date': '2026-09-22T11:25:02',
      'id': 3
    }

There is a problem with this, however.  Notice how the ``user`` was passed in
with the POST data?  This effectively will let a user post a message as another user.
It also means a user can use PUT requests to modify another user's message:

.. code-block:: python

    # continued from above -- edit another user's message (id=2)
    resp = requests.put(
        'http://127.0.0.1:5000/api/message/2/',
        json={'content': 'haxed you, bro'},
        auth=('admin', 'admin'),
    )
    response = resp.json()

The response will look like this:

.. code-block:: javascript

    {
      'content': 'haxed you, bro',
      'pub_date': '2026-09-16T18:36:15',
      'user': 2,
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

    resp = requests.put(
        'http://127.0.0.1:5000/api/message/2/',
        json={'content': 'haxed you, bro'},
        auth=('admin', 'admin'),
    )
    print(resp.status_code)  # 403

It is fine to modify our own message, though (message with id=1):

.. code-block:: python

    resp = requests.put(
        'http://127.0.0.1:5000/api/message/1/',
        json={'content': 'haxed you, bro'},
        auth=('admin', 'admin'),
    )
    print(resp.status_code)  # 200

Under-the-hood, the `implementation <https://github.com/coleifer/flask-peewee/blob/master/flask_peewee/rest.py>`_ of the :py:class:`RestrictOwnerResource` is pretty simple.

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


Token-based authentication
--------------------------

:py:class:`UserAuthentication` and :py:class:`AdminAuthentication` use HTTP
Basic auth, which is handy for humans but awkward for programmatic clients.  For
API clients, flask-peewee ships token-based authentication classes.  Like all
authentication classes they only guard the ``protected_methods`` (``POST``,
``PUT`` and ``DELETE`` by default -- ``GET`` is open).  To require auth on reads
too, pass ``protected_methods=ALL_METHODS`` (a convenience constant equal to
``('GET', 'POST', 'PUT', 'DELETE')``) or your own list.

API keys
^^^^^^^^

:py:class:`APIKeyAuthentication` authenticates against a model with ``key`` and
``secret`` fields, supplied as query-string, header, or form parameters.  The
matched row is stored on ``g.api_key``:

.. code-block:: python

    from flask_peewee.rest import APIKeyAuthentication

    class APIKey(db.Model):
        key = CharField()
        secret = CharField()

    api_key_auth = APIKeyAuthentication(APIKey)
    api.register(SecretModel, auth=api_key_auth)

    # curl "http://127.0.0.1:5000/api/secretmodel/?key=abc&secret=xyz"

.. warning::
    Because the key and secret can travel in the query string, they may end up
    in access logs.  Prefer bearer tokens (below) for anything sensitive.

Bearer tokens
^^^^^^^^^^^^^

:py:class:`BearerAuthentication` reads a token from the standard
``Authorization: Bearer <token>`` header -- so the credential stays out of the
query string and logs -- and looks it up in a model with a ``token`` field.
The matched row is stored on ``g.api_key``:

.. code-block:: python

    from flask_peewee.rest import BearerAuthentication

    class ApiToken(db.Model):
        token = CharField()

    bearer_auth = BearerAuthentication(ApiToken)
    api.register(SecretModel, auth=bearer_auth)

    # curl -H "Authorization: Bearer <token>" http://127.0.0.1:5000/api/secretmodel/

Override ``token_field`` to use a differently-named column, and store
high-entropy tokens (override ``get_key`` to keep them hashed at rest).

Bearer tokens as users
^^^^^^^^^^^^^^^^^^^^^^^

:py:class:`UserBearerAuthentication` resolves the token to a *user* and sets
``g.user`` (rather than ``g.api_key``), so bearer tokens work with
:py:class:`RestrictOwnerResource` and anything else keyed off the authenticated
user.  The token model carries a foreign key to the user:

.. code-block:: python

    from flask_peewee.rest import UserBearerAuthentication

    class ApiToken(db.Model):
        token = CharField()
        user = ForeignKeyField(User)

    user_bearer_auth = UserBearerAuthentication(ApiToken)

    class MessageResource(RestrictOwnerResource):
        owner_field = 'user'

    api.register(Message, MessageResource, auth=user_bearer_auth)

A request carrying a valid token is now treated as that token's user: new
objects are assigned to them, and they may only modify their own.  Set
``user_field = None`` if the token lives directly on the user model instead of
a separate token table.


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
        "page_count": 1,
        "previous": ""
      },
      "objects": [
        {
          "content": "haxed you, bro",
          "pub_date": "2026-09-16T18:36:15",
          "user": 2,
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
        "page_count": 1,
        "previous": ""
      },
      "objects": [
        {
          "content": "flask and peewee, together at last!",
          "pub_date": "2026-09-16T18:36:15",
          "user": 1,
          "id": 1
        },
        {
          "content": "hello api",
          "pub_date": "2026-09-22T11:25:02",
          "user": 1,
          "id": 3
        }
      ]
    }

It is also supported to use different comparison operators with the same double-underscore notation:

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/user/?id__lt=2

.. code-block:: javascript

    {
      "meta": {
        "model": "user",
        "next": "",
        "page": 1,
        "page_count": 1,
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
    'eq', 'lt', 'lte', 'gt', 'gte', 'ne', 'in', 'is', 'is_not', 'like', 'ilike', 'regexp'

The ``in`` operator accepts a comma-separated list and/or repeated parameters,
so ``?id__in=1,2`` and ``?id__in=1&id__in=2`` are equivalent.

.. note::
    Unrecognized filter parameters -- a misspelled field, or a field not exposed
    for filtering -- are **ignored** rather than rejected, so a typo such as
    ``?usernam=x`` silently returns every row.  This is intentional: it keeps
    stray query-string parameters (cache-busters, tracking params, etc.) from
    breaking a request.  Double-check your filter names if a query returns more
    than you expect.  An unknown ``ordering`` column is likewise ignored.


Restricting what can be filtered
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default every field on the model is filterable and joins may be traversed
into related models.  Since filters come straight off the query string, you will
often want to lock this down, especially for sensitive columns.  Three
:py:class:`RestResource` attributes control it:

* ``filter_fields`` -- a whitelist; only these fields may be filtered on.
* ``filter_exclude`` -- a blacklist of fields that may never be filtered on (use
  ``__`` notation for related columns, e.g. ``user__password``).
* ``filter_recursive`` -- set to ``False`` to forbid filtering across foreign
  keys entirely (no ``user__...`` lookups at all).

.. code-block:: python

    class MessageResource(RestResource):
        # the only fields a client may filter on (with any operator)
        filter_fields = ('id', 'content', 'user__username')

    class UserResource(RestResource):
        exclude = ('password',)          # don't serialize the hash...
        filter_exclude = ('password',)   # ...and don't let it be filtered on either

Because an unrecognized filter is ignored rather than rejected (see the note
above), tightening this list can never break an otherwise-valid request.  A
now-disallowed filter stops narrowing the results.


Sorting results
---------------

Results can be sorted by specifying an ``ordering`` as a GET argument.  The ordering
must be a column on the model.

`/api/message/?ordering=pub_date`

If you would like to order objects "descending", place a "-" (hyphen character) before the column name:

`/api/message/?ordering=-pub_date`


Limiting results and pagination
-------------------------------

By default, resources are paginated 20 per-page (the ``paginate_by`` attribute).
Specify a ``limit`` in the querystring to request a different page size -- larger
or smaller:

`/api/message/?limit=2`

``paginate_by`` is only the default page size, not a maximum -- a client may
request a larger page.  To cap how large a page can be requested, set
``max_paginate_by`` on the resource (it defaults to ``None``, meaning no ceiling).
Setting ``paginate_by = None`` disables pagination and returns every matching
object on a single page (still wrapped in the standard ``meta``/``objects``
envelope).

In the "meta" section of the response, URIs for the "next" and "previous" sets
of results are available, along with the total number of pages:

.. code-block:: javascript

    "meta": {
      "model": "message",
      "next": "/api/message/?limit=1&page=3",
      "page": 2,
      "page_count": 5,
      "previous": "/api/message/?limit=1&page=1"
    }
