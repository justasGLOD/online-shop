from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms import DecimalField, IntegerField, TextAreaField
from wtforms.validators import NumberRange, Optional
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

class LoginForm(FlaskForm):
    identity = StringField(
        "Username or email",
        validators=[
            DataRequired(
                message="Enter your username or email address."
            ),
            Length(max=255),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(max=128),
        ],
    )

    submit = SubmitField("Log in")

class LogoutForm(FlaskForm):
    submit = SubmitField("Log out")

class ProductForm(FlaskForm):
    name = StringField(
        "Product name",
        validators=[
            DataRequired(message="Product name is required."),
            Length(min=2, max=150),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=5000),
        ],
    )

    price = DecimalField(
        "Price (€)",
        places=2,
        validators=[
            DataRequired(message="Price is required."),
            NumberRange(
                min=0.01,
                message="Price must be greater than zero.",
            ),
        ],
    )

    stock = IntegerField(
        "Initial stock quantity",
        validators=[
            DataRequired(message="Stock quantity is required."),
            NumberRange(
                min=0,
                message="Stock cannot be negative.",
            ),
        ],
    )

    submit = SubmitField("Add product")


class RestockForm(FlaskForm):
    quantity = IntegerField(
        "Quantity to add",
        validators=[
            DataRequired(message="Enter a quantity."),
            NumberRange(
                min=1,
                message="You must add at least one item.",
            ),
        ],
    )

    submit = SubmitField("Add stock")


class ProductActionForm(FlaskForm):
    submit = SubmitField("Remove from sale")
