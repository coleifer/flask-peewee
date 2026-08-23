import datetime

from flask import Flask
from flask import Response
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from peewee import *

# flask-peewee bindings
from flask_peewee.admin import Admin
from flask_peewee.admin import AdminPanel
from flask_peewee.admin import ModelAdmin
from flask_peewee.auth import Auth
from flask_peewee.auth import BaseUser
from flask_peewee.db import Database
from flask_peewee.filters import QueryFilter
from flask_peewee.rest import ALL_METHODS
from flask_peewee.rest import APIKeyAuthentication
from flask_peewee.rest import AdminAuthentication
from flask_peewee.rest import BearerAuthentication
from flask_peewee.rest import Authentication
from flask_peewee.rest import RestAPI
from flask_peewee.rest import RestResource
from flask_peewee.rest import RestrictOwnerResource
from flask_peewee.rest import UserAuthentication
from flask_peewee.rest import UserBearerAuthentication
from flask_peewee.utils import get_object_or_404
from flask_peewee.utils import make_password
from flask_peewee.utils import object_list


class TestFlask(Flask):
    def update_template_context(self, *args):
        ret = super(TestFlask, self).update_template_context(*args)
        self._template_context.update(args[-1])
        return ret


app = TestFlask(__name__)
app.config.from_object('flask_peewee.tests.test_config.Configuration')

db = Database(app)

@app.before_request
def clear_context():
    app._template_context = {}


class User(db.Model, BaseUser):
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


class Message(db.Model):
    user = ForeignKeyField(User)
    content = TextField()
    pub_date = DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return '%s: %s' % (self.user, self.content)


class Note(db.Model):
    user = ForeignKeyField(User)
    message = TextField()
    created_date = DateTimeField(default=datetime.datetime.now)


class Comment(db.Model):
    user = ForeignKeyField(User)
    body = TextField()


class Ping(db.Model):
    user = ForeignKeyField(User)
    body = TextField()


class TestModel(db.Model):
    data = TextField()

    class Meta:
        order_by = ('id',)


class AModel(db.Model):
    a_field = CharField()

class BModel(db.Model):
    a = ForeignKeyField(AModel)
    b_field = CharField()

class CModel(db.Model):
    b = ForeignKeyField(BModel)
    c_field = CharField()

class DModel(db.Model):
    c = ForeignKeyField(CModel)
    d_field = CharField()

class BDetails(db.Model):
    b = ForeignKeyField(BModel)


class EModel(db.Model):
    e_field = CharField()

class FModel(db.Model):
    e = ForeignKeyField(EModel, null=True)
    f_field = CharField()


class GModel(db.Model):
    e = ForeignKeyField(EModel, null=True)
    g_field = CharField()

class HModel(db.Model):
    a = ForeignKeyField(AModel, null=True)
    h_field = CharField()
    h_date = DateTimeField(null=True)
    h_day = DateField(null=True)


class APIKey(db.Model):
    key = CharField()
    secret = CharField()


class BearerDoc(db.Model):
    data = TextField()


class ApiToken(db.Model):
    token = CharField()
    user = ForeignKeyField(User)


class Tweet(db.Model):
    user = ForeignKeyField(User)
    content = TextField()


class TSModel(db.Model):
    # TimestampField stores an integer but represents a datetime -- exercises
    # admin filtering of timestamp columns.
    ts = TimestampField()
    label = CharField()


class ScopedItem(db.Model):
    # ScopedItemAdmin.get_query() hides rows flagged hidden, so the admin's
    # delete path and the FK picker that targets this model must respect it.
    label = CharField()
    hidden = BooleanField(default=False)


class ScopedRef(db.Model):
    item = ForeignKeyField(ScopedItem)
    name = CharField()


class Link(db.Model):
    # two foreign keys to the same model, one nullable. exercises the aliased
    # filter join (distinct paths must not collapse) and the LEFT OUTER search
    # join (a null-fk row must survive a search that matches a direct field).
    src = ForeignKeyField(User, backref='links_out')
    dst = ForeignKeyField(User, null=True, backref='links_in')
    label = TextField(default='')


class Entry(db.Model):
    # exercises EntryAdmin's readonly_fields and fieldsets. status is listed
    # in no fieldset, so it renders in the trailing unlabeled section.
    title = CharField()
    body = TextField(default='')
    status = CharField(default='draft')
    created = DateTimeField(default=datetime.datetime.now)


class NotePanel(AdminPanel):
    template_name = 'admin/notes.html'

    def get_urls(self):
        return (
            ('/create/', self.create),
        )

    def create(self):
        if request.method == 'POST':
            if request.form.get('message'):
                Note.create(
                    user=auth.get_logged_in_user(),
                    message=request.form['message'],
                )
        next = request.form.get('next') or self.dashboard_url()
        return redirect(next)

    def get_context(self):
        return {
            'note_list': Note.select().order_by(Note.created_date.desc()).paginate(1, 3)
        }


auth = Auth(app, db, user_model=User)
admin = Admin(app, auth)


class AAdmin(ModelAdmin):
    columns = ('a_field',)

class BAdmin(ModelAdmin):
    columns = ('a', 'b_field',)
    include_foreign_keys = {'a': 'a_field'}

class CAdmin(ModelAdmin):
    columns = ('b', 'c_field',)
    include_foreign_keys = {'b': 'b_field'}

