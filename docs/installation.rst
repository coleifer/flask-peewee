.. _installation:

Installing
==========

flask-peewee can be installed using ``pip`` or any other packaging tool:

.. code-block:: shell

    pip install flask-peewee

If you do not have the dependencies installed already, pip will install them
for you, but for reference they are:

* `flask <https://github.com/pallets/flask>`_
* `peewee <https://github.com/coleifer/peewee>`_
* `wtforms <https://github.com/wtforms/wtforms>`_
* `wtf-peewee <https://github.com/coleifer/wtf-peewee>`_
* python 3.8+

Using git
---------

.. code-block:: shell

    git clone https://github.com/coleifer/flask-peewee.git
    cd flask-peewee
    pip install .

You can run the tests using the test-runner::

    python runtests.py
