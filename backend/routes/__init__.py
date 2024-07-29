# routes/__init__.py
from flask import Blueprint

# Create blueprints
client_bp = Blueprint('client_bp', __name__)
transaction_bp = Blueprint('transaction_bp', __name__)
excel_routes_bp = Blueprint('excel_routes_bp', __name__)
dash_routes_bp = Blueprint('dash_routes_bp', __name__)

from . import client_routes, transaction_routes, excel_routes, dashboard_routes

