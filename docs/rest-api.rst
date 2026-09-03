.. _rest-api:

REST API
========

flask-peewee comes with some tools for exposing your project's models via a
REST API. There are several components to the ``rest`` module, but the basic
setup is to create an instance of :py:class:`RestAPI` and then register your
project's models with subclasses of :py:class:`RestResource`.

Each :py:class:`RestResource` you expose via the API will support, by default,
the following:

* ``/api/<model name>/``: GET and POST requests
* ``/api/<model name>/<primary key>/``: GET, PUT, PATCH and DELETE requests.
  POST also edits, and ``POST /<primary key>/delete/`` works as DELETE, for
  clients that cannot issue PUT or DELETE.

PUT and PATCH share partial-update semantics, changing only the fields
present in the request body.

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
* ``__not_in``: not in set
* ``__is``: is, ``?field__is=None`` or ``?-field__is=None`` for NOT NULL
* ``__is_not``: is not, ``?field__is_not=None``
* ``__is_null``: takes true/false, ``?field__is_null=true`` for IS NULL
* ``__like``: wild-card matching, case-sensitive
* ``__ilike``: wild-card matching, case-insensitive
* ``__contains``: substring match, case-insensitive
* ``__startswith``, ``__endswith``: prefix / suffix match, case-insensitive
* ``__regexp``: regular-expression matching (database-specific)
* ``__iregexp``: like ``regexp`` but case-insensitive
* ``__between``: two comma-separated bounds, inclusive, ``?id__between=2,5``

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

In this documentation we'll start with a very simple API and build it out. The
complete version of this API is included in the `example app
<https://github.com/coleifer/flask-peewee/tree/master/example>`_, so feel free
to refer there.

The project will be a simple 'twitter-like' app where users can post short messages
and "follow" other users.


Project models
^^^^^^^^^^^^^^

There are three main models, ``User``, ``Relationship`` and ``Message``, which
we will expose via the API. Here is a truncated version of what they look like:

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

The :py:class:`RestAPI` holds the :py:class:`RestResource` objects we will
expose. By default it binds all resources to ``/api/<model-name>/``.

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
        "object_count": 2,
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
        "object_count": 2,
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

Passwords and email addresses are being exposed. To exclude these fields
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

``exclude`` is a blacklist. Its positive counterpart is ``fields``, a
whitelist of the only fields to serialize. The resource above could instead expose just
the username and id:

.. code-block:: python

    class UserResource(RestResource):
        fields = ('username', 'id')

Reach for whichever is more convenient: ``fields`` when you want to expose a
small, fixed set of columns, ``exclude`` when you want everything but a few.

For computed values, override :py:meth:`~RestResource.prepare_data`. It
receives each object and its serialized dictionary on the way out:

.. code-block:: python

    class UserResource(RestResource):
        exclude = ('password', 'email')

        def prepare_data(self, obj, data):
            data['gravatar'] = obj.gravatar_url()
            return data


Nested resources
----------------

By default a foreign key is serialized as the related row's primary key. Notice
the ``"user": 1`` in the message output above. To embed the full related
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

``include_resources`` can be nested arbitrarily deep (an included resource may
itself include resources), and one model can be embedded through more than one
foreign key. For example, a ``Relationship`` resource can expand both endpoints:

.. code-block:: python

    class RelationshipResource(RestResource):
        include_resources = {
            'from_user': UserResource,
            'to_user': UserResource,
        }

The whole nested tree is loaded in a single query, one ``JOIN`` per included
foreign key, so embedding related objects does not incur the N+1 queries you
would get from following each row's relations lazily.

Nested writes
^^^^^^^^^^^^^

Included resources also work on the way in. A ``POST`` or ``PUT`` whose body
carries a nested object (instead of a bare id) creates or updates the related row
as part of the same request. Two rules keep that safe:

* A resource's ``readonly_fields`` are stripped at every level of the
  payload, so a nested object cannot smuggle in a field the resource protects
  (e.g. slipping ``"admin": true`` into a nested user).
* Each nested write must pass the child resource's own ``check_post`` /
  ``check_put``, exactly as a direct write to that resource would, so nesting
  can never be used to sidestep a resource's authorization.

