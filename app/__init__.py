from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config
import os

# Initialize extensions (outside the factory function)
db = SQLAlchemy()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)

    # Initialize extensions with the app
    db.init_app(app)

    # Import and register blueprints or routes here later
    from . import routes
    app.register_blueprint(routes.bp)

    # Import models here to ensure they are known to SQLAlchemy before db creation
    from . import models

    # Create database tables if they don't exist
    # Use app context to ensure configurations are loaded
    with app.app_context():
         db.create_all() # Creates tables based on models defined in models.py

    return app 