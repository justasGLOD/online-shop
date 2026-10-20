from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User
from app.services.email_service import EmailDeliveryError


class TestConfig:
    TESTING = True
    SECRET_KEY = "marketing-tests-only"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def accounts(app):
    with app.app_context():
        admin = User(
            username="campaignadmin",
            email="campaignadmin@example.com",
            password_hash=generate_password_hash("AdminPass123!"),
            is_admin=True,
            is_active=True,
            email_verified=True,
        )
        customer = User(
            username="regularcustomer",
            email="regularcustomer@example.com",
            password_hash=generate_password_hash("CustomerPass123!"),
            is_admin=False,
            is_active=True,
            email_verified=True,
        )
        db.session.add_all([admin, customer])
        db.session.commit()
    return {
        "admin": ("campaignadmin", "AdminPass123!"),
        "customer": ("regularcustomer", "CustomerPass123!"),
    }


def login_as(client, credentials):
    username, password = credentials
    return client.post(
        "/login",
        data={"identity": username, "password": password},
        follow_redirects=True,
    )


def test_marketing_campaign_requires_login(client):
    response = client.get("/admin/marketing")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_regular_customer_cannot_access_marketing_campaign(
    client, accounts
):
    login_as(client, accounts["customer"])
    assert client.get("/admin/marketing").status_code == 403


def test_admin_can_view_marketing_campaign(client, accounts):
    login_as(client, accounts["admin"])
    response = client.get("/admin/marketing")
    assert response.status_code == 200
    assert b"Marketing Campaign" in response.data


def test_campaign_only_sends_to_eligible_customers(
    app, client, accounts, monkeypatch
):
    with app.app_context():
        users = [
            User(
                username="eligibleone",
                email="eligible1@example.com",
                password_hash="test-hash",
                is_active=True,
                email_verified=True,
                marketing_opt_in=True,
            ),
            User(
                username="eligibletwo",
                email="eligible2@example.com",
                password_hash="test-hash",
                is_active=True,
                email_verified=True,
                marketing_opt_in=True,
            ),
            User(
                username="inactiveuser",
                email="inactive@example.com",
                password_hash="test-hash",
                is_active=False,
                email_verified=True,
                marketing_opt_in=True,
            ),
            User(
                username="unverifieduser",
                email="unverified@example.com",
                password_hash="test-hash",
                is_active=True,
                email_verified=False,
                marketing_opt_in=True,
            ),
            User(
                username="optedoutuser",
                email="optedout@example.com",
                password_hash="test-hash",
                is_active=True,
                email_verified=True,
                marketing_opt_in=False,
            ),
        ]
        db.session.add_all(users)
        db.session.commit()

    attempted = []

    def fake_deliver(recipient, subject, body):
        attempted.append(recipient)
        if recipient == "eligible2@example.com":
            raise EmailDeliveryError("Simulated delivery failure.")
        return True

    monkeypatch.setattr(
        "app.services.email_service._deliver_email", fake_deliver
    )
    login_as(client, accounts["admin"])

    response = client.post(
        "/admin/marketing",
        data={
            "subject": "Spring sale",
            "message": "A promotional campaign for our customers.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Sent: 1; failed: 1." in response.data
    assert set(attempted) == {
        "eligible1@example.com",
        "eligible2@example.com",
    }


def test_invalid_campaign_is_not_sent(
    client, accounts, monkeypatch
):
    login_as(client, accounts["admin"])

    def should_not_send(*args, **kwargs):
        pytest.fail("Invalid campaign should not be sent.")

    monkeypatch.setattr(
        "app.routes.admin_products.send_marketing_email",
        should_not_send,
    )

    response = client.post(
        "/admin/marketing",
        data={"subject": "x", "message": "short"},
    )

    assert response.status_code == 200
    assert b"Subject must contain 3" in response.data
    assert b"Message must contain 10" in response.data