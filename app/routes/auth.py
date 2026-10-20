from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.forms import (
    LoginForm, LogoutForm, RegistrationForm,
    ResendVerificationForm, MarketingPreferencesForm,
)
from app.services.auth_service import (
    AuthenticationError, RegistrationError, authenticate_user,
    register_user, verify_user_email,
)
from app.services.email_service import (
    EmailDeliveryError, generate_verification_token,
    load_verification_token, send_verification_email,
    request_verification_email,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def home():
    return render_template("home.html", logout_form=LogoutForm())


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = register_user(
                form.username.data, form.email.data, form.password.data,
                marketing_opt_in=form.marketing_opt_in.data,
            )
            token = generate_verification_token(user)
            link = url_for("auth.verify_email", token=token, _external=True)
            send_verification_email(user, link)
            flash(
                "Your account was created successfully. "
                "Please check your email for a verification link before logging in.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except RegistrationError as error:
            flash(str(error), "error")
        except EmailDeliveryError:
            current_app.logger.exception("Verification email delivery failed.")
            try:
                user.verification_email_sent_at = None
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception(
                    "Could not reset registration email cooldown."
                )

            flash(
                "Your account was created, but the verification email "
                "could not be sent. Please try again later.",
                "error",
            )
            return redirect(url_for("auth.login"))
        except Exception:
            current_app.logger.exception("Unexpected registration error.")
            flash("An unexpected error occurred. Please try again.", "error")
    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    data = load_verification_token(token)
    if not data:
        flash("This verification link is invalid or expired. Request a new link.", "error")
        return redirect(url_for("auth.login"))

    try:
        if not verify_user_email(data["user_id"], data["email"]):
            flash("This verification link is invalid.", "error")
        else:
            flash("Email verified successfully. You can now log in.", "success")
    except RegistrationError as error:
        flash(str(error), "error")
    except Exception:
        current_app.logger.exception("Unexpected email-verification error.")
        flash("Email verification failed. Please try again.", "error")
    return redirect(url_for("auth.login"))

@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    form = ResendVerificationForm()

    if form.validate_on_submit():
        try:
            request_verification_email(form.email.data)
        except EmailDeliveryError:
            current_app.logger.exception("Verification resend failed.")
        except Exception:
            current_app.logger.exception("Unexpected verification resend error.")

        # Always show the same message to prevent account enumeration.
        flash(
            "If this address belongs to an unverified account, "
            "a verification email will be sent when available. "
            "Check your inbox.",
            "success",
        )
        return redirect(url_for("auth.resend_verification"))

    return render_template("auth/resend_verification.html", form=form)


@auth_bp.route("/email-preferences", methods=["GET", "POST"])
@login_required
def email_preferences():
    form = MarketingPreferencesForm()

    if form.is_submitted() and form.validate_on_submit():
        try:
            current_user.marketing_opt_in = bool(form.marketing_opt_in.data)
            db.session.commit()
            flash("Your email preferences have been saved.", "success")
            return redirect(url_for("auth.email_preferences"))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Failed to save email preferences.")
            flash("Your preferences could not be saved. Please try again.", "error")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Unexpected preferences error.")
            flash("An unexpected error occurred. Please try again.", "error")
    else:
        form.marketing_opt_in.data = bool(current_user.marketing_opt_in)

    return render_template("auth/email_preferences.html", form=form)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = authenticate_user(form.identity.data, form.password.data)
            login_user(user)
            flash("You have logged in successfully.", "success")
            return redirect(url_for("auth.home"))
        except AuthenticationError as error:
            flash(str(error), "error")
        except Exception:
            current_app.logger.exception("Unexpected login error.")
            flash("An unexpected error occurred. Please try again.", "error")
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if not LogoutForm().validate_on_submit():
        flash("Your logout request could not be verified. Please try again.", "error")
        return redirect(url_for("auth.home"))

    logout_user()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("auth.home"))