class DAdmin(ModelAdmin):
    columns = ('c', 'd_field',)
    include_foreign_keys = {'c': 'c_field'}

class MessageAdmin(ModelAdmin):
    columns = ('user', 'content', 'pub_date',)
    search_fields = ('content', 'user__username',)

class NoteAdmin(ModelAdmin):
    columns = ('user', 'message', 'created_date',)

class ScopedItemAdmin(ModelAdmin):
    # scope every path, including delete, to non-hidden rows.
    def get_query(self):
        return ScopedItem.select().where(ScopedItem.hidden == False)

class ScopedRefAdmin(ModelAdmin):
    foreign_key_lookups = {'item': 'label'}

class EntryAdmin(ModelAdmin):
    # mirrors the readonly_fields/fieldsets example in docs/admin.rst.
    readonly_fields = ('created',)
    fieldsets = [
        ('Content', {'fields': ('title', 'body')}),
        ('Meta', {'fields': ('created',), 'collapsed': True}),
    ]

class ReadOnlyCommentAdmin(ModelAdmin):
    columns = ('user', 'body',)
    can_add = can_edit = can_delete = False

class PingAdmin(ModelAdmin):
    # user-aware check_edit, plus can_delete off so the edit page renders
    # without its Delete button.
    can_delete = False

    def check_edit(self, user):
        return user.username == 'admin'


auth.register_admin(admin)
admin.register(AModel, AAdmin)
admin.register(BModel, BAdmin)
admin.register(CModel, CAdmin)
admin.register(DModel, DAdmin)
admin.register(BDetails)
admin.register(Message, MessageAdmin)
admin.register(Note, NoteAdmin)
admin.register(ScopedItem, ScopedItemAdmin)
admin.register(ScopedRef, ScopedRefAdmin)
admin.register(Entry, EntryAdmin)
admin.register(Comment, ReadOnlyCommentAdmin)
admin.register(Ping, PingAdmin)
admin.register_panel('Notes', NotePanel)


class UserResource(RestResource):
    exclude = ('password', 'email',)
    readonly_fields = ('admin',)

    def get_query(self):
        return User.select().where(User.active==True)

class AResource(RestResource):
    pass

class BResource(RestResource):
    include_resources = {'a': AResource}

class CResource(RestResource):
    include_resources = {'b': BResource}

class EResource(RestResource):
    paginate_by = None    # no default pagination -> single-page envelope
    max_paginate_by = 5   # but cap an explicit ?limit at 5

class FResource(RestResource):
    include_resources = {'e': EResource}

class CommentResource(RestrictOwnerResource):
    # nests the admin-only UserResource, which marks "admin" read-only
    owner_field = 'user'
    include_resources = {'user': UserResource}

class GResource(RestResource):
    # nesting is read-only: a nested {...} write is ignored.
    include_resources = {'e': EResource}
    nested_writes = False

class HResource(RestResource):
    # unrecognized keys are rejected with a 400, on writes and on filters.
    reject_unknown_fields = True
    reject_unknown_filters = True

class AdminOnlyUserResource(UserResource):
    # user writes (even nested) require an admin -- exercises check_*
    # enforcement on nested writes.
    def check_post(self, obj=None):
        return bool(getattr(g, 'user', None) and g.user.admin)
    def check_put(self, obj):
        return bool(getattr(g, 'user', None) and g.user.admin)

class PingResource(RestResource):
    include_resources = {'user': AdminOnlyUserResource}

# rest api stuff
dummy_auth = Authentication(protected_methods=[])
user_auth = UserAuthentication(auth)
admin_auth = AdminAuthentication(auth)
api_key_auth = APIKeyAuthentication(APIKey, ALL_METHODS)

class KeyBearerAuthentication(BearerAuthentication):
    token_field = 'key'  # reuse the APIKey.key column as the bearer token

bearer_auth = KeyBearerAuthentication(APIKey, ALL_METHODS)

class TweetResource(RestrictOwnerResource):
    owner_field = 'user'

# resolves a token (ApiToken.token) to ApiToken.user and sets g.user
user_bearer_auth = UserBearerAuthentication(ApiToken)

api = RestAPI(app, default_auth=user_auth)

api.register(Message, RestrictOwnerResource)
api.register(User, UserResource, auth=admin_auth)
api.register(Note)
api.register(Comment, CommentResource)
api.register(Ping, PingResource)
api.register(TestModel, auth=api_key_auth)
api.register(BearerDoc, auth=bearer_auth)
api.register(Tweet, TweetResource, auth=user_bearer_auth)
api.register(AModel, AResource, auth=dummy_auth)
api.register(BModel, BResource, auth=dummy_auth)
api.register(CModel, CResource, auth=dummy_auth)

api.register(EModel, EResource, auth=dummy_auth)
api.register(FModel, FResource, auth=dummy_auth)
api.register(GModel, GResource, auth=dummy_auth)
api.register(HModel, HResource, auth=dummy_auth)
api.register(Link, auth=dummy_auth)


# views
@app.route('/')
def homepage():
    return Response()

@app.route('/private/')
@auth.login_required
def private_timeline():
    return Response()

@app.route('/secret/')
@auth.admin_required
def secret_area():
    return Response()


admin.setup()
api.setup()
