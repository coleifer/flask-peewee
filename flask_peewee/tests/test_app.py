import datetime

from flask import Flask, request, redirect, url_for, render_template, flash, g, Response

from peewee import *

# flask-peewee bindings
from flask_peewee.admin import Admin, ModelAdmin, AdminPanel
from flask_peewee.auth import Auth, BaseUser
from flask_peewee.db import Database
from flask_peewee.filters import QueryFilter
from flask_peewee.rest import RestAPI, RestResource, RestrictOwnerResource, UserAuthentication, AdminAuthentication, APIKeyAuthentication
from flask_peewee.utils import get_object_or_404, object_list, make_password


class TestFlask(Flask):
    def update_template_context(self, context):
        ret = super(TestFlask, self).update_template_context(context)
        self._template_context.update(context)
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


class TestModel(db.Model):
    data = TextField()
    
    class Meta:
        ordering = ('id',)


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


class APIKey(db.Model):
    key = CharField()
    secret = CharField()


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
            'note_list': Note.select().order_by(('created_date', 'desc')).paginate(1, 3)
        }


auth = Auth(app, db, user_model=User)
admin = Admin(app, auth)


a_qf = QueryFilter(AModel.select())
bd_qf = QueryFilter(BDetails.select())
b_qf = QueryFilter(BModel.select(), related=[a_qf, bd_qf])
c_qf = QueryFilter(CModel.select(), related=[b_qf])
d_qf = QueryFilter(DModel.select(), related=[c_qf])

class AAdmin(ModelAdmin):
    columns = ('a_field',)

class BAdmin(ModelAdmin):
    columns = ('a', 'b_field',)
    related_filters = [a_qf]

class CAdmin(ModelAdmin):
    columns = ('b', 'c_field',)
    related_filters = [b_qf]

class DAdmin(ModelAdmin):
    columns = ('c', 'd_field',)
    related_filters = [c_qf]

class MessageAdmin(ModelAdmin):
    columns = ('user', 'content', 'pub_date',)

class NoteAdmin(ModelAdmin):
    columns = ('user', 'message', 'created_date',)


auth.register_admin(admin)
admin.register(AModel, AAdmin)
admin.register(BModel, BAdmin)
admin.register(CModel, CAdmin)
admin.register(DModel, DAdmin)
admin.register(BDetails)
admin.register(Message, MessageAdmin)
admin.register(Note, NoteAdmin)
admin.register_panel('Notes', NotePanel)


class UserResource(RestResource):
    exclude = ('password', 'email',)
    
    def get_query(self):
        return User.filter(active=True)


# rest api stuff
user_auth = UserAuthentication(auth)
admin_auth = AdminAuthentication(auth)
api_key_auth = APIKeyAuthentication(APIKey, ['GET', 'POST', 'PUT', 'DELETE'])

api = RestAPI(app, default_auth=user_auth)

api.register(Message, RestrictOwnerResource)
api.register(User, UserResource, auth=admin_auth)
api.register(Note)
api.register(TestModel, auth=api_key_auth)


# views
@app.route('/')
def homepage():
    return Response()

@app.route('/private/')
@auth.login_required
def private_timeline():
    return Response()


admin.setup()
api.setup()
