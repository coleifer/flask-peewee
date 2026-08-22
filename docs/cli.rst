.. _cli:

Command-Line Interface
======================

The :py:class:`Database` wrapper registers a ``fp`` command group with the
flask CLI. The commands locate your app the same way ``flask run`` does,
via ``--app`` or the ``FLASK_APP`` environment variable.

.. code-block:: console

    $ flask fp --help

Tables
------

``create-tables`` creates the table for every model subclassing ``db.Model``,
in foreign-key order. Existing tables are left alone, so it is safe to re-run.

.. code-block:: console

    $ flask fp create-tables
    created: note
    created: user

Users
-----

``createsuperuser`` creates an active admin user for the
:ref:`authentication system <authentication>`. The password prompt hides
input and asks for confirmation. Pass ``--email`` to set the email address.

.. code-block:: console

    $ flask fp createsuperuser
    Username: admin
    Password:
    Repeat for confirmation:
    created superuser: admin

Migrations
----------

The migration commands wrap the ``playhouse.migrations`` runner,
available in peewee 4.4 or newer, and mirror its ``pwmigrate`` verbs.
The database and models come from the app.

* ``status`` lists migrations, marking applied ones.
* ``up [TARGET]`` applies pending migrations, optionally stopping after
  ``TARGET``.
* ``down [TARGET]`` reverts the newest migration, or back through
  ``TARGET``.
* ``fake [TARGET]`` records pending migrations as applied without
  running them.
* ``create NAME`` writes a new empty/skeleton migration.
* ``initial`` writes a migration creating every model table.
* ``generate NAME`` writes a migration from the diff between the models
  and the database.
* ``diff`` prints that diff without writing anything.

See :ref:`migrations` for a worked example.

Shell
-----

The wrapper also installs a shell context, so ``flask shell`` starts with
``db``, ``database`` (the raw peewee database) and every model in scope.
