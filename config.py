import os
from dotenv import load_dotenv

load_dotenv()

def _env_flag(name, default="false"):
    """Read an environment variable as a boolean."""
    return os.getenv(name, default).lower() in {"1", "true", "yes"}

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///shop.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Stripe payments
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "eur").lower()

    # SMTP email delivery
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _env_flag("MAIL_USE_TLS", "true")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # Email verification
    EMAIL_VERIFICATION_TOKEN_MAX_AGE = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_MAX_AGE", "3600")
    )
    REQUIRE_EMAIL_VERIFICATION = _env_flag("REQUIRE_EMAIL_VERIFICATION", "true")