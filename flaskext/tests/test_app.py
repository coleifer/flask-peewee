import datetime

from flask import Flask, request, redirect, url_for, render_template, flash, g, Response

from peewee import *

# flask-peewee bindings
from flaskext.admin import Admin, ModelAdmin, AdminPanel
from flaskext.auth import Auth
from flaskext.db import Database
from flaskext.rest import RestAPI, RestResource, RestrictOwnerResource, UserAuthentication, AdminAuthentication
from flaskext.utils import get_object_or_404, object_list, make_password


class TestFlask(Flask):
    def update_template_context(self, context):
        ret = super(TestFlask, self).update_template_context(context)
        self._template_context.update(context)
        return ret


app = TestFlask(__name__)
app.config.from_object('flaskext.tests.test_config.Configuration')

db = Database(app)

@app.before_request
def clear_context():
    app._template_context = {}


class User(db.Model):
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

    def set_password(self, password):
        self.password = make_password(password)


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


class MessageAdmin(ModelAdmin):
    columns = ('user', 'content', 'pub_date',)

class NoteAdmin(ModelAdmin):
    columns = ('user', 'message', 'created_date',)


auth.register_admin(admin)
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

api = RestAPI(app, default_auth=user_auth)

api.register(Message, RestrictOwnerResource)
api.register(User, UserResource, auth=admin_auth)
api.register(Note)


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
