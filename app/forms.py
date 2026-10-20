
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
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
                    "Username may contain letters, numbers, underscores, "
                    "dots and hyphens only."
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
                    "Password must contain a lowercase letter, an uppercase "
                    "letter, a number and a special character."
                ),
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="The passwords do not match."),
        ],
    )
    marketing_opt_in = BooleanField(
        "I agree to receive promotional emails (optional)"
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    identity = StringField(
        "Username or email",
        validators=[
            DataRequired(message="Enter your username or email address."),
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
        validators=[Optional(), Length(max=5000)],
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
    discount_percent = DecimalField(
        "Discount (%)",
        places=2,
        default=Decimal("0.00"),
        validators=[
            NumberRange(
                min=0,
                max=100,
                message="Discount must be between 0 and 100%%.",
            ),
        ],
    )
    stock = IntegerField(
        "Initial stock quantity",
        validators=[
            DataRequired(message="Stock quantity is required."),
            NumberRange(min=0, message="Stock cannot be negative."),
        ],
    )
    submit = SubmitField("Add product")


class ProductEditForm(FlaskForm):
    name = StringField(
        "Product name",
        validators=[
            DataRequired(message="Product name is required."),
            Length(min=2, max=150),
        ],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=5000)],
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
    discount_percent = DecimalField(
        "Discount (%)",
        places=2,
        default=Decimal("0.00"),
        validators=[
            NumberRange(
                min=0,
                max=100,
                message="Discount must be between 0 and 100%%.",
            ),
        ],
    )
    submit = SubmitField("Save changes")


class RestockForm(FlaskForm):
    quantity = IntegerField(
        "Quantity to add",
        validators=[
            DataRequired(message="Enter a quantity."),
            NumberRange(min=1, message="You must add at least one item."),
        ],
    )
    submit = SubmitField("Add stock")


class ProductActionForm(FlaskForm):
    submit = SubmitField("Remove from sale")


class UserActionForm(FlaskForm):
    submit = SubmitField("Deactivate account")


class CartQuantityForm(FlaskForm):
    quantity = IntegerField(
        "Quantity",
        validators=[
            DataRequired(message="Enter a quantity."),
            NumberRange(min=1, message="Quantity must be at least 1."),
        ],
    )
    submit = SubmitField("Add to cart")


class CartActionForm(FlaskForm):
    submit = SubmitField("Remove")


class CheckoutForm(FlaskForm):
    submit = SubmitField("Confirm purchase")


class BalanceTopUpForm(FlaskForm):
    amount = StringField(
        "Top-up amount (€)",
        validators=[
            DataRequired(message="Please enter an amount."),
        ],
    )
    submit = SubmitField("Top up balance")


class ReviewForm(FlaskForm):
    rating = IntegerField(
        "Rating (1–5)",
        validators=[
            DataRequired(message="Please select a rating."),
            NumberRange(
                min=1,
                max=5,
                message="Rating must be between 1 and 5.",
            ),
        ],
    )
    comment = TextAreaField(
        "Your review",
        validators=[
            DataRequired(message="Please write a review."),
            Length(
                min=3,
                max=2000,
                message=(
                    "Your review must contain between 3 and 2000 characters."
                ),
            ),
        ],
    )
    submit = SubmitField("Submit review")


class ResendVerificationForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
    )
    submit = SubmitField("Resend verification email")


class MarketingPreferencesForm(FlaskForm):
    marketing_opt_in = BooleanField(
        "I agree to receive promotional emails (optional)"
    )
    submit = SubmitField("Save preferences")


class MarketingCampaignForm(FlaskForm):
    subject = StringField(
        "Email subject",
        validators=[
            DataRequired(message="Please enter an email subject."),
            Length(
                min=3,
                max=200,
                message="Subject must contain 3–200 characters.",
            ),
        ],
    )
    message = TextAreaField(
        "Email message",
        validators=[
            DataRequired(message="Please enter an email message."),
            Length(
                min=10,
                max=5000,
                message="Message must contain 10–5000 characters.",
            ),
        ],
    )
    submit = SubmitField("Send marketing email")
