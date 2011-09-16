import datetime

from flask import Flask, request, redirect, url_for, render_template, flash
from hashlib import md5, sha1

from peewee import *

# flask-peewee bindings
from flaskext.admin import Admin, ModelAdmin, AdminPanel
from flaskext.auth import Auth
from flaskext.db import Peewee
from flaskext.rest import RestAPI, RestResource, UserAuthentication
from flaskext.utils import get_object_or_404, object_list


app = Flask(__name__)
app.config.from_object('config.Configuration')

db = Peewee(app)

# model definitions
class User(db.Model):
    username = CharField()
    password = CharField()
    email = CharField()
    join_date = DateTimeField(default=datetime.datetime.now)
    active = BooleanField(default=True)
    admin = BooleanField(default=False)

    def __unicode__(self):
        return self.username

    def set_password(self, password):
        self.password = sha1(password).hexdigest()

    def following(self):
        return User.select().join(
            Relationship, on='to_user_id'
        ).where(from_user=self).order_by('username')

    def followers(self):
        return User.select().join(
            Relationship
        ).where(to_user=self).order_by('username')

    def is_following(self, user):
        return Relationship.filter(
            from_user=self,
            to_user=user
        ).exists()

    def gravatar_url(self, size=80):
        return 'http://www.gravatar.com/avatar/%s?d=identicon&s=%d' % \
            (md5(self.email.strip().lower().encode('utf-8')).hexdigest(), size)


class Relationship(db.Model):
    from_user = ForeignKeyField(User, related_name='relationships')
    to_user = ForeignKeyField(User, related_name='related_to')
    
    def __unicode__(self):
        return 'Relationship from %s to %s' % (self.from_user, self.to_user)


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

class UserStatsPanel(AdminPanel):
    template_name = 'admin/user_stats.html'
    
    def get_context(self):
        last_week = datetime.datetime.now() - datetime.timedelta(days=7)
        signups_this_week = User.filter(join_date__gt=last_week).count()
        messages_this_week = Message.filter(pub_date__gt=last_week).count()
        return {
            'signups': signups_this_week,
            'messages': messages_this_week,
        }


auth = Auth(app, db, user_model=User)
admin = Admin(app, db, auth)


class MessageAdmin(ModelAdmin):
    columns = ('user', 'content', 'pub_date',)

class NoteAdmin(ModelAdmin):
    columns = ('user', 'message', 'created_date',)


auth.register_admin(admin)
admin.register(Relationship)
admin.register(Message, MessageAdmin)
admin.register(Note, NoteAdmin)
admin.register_panel('Notes', NotePanel)
admin.register_panel('User stats', UserStatsPanel)

# rest api stuff
rest_auth = UserAuthentication(auth)
api = RestAPI(app, default_auth=rest_auth)

class UserResource(RestResource):
    exclude = ('password',)

api.register(Message)
api.register(Relationship)
api.register(User, UserResource)

# utils
def create_tables():
    User.create_table()
    Relationship.create_table()
    Message.create_table()
    Note.create_table()


# custom filters
@app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)


# views
@app.route('/')
def homepage():
    if auth.get_logged_in_user():
        return private_timeline()
    else:
        return public_timeline()

@app.route('/private/')
@auth.login_required
def private_timeline():
    user = auth.get_logged_in_user()
    
    messages = Message.select().where(
        user__in=user.following()
    ).order_by(('pub_date', 'desc'))
    
    return object_list('private_messages.html', messages, 'message_list')

@app.route('/public/')
def public_timeline():
    messages = Message.select().order_by(('pub_date', 'desc'))
    return object_list('public_messages.html', messages, 'message_list')

@app.route('/join/', methods=['GET', 'POST'])
def join():
    if request.method == 'POST' and request.form['username']:
        try:
            user = User.get(username=request.form['username'])
            flash('That username is already taken')
        except User.DoesNotExist:
            user = User(
                username=request.form['username'],
                email=request.form['email'],
                join_date=datetime.datetime.now()
            )
            user.set_password(request.form['password'])
            user.save()
            
            auth.login_user(user)
            return redirect(url_for('homepage'))

    return render_template('join.html')

@app.route('/following/')
@auth.login_required
def following():
    user = auth.get_logged_in_user()
    return object_list('user_following.html', user.following(), 'user_list')

@app.route('/followers/')
@auth.login_required
def followers():
    user = auth.get_logged_in_user()
    return object_list('user_followers.html', user.followers(), 'user_list')

@app.route('/users/')
def user_list():
    users = User.select().order_by('username')
    return object_list('user_list.html', users, 'user_list')

@app.route('/users/<username>/')
def user_detail(username):
    user = get_object_or_404(User, username=username)
    messages = user.message_set.order_by(('pub_date', 'desc'))
    return object_list('user_detail.html', messages, 'message_list', person=user)

@app.route('/users/<username>/follow/', methods=['POST'])
@auth.login_required
def user_follow(username):
    user = get_object_or_404(User, username=username)
    Relationship.get_or_create(
        from_user=auth.get_logged_in_user(),
        to_user=user,
    )
    flash('You are now following %s' % user.username)
    return redirect(url_for('user_detail', username=user.username))

@app.route('/users/<username>/unfollow/', methods=['POST'])
@auth.login_required
def user_unfollow(username):
    user = get_object_or_404(User, username=username)
    Relationship.delete().where(
        from_user=auth.get_logged_in_user(),
        to_user=user,
    ).execute()
    flash('You are no longer following %s' % user.username)
    return redirect(url_for('user_detail', username=user.username))

@app.route('/create/', methods=['GET', 'POST'])
@auth.login_required
def create():
    user = auth.get_logged_in_user()
    if request.method == 'POST' and request.form['content']:
        message = Message.create(
            user=user,
            content=request.form['content'],
        )
        flash('Your message has been created')
        return redirect(url_for('user_detail', username=user.username))

    return render_template('create.html')

admin.setup()
api.setup()


# allow running from the command line
if __name__ == '__main__':
    app.run()
