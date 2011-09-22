.. _getting-started:

Getting Started
===============

The goal of this document is to help get you up and running quickly.  So without
further ado, let's get started.

.. note::
    Hopefully you have some familiarity with the `flask framework <http://flask.pocoo.org/>`_ and
    the `peewee orm <http://charlesleifer.com/docs/peewee/>`_, but if not those links
    should help you get started.

.. note::
    For a complete example project, check the `example app <https://github.com/coleifer/flask-peewee/tree/master/example>`_
    that ships with flask-peewee.


Creating a flask app
--------------------

from flask import Flask
    
app = Flask(__name__)
app.config.from_object(__name__)
