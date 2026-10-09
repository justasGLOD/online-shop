
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app.forms import LoginForm, LogoutForm, RegistrationForm
from app.services.auth_service import (
    AuthenticationError,
    RegistrationError,
    authenticate_user,
    register_user,
)


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def home():
    """Display the home page."""
    return render_template(
        "home.html",
        logout_form=LogoutForm(),
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a new account."""
    form = RegistrationForm()

    if form.validate_on_submit():
        try:
            register_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
            )

            flash(
                "Your account was created successfully. Please log in.",
                "success",
            )
            return redirect(url_for("auth.login"))

        except RegistrationError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Unexpected registration error."
            )
            flash(
                "An unexpected error occurred. Please try again.",
                "error",
            )

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            user = authenticate_user(
                identity=form.identity.data,
                password=form.password.data,
            )

            login_user(user)

            flash("You have logged in successfully.", "success")
            return redirect(url_for("auth.home"))

        except AuthenticationError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Unexpected login error."
            )
            flash(
                "An unexpected error occurred. Please try again.",
                "error",
            )

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """End the authenticated session."""
    form = LogoutForm()

    if not form.validate_on_submit():
        flash(
            "Your logout request could not be verified. Please try again.",
            "error",
        )
        return redirect(url_for("auth.home"))

    logout_user()

    flash("You have logged out successfully.", "success")
    return redirect(url_for("auth.home"))
