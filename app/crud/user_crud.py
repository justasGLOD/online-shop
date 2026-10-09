from sqlalchemy import func, select

from app.extensions import db
from app.models import User


def get_user_by_username(username):
    """Find a user by username, ignoring letter case."""
    normalized_username = username.strip().casefold()

    statement = select(User).where(
        func.lower(User.username) == normalized_username
    )

    return db.session.scalar(statement)


def get_user_by_email(email):
    """Find a user by email, ignoring letter case."""
    normalized_email = email.strip().lower()

    statement = select(User).where(
        func.lower(User.email) == normalized_email
    )

    return db.session.scalar(statement)


def create_user(user):
    """Save a new user to the database."""
    db.session.add(user)
    db.session.commit()

    return user