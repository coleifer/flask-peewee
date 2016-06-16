.. flask-peewee documentation master file, created by
   sphinx-quickstart on Tue Sep 20 13:19:30 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

flask-peewee
============

.. warning::

    This package is in maintenance-only mode!
    -----------------------------------------

    I'm sorry to announce that flask-peewee will now be in maintenance-only mode. This decision is motivated by a number of factors:

    * `Flask-Admin <https://flask-admin.readthedocs.io/en/latest/>`_ provides a superior admin interface and has support for peewee models.
    * `Flask-Security <https://pythonhosted.org/Flask-Security/>`_ and `Flask-Login <https://flask-login.readthedocs.io/en/latest/>`_ both provide authentication functionality, and work well with Peewee.
    * Most importantly, though, I do not find myself wanting to work on flask-peewee.

    I plan on rewriting the ``Database`` and ``REST API`` portions of flask-peewee and repackaging them as a new library, but flask-peewee as it stands currently will be in maintenance-only mode.

------------------------------

Welcome to the flask-peewee documentation!

provides a layer of integration between the `flask <http://flask.pocoo.org/>`_
web framework and the `peewee orm <https://peewee.readthedocs.io/>`_.

Contents:

.. toctree::
   :maxdepth: 2
   :glob:

   installation
   getting-started
   database
   admin
   auth
   rest-api
   utils
   gevent

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
