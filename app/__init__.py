from flask import Flask

from config import Config
from .extensions import db, migrate, login_manager

@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database for Flask-Login."""
    from .models import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register models for SQLAlchemy and Flask-Migrate.
    from . import models

    # Register application blueprints.
    from .routes.auth import auth_bp
    from .routes.products import products_bp
    from .routes.admin_products import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(admin_bp)

    return app
