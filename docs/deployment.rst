.. _deployment:

Deployment
==========

Any WSGI server runs a flask-peewee app. With the tutorial's ``app.py``:

.. code-block:: console

    $ pip install gunicorn
    $ gunicorn -b 127.0.0.1:8000 app:app

.. code-block:: console

    $ pip install waitress
    $ waitress-serve --listen=127.0.0.1:8000 app:app

.. code-block:: console

    $ pip install uwsgi
    $ uwsgi --http 127.0.0.1:8000 --master --die-on-term --module app:app

``--die-on-term`` makes SIGTERM stop uwsgi instead of reloading it.

The REST api's basic-auth backends read the ``Authorization`` header. If
API writes start returning 401 behind a new server or proxy, check that
the header survives the hop.

Behind a proxy
--------------

When nginx or another proxy fronts the app, trust its forwarded headers
so redirects and generated urls come out right, including when the app is
mounted under a path prefix:

.. code-block:: python

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

Sessions
--------

Login state is stored in the flask session. Use a long random
``SECRET_KEY``, and on HTTPS set the cookie flags:

.. code-block:: python

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

:py:meth:`Auth.login_user` marks the session permanent, so
``PERMANENT_SESSION_LIFETIME`` bounds how long a login lasts (flask
defaults it to 31 days). See also ``clear_session`` in
:ref:`authentication`.

CSRF protection
---------------

The form templates, the login page included, carry a hidden
``_csrf_token`` input wired for
`flask-seasurf <https://pypi.org/project/flask-seasurf/>`_:

.. code-block:: python

    from flask_seasurf import SeaSurf

    csrf = SeaSurf(app)
    csrf.exempt_urls(('/api',))

With SeaSurf initialized, a form post without a valid token is rejected
with a 403. The REST api authenticates by header rather than by session,
so exempt its prefix as above, or every API write is rejected too.

Static files
------------

The admin's stylesheets and scripts are served by its blueprint, which
any WSGI server handles. At admin traffic levels that is fine. Alias
``/admin/static/`` from the web server if you want it off the app.
