from flask import Blueprint

bp = Blueprint("main", __name__)

from . import home
from . import health
from . import admin_sync
from . import articles
from . import blogs
