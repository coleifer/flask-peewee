flask-peewee
============

provides a layer of integration between the `flask <http://flask.pocoo.org/>`_ 
web framework and the `peewee orm <http://charlesleifer.com/docs/peewee/>`_.

batteries included:

* admin interface
* authentication
* rest api

requirements:

* `flask <https://github.com/mitsuhiko/flask>`_
* `peewee <https://github.com/coleifer/peewee>`_
* `wtforms <https://bitbucket.org/simplecodes/wtforms>`_
* `wtforms-peewee <https://github.com/coleifer/wtf-peewee>`_
* python 2.5 or greater


NOT READY FOR USE
=================

this project probably has strange bugs, the public and private apis may change
significantly, and it currently doesn't have unit tests.  that burning smell?
probably the project.


admin interface
---------------

influenced heavily by the `django <http://djangoproject.com>`_ admin, provides easy
create/edit/delete functionality for your project's models.

.. image:: http://i.imgur.com/aVcIx.jpg


rest api
--------

influenced by `tastypie <https://github.com/toastdriven/django-tastypie>`_, provides
a way to expose a RESTful interface for your project's models.

::

    GET /api/user/
    
    {
      meta: {
        model: "user"
        next: ""
        page: 1
        previous: ""
      },
      objects: [
        {
          username: "admin"
          admin: true
          email: ""
          join_date: "2011-09-16 18:34:49"
          active: true
          id: 1
        },
        {
          username: "coleifer"
          admin: false
          email: "coleifer@gmail.com"
          join_date: "2011-09-16 18:35:56"
          active: true
          id: 2
        }
      ]
    }


example app
-----------

the project ships with an example app, which is a silly twitter clone.  if you
would like to test out the admin area, log in as "admin/admin" and navigate to:

http://127.0.0.1:5000/admin/

you can check out the REST api at the following url:

http://127.0.0.1:5000/api/message/
