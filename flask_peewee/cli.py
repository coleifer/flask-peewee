import click
from flask import current_app
from flask.cli import AppGroup
from peewee import AutoField
from peewee import IntegrityError
from peewee import sort_models

try:
    from playhouse.migrations import MigrationError
    from playhouse.migrations import Runner
    from playhouse.migrations import template
except ImportError:
    class MigrationError(Exception):
        pass
    Runner = template = None


fp = AppGroup('fp', help='flask-peewee commands.')


def get_extension(key, label):
    obj = current_app.extensions.get('flask_peewee', {}).get(key)
    if obj is None:
        raise click.ClickException(
            'no %s instance is registered with this app.' % label)
    return obj


def get_runner():
    if Runner is None:
        raise click.ClickException(
            'migration commands require playhouse.migrations, available in '
            'peewee 4.4 or newer.')
    db = get_extension('db', 'Database')
    return Runner(db.database,
                  current_app.config.get('MIGRATIONS_DIR', 'migrations'),
                  current_app.config.get('MIGRATIONS_TABLE',
                                         'schema_migration'))


def run_migration(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except MigrationError as exc:
        raise click.ClickException(str(exc))


def implicit_id_only(model):
    fields = model._meta.sorted_fields
    return (len(fields) == 1 and type(fields[0]) is AutoField and
            fields[0].name == 'id' and fields[0].column_name == 'id' and
            not model._meta.indexes)


def get_diff(runner, initial=False):
    from playhouse.schema_diff import SchemaDiff, diff_models
    models = []
    for model in get_extension('db', 'Database').get_models():
        if implicit_id_only(model):
            click.echo('skipped: %s (no fields)' % model.__name__, err=True)
        elif initial and getattr(model._meta, 'extension_module', None):
            click.echo('skipped: %s (virtual table)' % model.__name__,
                       err=True)
        else:
            models.append(model)
    if initial:
        return SchemaDiff(sort_models(models), [], [], [], [])
    try:
        return diff_models(runner.database, models)
    except ValueError as exc:
        raise MigrationError(str(exc))


def report(verb, names):
    for name in names:
        click.echo('%s: %s' % (verb, name))
    if not names:
        click.echo('nothing to do.')


@fp.command()
def create_tables():
    """Create tables for all db.Model subclasses."""
    db = get_extension('db', 'Database')
    models = db.get_models()
    pending = [m for m in models if not m.table_exists()]
    db.database.create_tables(models)
    for model in pending:
        click.echo('created: %s' % model._meta.table_name)
    if not pending:
        click.echo('nothing to create.')


@fp.command()
@click.option('--username', prompt=True)
@click.option('--email', default='')
@click.password_option()
def createsuperuser(username, email, password):
    """Create an active admin user."""
    auth = get_extension('auth', 'Auth')
    User = auth.User
    User.create_table()
    if User.select().where(User.username == username).exists():
        raise click.ClickException('user "%s" already exists.' % username)

    user = User(username=username, email=email, admin=True, active=True)
    user.set_password(password)
    try:
        user.save()
    except IntegrityError as exc:
        raise click.ClickException(str(exc))
    click.echo('created superuser: %s' % username)


@fp.command()
def status():
    """List migrations, marking the applied ones."""
    pending = False
    for migration in get_runner().status():
        if not migration.applied:
            marker = ' '
            pending = True
        elif migration.path is not None:
            marker = 'x'
        else:
            marker = '?'  # applied but the file is gone.
        line = '[%s] %s' % (marker, migration.name)
        if migration.applied:
            line += '  ' + migration.applied.strftime('%Y-%m-%d %H:%M:%S')
        click.echo(line)
    if pending:
        # Exit 1 when pending, so status can gate a deploy.
        raise SystemExit(1)


@fp.command()
@click.argument('target', required=False)
def up(target):
    """Apply pending migrations, optionally stopping after TARGET."""
    report('applied', run_migration(get_runner().up, target))


@fp.command()
@click.argument('target', required=False)
def down(target):
    """Revert the last migration, or back through TARGET."""
    report('reverted', run_migration(get_runner().down, target))


@fp.command()
@click.argument('target', required=False)
def fake(target):
    """Record pending migrations as applied without running them."""
    report('faked', run_migration(get_runner().fake, target))


@fp.command()
@click.argument('name')
def create(name):
    """Write a numbered skeleton migration file."""
    click.echo(run_migration(get_runner().create, name))


@fp.command()
def initial():
    """Write an initial migration creating every model table."""
    runner = get_runner()
    if runner.migrations():
        raise click.ClickException(
            'migrations already exist in "%s".' % runner.directory)
    diff = run_migration(get_diff, runner, initial=True)
    click.echo(run_migration(runner.create, 'initial', template(diff)))


@fp.command()
@click.argument('name')
def generate(name):
    """Write a migration from the diff between models and database."""
    runner = get_runner()
    diff = run_migration(get_diff, runner)
    if not diff:
        click.echo('schema matches models. Nothing to generate.')
        return
    click.echo(run_migration(runner.create, name, template(diff)))


@fp.command()
def diff():
    """Print the schema changes needed to match the models."""
    schema_diff = run_migration(get_diff, get_runner())
    click.echo(schema_diff if schema_diff else 'schema matches models.')
