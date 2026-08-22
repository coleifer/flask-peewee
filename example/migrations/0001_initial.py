# Generated from a schema diff on 2026-08-22 17:32.
from peewee import *
import datetime

def up(migrator, db):
    class User(Model):
        username = CharField()
        password = CharField()
        email = CharField()
        join_date = DateTimeField(default=datetime.datetime.now)
        active = BooleanField(default=True)
        admin = BooleanField(default=False)
        class Meta:
            database = db
            table_name = 'user'
    db.create_tables([User])

    class Message(Model):
        user = ForeignKeyField(User)
        content = TextField()
        pub_date = DateTimeField(default=datetime.datetime.now)
        class Meta:
            database = db
            table_name = 'message'
    db.create_tables([Message])

    class Note(Model):
        user = ForeignKeyField(User)
        message = TextField()
        status = IntegerField(null=True)
        created_date = DateTimeField(default=datetime.datetime.now)
        class Meta:
            database = db
            table_name = 'note'
    db.create_tables([Note])

    class Relationship(Model):
        from_user = ForeignKeyField(User)
        to_user = ForeignKeyField(User)
        class Meta:
            database = db
            table_name = 'relationship'
    db.create_tables([Relationship])


def down(migrator, db):
    migrator.migrate(migrator.drop_table('relationship'))
    migrator.migrate(migrator.drop_table('note'))
    migrator.migrate(migrator.drop_table('message'))
    migrator.migrate(migrator.drop_table('user'))
