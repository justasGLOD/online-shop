from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
)


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(
                min=3,
                max=80,
                message="Username must contain between 3 and 80 characters.",
            ),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message=(
                    "Username may contain letters, numbers, "
                    "underscores, dots and hyphens only."
                ),
            ),
        ],
    )

    email = StringField(
        "Email address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(
                min=8,
                max=128,
                message="Password must be between 8 and 128 characters.",
            ),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$",
                message=(
                    "Password must contain a lowercase letter, "
                    "an uppercase letter, a number and a special character."
                ),
            ),
        ],
    )

    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo(
                "password",
                message="The passwords do not match.",
            ),
        ],
    )

    submit = SubmitField("Create account")