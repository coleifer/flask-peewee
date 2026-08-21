.. _example-app:

The example app
===============

The project ships a small twitter clone under ``example/`` that exercises
every component:

* ``models.py``: ``User`` (mixing in :py:class:`BaseUser`),
  ``Relationship``, ``Message``, and ``Note``
* ``auth.py``: :py:class:`Auth` with the custom ``User`` model
* ``admin.py``: model admins using columns, search, filters, and
  foreign-key lookups, plus two dashboard panels
* ``api.py``: a REST api with user and admin authentication,
  owner-restricted writes, and nested user resources
* ``views.py``: the public site, including a ``/join/`` signup view built
  on :py:meth:`Auth.login_user`

Run it from a source checkout:

.. code-block:: console

    $ cd example/
    $ python run_example.py

Log in as admin/admin at http://127.0.0.1:5000/admin/, and try the API at
http://127.0.0.1:5000/api/message/.
