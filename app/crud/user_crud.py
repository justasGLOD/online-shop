
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import User


def get_user_by_username(username):
    """Find a user by username, ignoring letter case."""
    normalized = (username or "").strip().lower()
    statement = select(User).where(
        func.lower(User.username) == normalized
    )
    return db.session.scalar(statement)


def get_user_by_email(email):
    """Find a user by email, ignoring letter case."""
    normalized = (email or "").strip().lower()
    statement = select(User).where(
        func.lower(User.email) == normalized
    )
    return db.session.scalar(statement)


def get_user_by_identity(identity):
    """Find a user by username or email."""
    normalized = (identity or "").strip().lower()
    statement = select(User).where(
        or_(
            func.lower(User.username) == normalized,
            func.lower(User.email) == normalized,
        )
    )
    return db.session.scalar(statement)


def create_user(user):
    """Save a new user to the database."""
    db.session.add(user)
    db.session.commit()
    return user


def get_all_users():
    """Return registered users for the admin management page."""
    statement = select(User).order_by(User.id.asc())
    return db.session.scalars(statement).all()


def get_user_for_admin(user_id):
    """Find a registered user by ID for administration."""
    return db.session.get(User, user_id)


def deactivate_user(user):
    """Deactivate an account without deleting its records."""
    user.is_active = False
    db.session.commit()
    return user

def delete_user(user):
    """Delete a user account and commit the database transaction."""
    db.session.delete(user)
    db.session.commit()