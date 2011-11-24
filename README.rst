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


check out the `documentation <http://charlesleifer.com/docs/flask-peewee/>`_.


admin interface
---------------

influenced heavily by the `django <http://djangoproject.com>`_ admin, provides easy
create/edit/delete functionality for your project's models.

.. image:: http://i.imgur.com/EtzdO.jpg


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


installing
----------

I recommend installing in a virtualenv.  to get started::

    # create a new virtualenv
    virtualenv --no-site-packages project
    cd project/
    source bin/activate

    # install this project (will install dependencies as well)
    pip install flask-peewee


example app
-----------

the project ships with an example app, which is a silly twitter clone.  to
start the example app, ``cd`` into the "example" directory and execute
the ``run_example.py`` script::

    cd example/
    python run_example.py

if you would like to test out the admin area, log in as "admin/admin" and navigate to:

http://127.0.0.1:5000/admin/

you can check out the REST api at the following url:

http://127.0.0.1:5000/api/message/
