from flask import Flask

# flask-peewee bindings
from flaskext.db import Peewee


app = Flask(__name__)
app.config.from_object('config.Configuration')

db = Peewee(app)


def create_tables():
    User.create_table()
    Relationship.create_table()
    Message.create_table()
    Note.create_table()


@app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)