The entire object graph is saved in a single transaction, so if any nested write
is rejected the whole request rolls back. To disable nested writes for a
resource, set ``nested_writes = False``. A nested object in the payload is then
ignored, though the foreign key can still be assigned with a bare id.


Validating incoming data
------------------------

A write accepts its payload three ways, checked in order: a JSON request
body (send ``Content-Type: application/json``), a form field named
``data`` holding a JSON string (the ``curl -d data='{...}'`` convention),
or plain form fields, one per column.

Write payloads are validated as they are deserialized, and problems surface as
a 400 with a JSON error rather than a 500 (or worse, bad data):

* A body that is not valid JSON, or whose JSON is not an object, is rejected.
* Values that cannot be coerced to their field's type are rejected. This
  includes date/time strings: a value like ``"pub_date": "not-a-date"`` returns
  ``{"error": "Unrecognized date/time value for \"pub_date\": 'not-a-date'"}``
  instead of being written through to the database. Both ISO-8601 (what the
  API itself emits) and the field's own ``formats`` are accepted.
* Violated database constraints (``NOT NULL``, unique, foreign keys) are
  reported as a 400 as well.

Unrecognized keys in a payload are silently ignored by default, which is
forgiving but means a typo'd field name is dropped without complaint. Set
``reject_unknown_fields = True`` on the resource to get a 400 listing the
offending keys instead:

.. code-block:: python

    class MessageResource(RestResource):
        reject_unknown_fields = True

.. code-block:: console

    $ curl -u admin:admin -H 'Content-Type: application/json' \
        -d '{"contnet": "hello"}' http://127.0.0.1:5000/api/message/

    {"error": "Unrecognized field(s): contnet"}

Read-only fields are exempt (they are stripped, not rejected), so fetching an
object and ``PUT``-ing the whole thing back continues to work, and a foreign
key may be written by field name or column name (``user`` / ``user_id``).
Unknown keys inside a nested object are reported with the ``__`` path notation,
e.g. ``user__usernmae``.


Error responses
---------------

Every error the API returns is a JSON object with a single ``error`` key,
whether it is a 400, 401, 403, 404 or 405. A 401 also carries the
``WWW-Authenticate`` challenge header.

.. code-block:: console

    $ curl http://127.0.0.1:5000/api/message/9999/

    {"error": "Not found"}


Bulk creation
-------------

A POST body is normally a single JSON object. Set ``allow_bulk = True`` on a
resource and POST a JSON list to create many objects in one request:

.. code-block:: python

    class MessageResource(RestResource):
        allow_bulk = True

.. code-block:: console

    $ curl -u admin:admin -H 'Content-Type: application/json' \
        -d '[{"user": 1, "content": "one"}, {"user": 1, "content": "two"}]' \
        http://127.0.0.1:5000/api/message/

Each object passes through the same validation as a single create, and the
whole batch is saved in one transaction. An object that fails returns a 400
naming its index and nothing is saved. A list longer than ``max_bulk``
objects (default 100) is rejected. On success the response is
``{"objects": [...]}`` with the created objects in order.


Allowing users to post objects
------------------------------

What if we want to create new messages via the Api? Or modify/delete existing messages?

.. code-block:: console

    $ curl -i -d '' http://127.0.0.1:5000/api/message/

    HTTP/1.1 401 UNAUTHORIZED
    WWW-Authenticate: Basic realm="Login Required"
    Content-Type: application/json

    {"error": "Authentication failed"}

The authentication failed because the default authentication mechanism only
allows read-only access.

To allow users to create messages via the API, we need to use a subclass
of :py:class:`Authentication` that allows ``POST`` requests. We also want to ensure
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

There is a problem with this, however. Notice how the ``user`` was passed in
with the POST data? This effectively will let a user post a message as another user.
It also means a user can use PUT requests to modify another user's message:

.. code-block:: python

    # continued from above, edit another user's message (id=2)
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

This is a problem. We need a way of ensuring that users can only edit their
own messages. Furthermore, when they create messages we need to make sure the
message is assigned to them.


