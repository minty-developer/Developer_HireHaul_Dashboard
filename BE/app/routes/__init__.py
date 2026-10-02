from flask import Blueprint

bp = Blueprint("main", __name__)

from . import home
from . import health
from . import jobs
from . import stats
from . import sync