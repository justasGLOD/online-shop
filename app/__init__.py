
from flask import Flask

from config import Config
from .extensions import db, login_manager, migrate

@login_manager.user_loader
def load_user(user_id):
    """Load a logged-in user from the database."""
    from .models import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Import models so SQLAlchemy and Flask-Migrate can discover them.
    from . import models

    # Import the application's route blueprints.
    from .routes.auth import auth_bp
    from .routes.products import products_bp
    from .routes.admin_products import admin_bp
    from .routes.cart import cart_bp
    from .routes.checkout import checkout_bp
    from .routes.balance import balance_bp
    from .routes.reviews import reviews_bp
    from .routes.orders import orders_bp
    from .routes.payments import payments_bp

    # Register every blueprint with the application.
    for blueprint in (
        auth_bp,
        products_bp,
        admin_bp,
        cart_bp,
        checkout_bp,
        balance_bp,
        reviews_bp,
        orders_bp,
        payments_bp,
    ):
        app.register_blueprint(blueprint)

    return app
