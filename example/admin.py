import datetime
from flask import request, redirect

from flask_peewee.admin import Admin, ModelAdmin, AdminPanel
from flask_peewee.filters import QueryFilter

from app import app, db
from auth import auth
from models import User, Message, Note, Relationship


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

class UserStatsPanel(AdminPanel):
    template_name = 'admin/user_stats.html'

    def get_context(self):
        last_week = datetime.datetime.now() - datetime.timedelta(days=7)
        signups_this_week = User.select().where(User.join_date > last_week).count()
        messages_this_week = Message.select().where(Message.pub_date > last_week).count()
        return {
            'signups': signups_this_week,
            'messages': messages_this_week,
        }


admin = Admin(app, auth, branding='Example Site')


class MessageAdmin(ModelAdmin):
    columns = ('user', 'content', 'pub_date',)
    foreign_key_lookups = {'user': 'username'}
    filter_fields = ('user', 'content', 'pub_date', 'user__username')

class NoteAdmin(ModelAdmin):
    columns = ('user', 'message', 'created_date',)
    exclude = ('created_date',)


auth.register_admin(admin)
admin.register(Relationship)
admin.register(Message, MessageAdmin)
admin.register(Note, NoteAdmin)
admin.register_panel('Notes', NotePanel)
admin.register_panel('User stats', UserStatsPanel)
