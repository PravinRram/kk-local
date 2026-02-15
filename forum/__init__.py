from flask import Blueprint

forum_bp = Blueprint('forum', __name__)

from . import routes