Restricting API access on a per-model basis
-------------------------------------------

flask-peewee comes with a special subclass of :py:class:`RestResource` that
restricts POST/PUT/PATCH/DELETE requests to prevent users from modifying another user's
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

* PUT / PATCH / DELETE: verify the authenticated user is the owner of the object
* POST: assign the authenticated user as the owner of the new object


Locking down a resource
-----------------------

Suppose we want to restrict normal users from modifying ``User`` resources. For this
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


Adding custom endpoints
-----------------------

A resource's urls come from its ``get_urls()`` method. Extend it to
expose views alongside the standard list and detail. Here messages gain
``/api/message/mine/``, the authenticated user's messages. Reads need an
authentication that sets ``g.user``, so protect GET too:

.. code-block:: python

    from flask import g
    from flask_peewee.rest import ALL_METHODS

    user_auth = UserAuthentication(auth, protected_methods=ALL_METHODS)

    class MessageResource(RestrictOwnerResource):
        owner_field = 'user'

        def get_urls(self):
            return super(MessageResource, self).get_urls() + (
                ('/mine/', self.require_method(self.api_mine, ['GET'])),
            )

        def api_mine(self):
            query = self.get_query().where(Message.user == g.user)
            return self.paginated_object_list(query)

    api.register(Message, MessageResource, auth=user_auth)


Token-based authentication
--------------------------

:py:class:`UserAuthentication` and :py:class:`AdminAuthentication` use HTTP
Basic auth, which is handy for humans but awkward for programmatic clients. For
API clients, flask-peewee ships token-based authentication classes. Like all
authentication classes they only guard the ``protected_methods`` (``POST``,
``PUT``, ``PATCH`` and ``DELETE`` by default, with ``GET`` open). To require
auth on reads too, pass ``protected_methods=ALL_METHODS`` (a convenience
constant equal to ``('GET', 'POST', 'PUT', 'PATCH', 'DELETE')``) or your own
list.

API keys
^^^^^^^^

:py:class:`APIKeyAuthentication` authenticates against a model with ``key`` and
``secret`` fields, supplied as query-string, header, or form parameters. The
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
    in access logs. Prefer bearer tokens (below) for anything sensitive.

Bearer tokens
^^^^^^^^^^^^^

:py:class:`HashedBearerAuthentication` reads a token from the standard
``Authorization: Bearer <token>`` header, keeping the credential out of the
query string and logs. Tokens are stored as sha256 hashes, so the raw token
never touches the database. :py:func:`make_token_model` builds the token
model, and its ``create_token()`` classmethod returns the new row along with
the raw token:

.. code-block:: python

    from flask_peewee.rest import HashedBearerAuthentication
    from flask_peewee.rest import make_token_model

    ApiToken = make_token_model(db, user_model=User)

    token, raw = ApiToken.create_token(user=some_user)
    # show "raw" to the caller once. it cannot be recovered later.

    api.register(SecretModel, auth=HashedBearerAuthentication(ApiToken))

    # curl -H "Authorization: Bearer <raw>" http://127.0.0.1:5000/api/secretmodel/

The model has ``token_hash``, ``created``, ``expires`` and ``revoked``
columns, plus a ``user`` foreign key when ``user_model`` is given. A token
stops working when ``revoked`` is set or ``expires`` passes (null means no
expiry):

.. code-block:: python

    ApiToken.create_token(user=some_user,
                          expires=datetime.now() + timedelta(days=30))

The matching row is stored on ``g.api_key``. When the model has a ``user``
foreign key, ``g.user`` is set to the token's user, so bearer tokens work with
:py:class:`RestrictOwnerResource` and anything else keyed off the
authenticated user: new objects are assigned to the token's user, and they may
only modify their own. Omit ``user_model`` for tokens tied to no user.

Custom token schemes
^^^^^^^^^^^^^^^^^^^^

When the factory model does not fit, plain :py:class:`BearerAuthentication`
looks the presented token up verbatim in a model with a ``token`` field
(override ``token_field`` to rename it, or ``get_key`` to change the lookup)
and sets ``g.api_key``. :py:class:`UserBearerAuthentication` extends it to
resolve the row to a user through its ``user_field`` foreign key and set
``g.user`` instead of ``g.api_key``. Set ``user_field = None`` when the token
lives on the user model itself.


