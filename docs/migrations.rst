.. _migrations:

Migrations
==========

The :ref:`CLI <cli>` migration commands wrap ``playhouse.migrations``,
available in peewee 4.4 or newer. Peewee migrations are python scripts, applied
in numeric order and recorded by name in a history table. Each script defines
``up(migrator, db)`` and, if it can be reverted, ``down(migrator, db)``. The
migrator is a :ref:`SchemaMigrator <https://docs.peewee-orm.com/en/latest/peewee/db_tools.html#migration-api>`_ (docs).

Configuration options:

* ``MIGRATIONS_DIR``: directory for migration scripts, default ``migrations``.
* ``MIGRATIONS_TABLE``: history table name, default ``schema_migration``.

Example
-------

Write and apply an initial migration for the app's models:

.. code-block:: console

    $ flask fp initial
    migrations/0001_initial.py

    $ flask fp up
    applied: 0001_initial

Add a field to a model:

.. code-block:: python

    class User(db.Model):
        username = CharField()
        karma = IntegerField(default=0)

``diff`` prints what changed (we added the "karma" field), and ``generate``
writes it the migration:

.. code-block:: console

    $ flask fp diff
    add column user.karma

    $ flask fp generate "add karma"
    migrations/0002_add_karma.py

The generated migration script:

.. code-block:: python

    # Generated from a schema diff on 2026-08-22 16:54.
    from peewee import *

    def up(migrator, db):
        migrator.migrate(migrator.add_column('user', 'karma', IntegerField(default=0)))


    def down(migrator, db):
        migrator.migrate(migrator.drop_column('user', 'karma'))

Apply it (``up``) and review the history (``status``). Applied migrations show
a marker and timestamp:

.. code-block:: console

    $ flask fp up
    applied: 0002_add_karma

    $ flask fp status
    [x] 0001_initial  2026-08-22 16:54:02
    [x] 0002_add_karma  2026-08-22 16:54:03

``down`` reverts the newest migration, or back through an optional
target:

.. code-block:: console

    $ flask fp down
    reverted: 0002_add_karma

``create`` writes an empty skeleton migration for any changes you prefer to
write manually.

``fake`` records migrations as applied without running them, for
adopting migrations on a database that already matches the models.

More details on Peewee's migration runner can be found in the
:ref:`migration runner docs <https://docs.peewee-orm.com/en/latest/peewee/db_tools.html#module-playhouse.migrations>`_.
