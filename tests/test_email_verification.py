import time
from urllib.parse import urlparse

import pytest
from app import create_app
from app.extensions import db
from app.models import User
from app.services.email_service import EmailDeliveryError, generate_verification_token
from werkzeug.security import generate_password_hash

class EmailTestConfig:
    TESTING = True
    SECRET_KEY = "email-tests-only"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REQUIRE_EMAIL_VERIFICATION = True
    EMAIL_VERIFICATION_TOKEN_MAX_AGE = 3600


@pytest.fixture
def app():
    test_app = create_app(EmailTestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def registration_data(username, email, marketing_opt_in=False):
    data = {
        "username": username,
        "email": email,
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
    }
    if marketing_opt_in:
        data["marketing_opt_in"] = "y"
    return data


@pytest.mark.parametrize("opt_in", [True, False])
def test_registration_requires_verification_and_saves_marketing_choice(
    app, client, monkeypatch, opt_in
):
    sent = {}

    def fake_send(user, verification_url):
        sent["url"] = verification_url
        return True

    monkeypatch.setattr(
        "app.routes.auth.send_verification_email", fake_send
    )

    username = f"emailuser{int(opt_in)}"
    email = f"{username}@example.com"

    response = client.post(
        "/register",
        data=registration_data(username, email, opt_in),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your account was created successfully." in response.data
    assert "url" in sent

    with app.app_context():
        user = db.session.query(User).filter_by(email=email).one()
        user_id = user.id
        assert user.email_verified is False
        assert user.marketing_opt_in is opt_in

    # An unverified user cannot log in.
    response = client.post(
        "/login",
        data={"identity": username, "password": "StrongPass123!"},
        follow_redirects=True,
    )
    assert b"verify your email address" in response.data.lower()

    # Open the verification URL captured from the mocked email.
    verify_path = urlparse(sent["url"]).path
    response = client.get(verify_path, follow_redirects=True)
    assert response.status_code == 200
    assert b"Email verified successfully." in response.data

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.email_verified is True
        assert user.email_verified_at is not None

    # Login succeeds after verification.
    response = client.post(
        "/login",
        data={"identity": username, "password": "StrongPass123!"},
        follow_redirects=True,
    )
    assert b"You have logged in successfully." in response.data


def test_invalid_verification_token_is_rejected(client):
    response = client.get(
        "/verify-email/not-a-valid-token", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"invalid or expired" in response.data.lower()


def test_expired_verification_token_is_rejected(app, client):
    with app.app_context():
        app.config["EMAIL_VERIFICATION_TOKEN_MAX_AGE"] = 1
        user = User(
            username="expireduser",
            email="expired@example.com",
            password_hash="not-used-for-login",
            email_verified=False,
        )
        db.session.add(user)
        db.session.commit()
        token = generate_verification_token(user)
        user_id = user.id

    time.sleep(2)

    response = client.get(
        f"/verify-email/{token}", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"invalid or expired" in response.data.lower()

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.email_verified is False
        assert user.email_verified_at is None

def test_resend_verification_respects_cooldown(app, client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.send_verification_email",
        lambda user, link: sent.append((user.email, link)) or True,
    )

    with app.app_context():
        db.session.add(User(
            username="resenduser", email="resend@example.com",
            password_hash="unused", email_verified=False,
        ))
        db.session.commit()

    data = {"email": "resend@example.com"}
    first = client.post("/resend-verification", data=data, follow_redirects=True)
    assert first.status_code == 200
    assert b"If this address belongs" in first.data
    assert len(sent) == 1

    with app.app_context():
        user = db.session.query(User).filter_by(email="resend@example.com").one()
        assert user.verification_email_sent_at is not None

    # A second immediate request must not send another email.
    second = client.post("/resend-verification", data=data, follow_redirects=True)
    assert second.status_code == 200
    assert b"If this address belongs" in second.data
    assert len(sent) == 1

def test_customer_can_update_marketing_preferences(app, client):
    password = "StrongPass123!"
    with app.app_context():
        user = User(
            username="preferencesuser",
            email="preferences@example.com",
            password_hash=generate_password_hash(password),
            email_verified=True,
            marketing_opt_in=False,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    login = client.post(
        "/login",
        data={"identity": "preferencesuser", "password": password},
        follow_redirects=True,
    )
    assert login.status_code == 200
    assert b"You have logged in successfully." in login.data

    # Explicitly opt in.
    response = client.post(
        "/email-preferences",
        data={"marketing_opt_in": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your email preferences have been saved." in response.data

    with app.app_context():
        assert db.session.get(User, user_id).marketing_opt_in is True

    # Submitting without the checkbox opts out.
    response = client.post("/email-preferences", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your email preferences have been saved." in response.data

    with app.app_context():
        assert db.session.get(User, user_id).marketing_opt_in is False

def test_resend_clears_cooldown_when_email_delivery_fails(
    app, client, monkeypatch
):
    with app.app_context():
        db.session.add(User(
            username="resendfailuser",
            email="resendfail@example.com",
            password_hash="unused",
            email_verified=False,
        ))
        db.session.commit()

    def fail_send(user, link):
        raise EmailDeliveryError("Simulated SMTP failure.")

    monkeypatch.setattr(
        "app.services.email_service.send_verification_email", fail_send
    )

    response = client.post(
        "/resend-verification",
        data={"email": "resendfail@example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"If this address belongs" in response.data

    with app.app_context():
        user = db.session.query(User).filter_by(
            email="resendfail@example.com"
        ).one()
        assert user.verification_email_sent_at is None

def test_registration_clears_cooldown_when_email_delivery_fails(
    app, client, monkeypatch
):
    def fail_send(user, link):
        raise EmailDeliveryError("Simulated SMTP failure.")

    monkeypatch.setattr(
        "app.routes.auth.send_verification_email", fail_send
    )

    response = client.post(
        "/register",
        data=registration_data(
            "registerfailuser", "registerfail@example.com"
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your account was created" in response.data
    assert b"verification email could not be sent" in response.data

    with app.app_context():
        user = db.session.query(User).filter_by(
            email="registerfail@example.com"
        ).one()
        assert user.email_verified is False
        assert user.verification_email_sent_at is None