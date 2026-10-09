
from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import User


def get_user_by_username(username):
    """Find a user by username, ignoring letter case."""
    normalized = username.strip().lower()

    statement = select(User).where(
        func.lower(User.username) == normalized
    )

    return db.session.scalar(statement)


def get_user_by_email(email):
    """Find a user by email, ignoring letter case."""
    normalized = email.strip().lower()

    statement = select(User).where(
        func.lower(User.email) == normalized
    )

    return db.session.scalar(statement)


def get_user_by_identity(identity):
    """Find a user by username or email."""
    normalized = identity.strip().lower()

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
