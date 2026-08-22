import os
import shutil
import tempfile
import unittest
from unittest import mock

from flask import Flask
from peewee import *

from flask_peewee import utils
from flask_peewee.auth import Auth
from flask_peewee.db import Database


class CLITestCase(unittest.TestCase):
    def setUp(self):
        utils.PASSWORD_HASH_METHOD = 'pbkdf2:sha256:1'
        self.tempdir = tempfile.mkdtemp()
        self.app = Flask(__name__)
        self.app.config.update(
            DATABASE={'name': os.path.join(self.tempdir, 'cli.db'),
                      'engine': 'peewee.SqliteDatabase'},
            MIGRATIONS_DIR=os.path.join(self.tempdir, 'migrations'),
            SECRET_KEY='shhh')
        self.db = Database(self.app)
        self.auth = Auth(self.app, self.db)

        class Person(self.db.Model):
            name = CharField()

        class Employee(Person):
            title = CharField()

        class Pet(self.db.Model):
            owner = ForeignKeyField(Person)
            name = CharField()

        self.Person, self.Employee, self.Pet = Person, Employee, Pet
        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        if not self.db.database.is_closed():
            self.db.database.close()
        shutil.rmtree(self.tempdir)

    def all_output(self, result):
        # click >= 8.2 splits stderr from output, older versions mix them.
        try:
            return result.output + result.stderr
        except (AttributeError, ValueError):
            return result.output

    def test_create_tables(self):
        result = self.runner.invoke(args=['fp', 'create-tables'])
        self.assertEqual(result.exit_code, 0)
        for model in (self.Person, self.Employee, self.Pet, self.auth.User):
            self.assertTrue(model.table_exists())
            self.assertIn('created: %s' % model._meta.table_name,
                          result.output)

        result = self.runner.invoke(args=['fp', 'create-tables'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'nothing to create.\n')

    def test_createsuperuser(self):
        result = self.runner.invoke(args=['fp', 'createsuperuser'],
                                    input='huey\nmeow!\nmeow!\n')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('created superuser: huey', result.output)

        user = self.auth.User.get(self.auth.User.username == 'huey')
        self.assertTrue(user.admin)
        self.assertTrue(user.active)
        self.assertTrue(user.check_password('meow!'))
        self.assertFalse(user.check_password('woof'))

        result = self.runner.invoke(
            args=['fp', 'createsuperuser', '--username', 'huey',
                  '--password', 'meow!'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('already exists', self.all_output(result))

        # default user model has a unique email, blank collides with huey's.
        result = self.runner.invoke(
            args=['fp', 'createsuperuser', '--username', 'zaizee',
                  '--password', 'purr'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('user.email', self.all_output(result))

    def test_createsuperuser_no_auth(self):
        app = Flask(__name__)
        app.config.update(DATABASE={
            'name': os.path.join(self.tempdir, 'no-auth.db'),
            'engine': 'peewee.SqliteDatabase'})
        Database(app)

        result = app.test_cli_runner().invoke(
            args=['fp', 'createsuperuser', '--username', 'x',
                  '--password', 'y'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('no Auth instance', self.all_output(result))

    def migration_path(self, filename):
        return os.path.join(self.app.config['MIGRATIONS_DIR'], filename)

    def write_migration(self, path, body):
        with open(path, 'w') as fh:
            fh.write(body)

    def test_up_down_status(self):
        result = self.runner.invoke(args=['fp', 'create', 'add color'])
        self.assertEqual(result.exit_code, 0)
        path = self.migration_path('0001_add_color.py')
        self.assertIn(path, result.output)
        self.assertTrue(os.path.exists(path))

        result = self.runner.invoke(args=['fp', 'status'])
        self.assertEqual(result.output, '[ ] 0001_add_color\n')
        self.assertEqual(result.exit_code, 1)

        self.write_migration(path,
            'def up(migrator, db):\n'
            '    db.execute_sql("create table color (name text)")\n'
            'def down(migrator, db):\n'
            '    db.execute_sql("drop table color")\n')

        result = self.runner.invoke(args=['fp', 'up'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('applied: 0001_add_color', result.output)
        self.assertTrue(self.db.database.table_exists('color'))

        result = self.runner.invoke(args=['fp', 'status'])
        self.assertEqual(result.exit_code, 0)
        self.assertRegex(result.output,
                         r'^\[x\] 0001_add_color  \d{4}-\d\d-\d\d ')

        result = self.runner.invoke(args=['fp', 'up'])
        self.assertEqual(result.output, 'nothing to do.\n')

        result = self.runner.invoke(args=['fp', 'up', '0009_nope'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('unknown migration', self.all_output(result))

        result = self.runner.invoke(args=['fp', 'down'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('reverted: 0001_add_color', result.output)
        self.assertFalse(self.db.database.table_exists('color'))

    def test_fake(self):
        self.runner.invoke(args=['fp', 'create', 'add color'])
        self.write_migration(self.migration_path('0001_add_color.py'),
            'def up(migrator, db):\n'
            '    db.execute_sql("create table color (name text)")\n')

        result = self.runner.invoke(args=['fp', 'fake'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('faked: 0001_add_color', result.output)
        self.assertFalse(self.db.database.table_exists('color'))

        result = self.runner.invoke(args=['fp', 'up'])
        self.assertEqual(result.output, 'nothing to do.\n')

    def test_initial_generate_diff(self):
        class Tag(self.db.Model):
            pass

        result = self.runner.invoke(args=['fp', 'diff'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('person', result.output.lower())
        self.assertIn('skipped: Tag (no fields)', self.all_output(result))

        result = self.runner.invoke(args=['fp', 'initial'])
        self.assertEqual(result.exit_code, 0)
        path = self.migration_path('0001_initial.py')
        self.assertIn(path, result.output)
        with open(path) as fh:
            body = fh.read().lower()
        for fragment in ('person', 'employee', 'pet', 'user'):
            self.assertIn(fragment, body)
        self.assertNotIn('tag', body)

        result = self.runner.invoke(args=['fp', 'initial'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('already exist', self.all_output(result))

        result = self.runner.invoke(args=['fp', 'up'])
        self.assertEqual(result.exit_code, 0)
        for model in (self.Person, self.Employee, self.Pet):
            self.assertTrue(model.table_exists())

        # the skipped-Tag notice may share the stream with stdout.
        result = self.runner.invoke(args=['fp', 'diff'])
        self.assertTrue(result.output.endswith('schema matches models.\n'))

        result = self.runner.invoke(args=['fp', 'generate', 'noop'])
        self.assertTrue(result.output.endswith(
            'schema matches models. Nothing to generate.\n'))

        self.db.database.drop_tables([self.Pet])
        result = self.runner.invoke(args=['fp', 'generate', 'add pet'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.migration_path('0002_add_pet.py'), result.output)

        result = self.runner.invoke(args=['fp', 'up'])
        self.assertIn('applied: 0002_add_pet', result.output)
        self.assertTrue(self.Pet.table_exists())

    def test_create_requires_name(self):
        result = self.runner.invoke(args=['fp', 'create'])
        self.assertEqual(result.exit_code, 2)

    def test_migrations_table_config(self):
        self.app.config['MIGRATIONS_TABLE'] = 'fp_history'
        self.runner.invoke(args=['fp', 'create', 'x'])
        result = self.runner.invoke(args=['fp', 'fake'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.db.database.table_exists('fp_history'))
        self.assertFalse(self.db.database.table_exists('schema_migration'))

    def test_migrations_missing_playhouse(self):
        from flask_peewee import cli
        with mock.patch.object(cli, 'Runner', None):
            for args in (['fp', 'status'], ['fp', 'up'], ['fp', 'down'],
                         ['fp', 'fake'], ['fp', 'create', 'x'],
                         ['fp', 'initial'], ['fp', 'generate', 'x'],
                         ['fp', 'diff']):
                result = self.runner.invoke(args=args)
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn('peewee 4.4', self.all_output(result))

    def test_shell_context(self):
        context = self.app.make_shell_context()
        self.assertTrue(context['db'] is self.db)
        self.assertTrue(context['database'] is self.db.database)
        self.assertTrue(context['Person'] is self.Person)
        self.assertTrue(context['Employee'] is self.Employee)
        self.assertTrue(context['Pet'] is self.Pet)
        self.assertTrue(context['User'] is self.auth.User)