Filtering records and querying
------------------------------

A REST Api is not very useful if it cannot be queried in a meaningful fashion. To
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
        "object_count": 1,
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
        "object_count": 2,
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
        "object_count": 1,
        "page": 1,
        "page_count": 1,
        "previous": ""
      },
      "objects": [
        {
          "username": "admin",
          "admin": true,
          "join_date": "2026-09-16T18:34:49",
          "active": true,
          "id": 1
        }
      ]
    }


Valid Comparison Operators are:
    'eq', 'lt', 'lte', 'gt', 'gte', 'ne', 'in', 'not_in', 'is', 'is_not',
    'is_null', 'like', 'ilike', 'contains', 'startswith', 'endswith',
    'regexp', 'iregexp', 'between'

The ``in`` and ``not_in`` operators accept a comma-separated list and/or
repeated parameters, so ``?id__in=1,2`` and ``?id__in=1&id__in=2`` are
equivalent. ``between`` takes exactly two comma-separated values.

A filter repeated with different values matches any of them, so
``?username=a&username=b`` is an OR. Exclusions combine the other way, so
repeated ``ne`` or negated values exclude every listed value.

.. note::
    Unrecognized filter parameters (a misspelled field, or a field not exposed
    for filtering) are ignored by default, so a typo such as ``?usernam=x``
    silently returns every row. The lenient default keeps stray query-string
    parameters (cache-busters, tracking params) from breaking a request. Set
    ``reject_unknown_filters = True`` on the resource to get a 400 naming the
    offending parameters instead. Those stray parameters then 400 as well, so
    enable it only when clients send clean query strings. An unknown
    ``ordering`` column is always ignored.


Restricting what can be filtered
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default every field on the model is filterable, but related columns are
not. Since filters come straight off the query string, you will often want to
restrict this, especially for sensitive columns. Three
:py:class:`RestResource` attributes control it:

* ``filter_fields``: a whitelist, only these fields may be filtered on. Related
  columns use ``__`` notation, e.g. ``user__username``.
* ``filter_exclude``: a blacklist of fields that may never be filtered on (use
  ``__`` notation for related columns, e.g. ``user__password``).
* ``filter_recursive``: set to ``True`` to make every column of a related model
  filterable, up to ``max_filter_depth`` foreign keys deep.

.. warning::
    A filter reveals the value of the column it tests, even when the column is
    not serialized. ``?user__password__startswith=a`` tests the password hash
    one character at a time, and ``exclude`` does not prevent it. For that
    reason ``filter_recursive`` is off by default, and a resource in
    ``include_resources`` adds only the filters in its own ``filter_fields``.

.. code-block:: python

    class MessageResource(RestResource):
        # the only fields a client may filter on (with any operator)
        filter_fields = ('id', 'content', 'user__username')

    class UserResource(RestResource):
        exclude = ('password',)          # don't serialize the hash...
        filter_exclude = ('password',)   # ...and don't let it be filtered on either

With the default lenient handling (see the note above), tightening this list
never breaks an otherwise-valid request. A now-disallowed filter stops
narrowing the results. With ``reject_unknown_filters`` set it becomes a 400
instead.


Sorting results
---------------

Results can be sorted by specifying an ``ordering`` as a GET argument. The
ordering must be a column the resource allows filtering on. Anything else is
ignored.

`/api/message/?ordering=pub_date`

If you would like to order objects "descending", place a "-" (hyphen character) before the column name:

`/api/message/?ordering=-pub_date`


Limiting results and pagination
-------------------------------

By default, resources are paginated 20 per-page (the ``paginate_by`` attribute).
Specify a ``limit`` in the querystring to request a different page size, larger
or smaller:

`/api/message/?limit=2`

``paginate_by`` is only the default page size, not a maximum. A client may
request a larger page. To cap how large a page can be requested, set
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
      "object_count": 5,
      "page": 2,
      "page_count": 5,
      "previous": "/api/message/?limit=1&page=1"
    }
