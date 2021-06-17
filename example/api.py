from flask_peewee.rest import RestAPI, RestResource, RestrictOwnerResource

from app import app
from auth import auth
from models import User, Message, Note, Relationship


admin_auth = AdminAuthentication()

# instantiate our api wrapper
api = RestAPI(app, default_auth=user_auth)


class UserResource(RestResource):
    exclude = ('password', 'email',)


class MessageResource(RestrictOwnerResource):
    owner_field = 'user'
    include_resources = {'user': UserResource}


class RelationshipResource(RestrictOwnerResource):
    owner_field = 'from_user'
    include_resources = {
        'from_user': UserResource,
        'to_user': UserResource,
    }
    paginate_by = None


class NoteResource(RestrictOwnerResource):
    owner_field = 'user'
    include_resources = {
        'user': UserResource,
    }

    def get_query(self):
        query = super().get_query()
        return query.where(Note.status == 1)


# register our models so they are exposed via /api/<model>/
api.register(User, UserResource, auth=admin_auth)
api.register(Relationship, RelationshipResource)
api.register(Message, MessageResource)
api.register(Note, NoteResource)
