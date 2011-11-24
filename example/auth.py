from flask_peewee.auth import Auth

from app import app, db
from models import User


auth = Auth(app, db, user_model=User)
