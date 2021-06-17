flask-peewee
============

.. image:: https://img.shields.io/badge/License-MIT%20License-blue.svg
  :target: https://raw.githubusercontent.com/rammie/flask-peewee/master/LICENSE

.. image:: https://api.travis-ci.org/rammie/flask-peewee.png?branch=master
  :target: https://travis-ci.org/rammie/flask-peewee

This fork is different in the following ways:

* Strips out the admin and auth components.
* Change the REST API in backward incompatible ways.
* Adds StatsResource which is useful for aggregations.
* Changes how date serialization works.
* Adds support for JSON and JSONB fields when using a postgres backend.

requirements:

* `flask <https://github.com/mitsuhiko/flask>`_
* `peewee <https://github.com/coleifer/peewee>`_
* `wtforms <https://github.com/wtforms/wtforms>`_
* `wtf-peewee <https://github.com/coleifer/wtf-peewee>`_
* `flask-login <https://github.com/maxcountryman/flask-login>`_
* `pytest <https://github.com/pytest-dev/pytest>`_
* python 3.6 or greater


Check out the original `documentation <https://flask-peewee.readthedocs.io/>`_.


rest api
--------

influenced by `tastypie <https://github.com/toastdriven/django-tastypie>`_, provides
a way to expose a RESTful interface for your project's models.

::

    curl localhost:5000/api/user/
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
          "id": 1
        },
        {
          "username": "coleifer",
          "admin": false,
          "email": "coleifer@gmail.com",
          "join_date": "2011-09-16 18:35:56",
          "active": true,
          "id": 2
        }
      ]
    }
