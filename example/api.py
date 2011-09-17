from flaskext.rest import RestAPI, RestResource, UserAuthentication

from app import app
from auth import auth
from models import User, Message, Relationship


user_auth = UserAuthentication(auth)
api = RestAPI(app, default_auth=user_auth)

class UserResource(RestResource):
    exclude = ('password',)


api.register(Message)
api.register(Relationship)
api.register(User, UserResource)
