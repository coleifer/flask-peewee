from flaskext.auth import Auth

from app import app, db
from models import User


auth = Auth(app, db, user_model=User)
