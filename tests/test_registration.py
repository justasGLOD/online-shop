
import pytest

from sqlalchemy import select
from werkzeug.security import check_password_hash

from app import create_app
from app.extensions import db
from app.models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "registration-test-secret"
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


def registration_data(**overrides):
    data = {
        "username": "testuser01",
        "email": "testuser01@example.com",
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
    }
    data.update(overrides)
    return data


def test_registration_success(client, app):
    response = client.post(
        "/register",
        data=registration_data(),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your account was created successfully." in response.data

    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.username == "testuser01")
        )

        assert user is not None
        assert user.password_hash != "StrongPass123!"
        assert check_password_hash(
            user.password_hash,
            "StrongPass123!",
        )


def test_duplicate_username_is_rejected(client):
    client.post("/register", data=registration_data())

    response = client.post(
        "/register",
        data=registration_data(email="another@example.com"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"That username is already taken." in response.data


def test_duplicate_email_is_rejected(client):
    client.post("/register", data=registration_data())

    response = client.post(
        "/register",
        data=registration_data(username="anotheruser"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"That email address is already registered." in response.data


def test_weak_password_is_rejected(client):
    response = client.post(
        "/register",
        data=registration_data(
            password="weakpassword",
            confirm_password="weakpassword",
        ),
    )

    assert response.status_code == 200
    assert b"Password must contain" in response.data


def test_password_confirmation_must_match(client):
    response = client.post(
        "/register",
        data=registration_data(
            confirm_password="DifferentPass123!",
        ),
    )

    assert response.status_code == 200
    assert b"The passwords do not match." in response.data
