
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "authentication-test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def app():
    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app):
    """Create a test account in the isolated test database."""
    with app.app_context():
        user = User(
            username="testuser01",
            email="testuser01@example.com",
            password_hash=generate_password_hash("StrongPass123!"),
        )

        db.session.add(user)
        db.session.commit()

        return {
            "username": user.username,
            "email": user.email,
            "password": "StrongPass123!",
        }


def submit_login(client, identity, password):
    return client.post(
        "/login",
        data={
            "identity": identity,
            "password": password,
        },
        follow_redirects=True,
    )


def test_login_with_username(client, registered_user):
    response = submit_login(
        client,
        registered_user["username"],
        registered_user["password"],
    )

    assert response.status_code == 200
    assert b"You have logged in successfully." in response.data
    assert b"Welcome, " in response.data
    assert b"testuser01" in response.data


def test_login_with_email(client, registered_user):
    response = submit_login(
        client,
        registered_user["email"],
        registered_user["password"],
    )

    assert response.status_code == 200
    assert b"You have logged in successfully." in response.data


def test_invalid_password_is_rejected(client, registered_user):
    response = submit_login(
        client,
        registered_user["username"],
        "WrongPassword123!",
    )

    assert response.status_code == 200
    assert b"Invalid username/email or password." in response.data


def test_three_failed_attempts_block_account(client, registered_user):
    for _ in range(3):
        response = submit_login(
            client,
            registered_user["username"],
            "WrongPassword123!",
        )

    assert b"blocked for 5 minutes" in response.data

    # Even the correct password must be rejected during the lockout.
    response = submit_login(
        client,
        registered_user["username"],
        registered_user["password"],
    )

    assert b"Too many failed login attempts" in response.data
    assert b"Welcome, testuser01!" not in response.data


def test_fourth_failed_attempt_triggers_one_hour_lockout(
    client,
    app,
    registered_user,
):
    # Trigger the initial five-minute lockout.
    for _ in range(3):
        submit_login(
            client,
            registered_user["username"],
            "WrongPassword123!",
        )

    # Simulate the five-minute lockout having expired.
    # This changes only the isolated test database.
    with app.app_context():
        user = db.session.scalar(
            select(User).where(
                User.username == registered_user["username"]
            )
        )

        user.blocked_until = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        db.session.commit()

    # The next failed attempt should trigger the one-hour lockout.
    response = submit_login(
        client,
        registered_user["username"],
        "WrongPassword123!",
    )

    assert b"blocked for 1 hour" in response.data


def test_successful_login_resets_failed_attempts(
    client,
    app,
    registered_user,
):
    submit_login(
        client,
        registered_user["username"],
        "WrongPassword123!",
    )

    response = submit_login(
        client,
        registered_user["username"],
        registered_user["password"],
    )

    assert b"You have logged in successfully." in response.data

    with app.app_context():
        user = db.session.scalar(
            select(User).where(
                User.username == registered_user["username"]
            )
        )

        assert user.failed_login_attempts == 0
        assert user.blocked_until is None


def test_logout_clears_authenticated_session(client, registered_user):
    submit_login(
        client,
        registered_user["username"],
        registered_user["password"],
    )

    with client.session_transaction() as session:
        assert "_user_id" in session

    response = client.post(
        "/logout",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"You have logged out successfully." in response.data
    assert b"Create an account" in response.data

    with client.session_transaction() as session:
        assert "_user_id" not in session
