from flask import Blueprint

main = Blueprint('main', __name__)

from . import errors
from .views import auth, reset_password, create_user, status, notifications, cookie_settings
