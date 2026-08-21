.. flask-peewee documentation master file, created by
   sphinx-quickstart on Tue Sep 20 13:19:30 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

flask-peewee
============

provides a layer of integration between the `flask <https://flask.palletsprojects.com/>`_
web framework and the `peewee orm <https://docs.peewee-orm.com/>`_.

The batteries are an admin interface, authentication, and a REST api. It
deliberately leaves out inline child editing, CSV export, action
confirmation prompts, translations, and file management. For a richer,
storage-agnostic admin, see
`Flask-Admin <https://flask-admin.readthedocs.io/>`_.

Contents:

.. toctree::
   :maxdepth: 2
   :glob:

   installation
   getting-started
   example
   database
   admin
   auth
   rest-api
   deployment
   utils

API in depth:

.. toctree::
    :maxdepth: 2
    :glob:

    api/

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
