from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)

from app.forms import RegistrationForm
from app.services.auth_service import (
    RegistrationError,
    register_user,
)


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Display and process the registration form."""
    form = RegistrationForm()

    if form.validate_on_submit():
        try:
            register_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
            )

            flash(
                "Your account was created successfully. "
                "You can now log in.",
                "success",
            )

            return redirect(url_for("auth.register"))

        except RegistrationError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Unexpected error during user registration."
            )

            flash(
                "An unexpected error occurred. Please try again.",
                "error",
            )

    return render_template("auth/register.html", form=form)