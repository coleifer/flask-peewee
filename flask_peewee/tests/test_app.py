import datetime

from flask import Flask, Response
from flask_login import login_user, logout_user, LoginManager, UserMixin

from peewee import (
    BooleanField, CharField, DateTimeField,
    ForeignKeyField, TextField,
    Model, SqliteDatabase,
)

# flask-peewee bindings
from flask_peewee.rest import AdminAuthentication
from flask_peewee.rest import Authentication
from flask_peewee.rest import RestAPI
from flask_peewee.rest import RestResource
from flask_peewee.rest import RestrictOwnerResource


class FlaskApp(Flask):
    def update_template_context(self, context):
        ret = super(FlaskApp, self).update_template_context(context)
        self._template_context.update(context)
        return ret


app = FlaskApp(__name__)
app.config.from_object('flask_peewee.tests.test_config.Configuration')

login_manager = LoginManager()
login_manager.init_app(app)

db = SqliteDatabase(':memory:')


class BaseModel(Model):
    class Meta:
        database = db


@login_manager.user_loader
def load_user(user_id):
    return User.get(User.id == user_id)


@app.before_request
def clear_context():
    app._template_context = {}


class User(BaseModel, UserMixin):
    username = CharField()
    password = CharField()
    email = CharField()
    join_date = DateTimeField(default=datetime.datetime.now)
    active = BooleanField(default=True)
    admin = BooleanField(default=False, verbose_name='Can access admin')

    def __unicode__(self):
        return self.username

    def __hash__(self):
        return hash(self.username)

    def message_count(self):
        return self.message_set.count()


class Message(BaseModel):
    user = ForeignKeyField(User)
    content = TextField()
    pub_date = DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return '%s: %s' % (self.user, self.content)


class Note(BaseModel):
    user = ForeignKeyField(User)
    message = TextField()
    created_date = DateTimeField(default=datetime.datetime.now)


class AModel(BaseModel):
    a_field = CharField()


class BModel(BaseModel):
    a = ForeignKeyField(AModel)
    b_field = CharField()


class CModel(BaseModel):
    b = ForeignKeyField(BModel)
    c_field = CharField()


class DModel(BaseModel):
    c = ForeignKeyField(CModel)
    d_field = CharField()


class BDetails(BaseModel):
    b = ForeignKeyField(BModel)


class EModel(BaseModel):
    e_field = CharField()


class FModel(BaseModel):
    e = ForeignKeyField(EModel, null=True)
    f_field = CharField()


class DeletableResource(RestResource):

    def check_delete(self, obj):
        return True


class UserResource(DeletableResource):
    exclude = ('password', 'email',)

    def get_query(self):
        return User.select().where(User.active >> True)


class AResource(DeletableResource):
    pass


class BResource(DeletableResource):
    include_resources = {'a': AResource}


class CResource(DeletableResource):
    include_resources = {'b': BResource}


class EResource(DeletableResource):
    pass


class FResource(DeletableResource):
    include_resources = {'e': EResource}


# rest api stuff
dummy_auth = Authentication(protected_methods=[])
admin_auth = AdminAuthentication()

api = RestAPI(app, default_auth=dummy_auth)

api.register(Message, RestrictOwnerResource)
api.register(User, UserResource, auth=admin_auth)
api.register(Note, DeletableResource)
api.register(AModel, AResource, auth=dummy_auth)
api.register(BModel, BResource, auth=dummy_auth)
api.register(CModel, CResource, auth=dummy_auth)

api.register(EModel, EResource, auth=dummy_auth)
api.register(FModel, FResource, auth=dummy_auth)


# views
@app.route('/')
def homepage():
    return Response()


@app.route('/login/<pk>')
def login(pk):
    login_user(User.get(User.id == pk), remember=True)
    return "ok"


@app.route('/logout')
def logout():
    logout_user()
    return "ok"


api.setup()
