# Online Shop

A Flask-based online shop built with Python, Flask, SQLAlchemy, and SQLite. The application supports customer accounts, a product catalogue, shopping carts, checkout, balance management, orders, product reviews, and administrator tools.

## Features

### Customer accounts
- User registration and login with hashed passwords.
- Password validation and escalating login lockouts after repeated failures.
- Email verification using time-limited verification links.
- Verification email resend with a cooldown.
- Optional promotional-email consent and customer email preferences.

### Shopping
- Browse products and sort the catalogue using supported sorting options.
- View product information, prices, discounts, ratings, and stock availability.
- Add products to a persistent shopping cart and update quantities.
- Complete purchases with checkout and stock validation.
- View order history and balance transaction history.
- Review products after purchasing them.

### Balance and payments
- View the current customer balance.
- Top up account balance through Stripe Checkout in test mode.
- Record balance transactions.
- Process Stripe webhook events and prevent duplicate balance credits.
- Keep payment records and payment statuses in the database.

### Administration
- View the administrator dashboard and store statistics.
- Create and edit products.
- Restock products and remove products from sale without deleting their history.
- View and deactivate customer accounts.
- Manage promotional email campaigns.
- Send marketing emails only to active customers whose email addresses are verified and who have opted in.

## Technology stack

- Python
- Flask
- Flask-SQLAlchemy and SQLAlchemy
- Flask-Login
- Flask-WTF and WTForms
- Flask-Migrate and Alembic
- SQLite
- Stripe Checkout and Stripe CLI for payment testing
- SMTP for email delivery
- pytest for automated tests

## Project structure

```text
online_shop/
├── app/
│   ├── crud/            # Database access operations
│   ├── models/          # SQLAlchemy models
│   ├── routes/          # Flask routes and blueprints
│   ├── services/        # Business logic and integrations
│   ├── templates/       # Jinja2 HTML templates
│   ├── static/          # CSS and other static files
│   ├── extensions.py    # Flask extension instances
│   └── forms.py         # WTForms form definitions
├── migrations/          # Database migration history
├── tests/               # Automated tests
├── config.py            # Application configuration
├── requirements.txt     # Python dependencies
├── run.py               # Application entry point
└── README.md
```

## Requirements

- Python installed and available in PowerShell.
- Git.
- A working internet connection for installing dependencies and using external services.
- A Stripe test-mode account and the Stripe CLI to test payment webhooks.
- SMTP credentials for real email delivery. Local development may use the configured verification-link logging fallback when SMTP is not configured.

## Installation on Windows

Open PowerShell in the project directory.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you already use an existing virtual environment for this project, activate that environment instead.

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root. Use the following template and replace the example values with your own local configuration.

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///shop.db

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_CURRENCY=eur

MAIL_SERVER=
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

EMAIL_VERIFICATION_TOKEN_MAX_AGE=3600
REQUIRE_EMAIL_VERIFICATION=true
```

Configuration details:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Protects Flask sessions and form security. |
| `DATABASE_URL` | Database connection URL; SQLite is used by default. |
| `STRIPE_SECRET_KEY` | Stripe test-mode API secret key. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret used to verify local Stripe webhook events. |
| `STRIPE_CURRENCY` | Currency used for Stripe payments, set to `eur` by default. |
| `MAIL_SERVER` | SMTP server hostname. |
| `MAIL_PORT` | SMTP server port, usually `587` for STARTTLS. |
| `MAIL_USE_TLS` | Controls SMTP TLS usage. |
| `MAIL_USERNAME` | SMTP username. |
| `MAIL_PASSWORD` | SMTP password or provider-specific app password. |
| `MAIL_DEFAULT_SENDER` | Sender address for outgoing email; defaults to the configured mail username when not provided. |
| `EMAIL_VERIFICATION_TOKEN_MAX_AGE` | Verification-token lifetime in seconds; defaults to `3600`. |
| `REQUIRE_EMAIL_VERIFICATION` | Controls whether email verification is required before login; defaults to enabled. |

Keep `.env` private. **Never commit API keys, webhook secrets, SMTP passwords, or production credentials to GitHub.** Use Stripe test credentials when testing the application.

## Database setup

Apply the existing database migrations:

```powershell
flask --app run.py db upgrade
```

To inspect the current migration revision:

```powershell
flask --app run.py db current
```

When developing a database schema change, create a migration, inspect the generated migration file, and then apply it:

```powershell
flask --app run.py db migrate -m "Describe the schema change"
flask --app run.py db upgrade
```

Do not create a new migration just to start the application. Use the migrations already included in the repository.

## Run the application

Start the development server:

```powershell
flask --app run.py run --debug
```

Open the local address shown in the terminal, normally:

`http://127.0.0.1:5000/`

The debug server is intended for development, not production deployment.

## Stripe test payments

1. Configure `STRIPE_SECRET_KEY` using your Stripe test-mode secret key.
2. Install the Stripe CLI and authenticate it:

   ```powershell
   stripe login
   ```

3. Start webhook forwarding in a separate terminal:

   ```powershell
   stripe listen --forward-to localhost:5000/payments/webhook --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired
   ```

4. Copy the `whsec_...` signing secret printed by the Stripe CLI into `STRIPE_WEBHOOK_SECRET` in your local `.env` file.
5. Restart the Flask application after changing configuration.
6. Use Stripe test-mode payment details to complete a test checkout and verify that the webhook updates the payment and balance.

Keep the Stripe CLI listener running while testing local webhook events. A test checkout redirect alone does not prove that the webhook was successfully processed.

## Email verification and marketing

Configure the SMTP variables in `.env` when real email delivery is required.

During local debugging, the application can log a verification URL in the terminal if SMTP is not configured and the development fallback is enabled. Use that URL to test account verification.

Customers can manage their promotional-email preferences. The administrator marketing campaign feature selects only active users whose email addresses are verified and whose marketing preference is enabled.

Do not use the local email fallback as a replacement for proper email delivery configuration in production.

## Run the automated tests

Install the dependencies, activate the virtual environment, and run:

```powershell
python -m pytest -q
```

To run a particular test module:

```powershell
python -m pytest tests/test_admin_marketing.py -q
```

The suite covers application features including authentication, products, administration, shopping carts, checkout, balance management, Stripe payment processing, reviews, orders, and email verification.

At the latest verified checkpoint before the documentation task, **139 tests passed**. Run the suite again after making changes and use the actual result when reporting test status.

## Development workflow

The project uses Jira to organize tasks and GitHub pull requests to review changes.

1. Start from the `Development` branch.
2. Pull the latest changes from `origin/Development`.
3. Create a dedicated task branch.
4. Implement the task and run relevant tests.
5. Run `git diff --check`.
6. Commit and push the task branch.
7. Open a pull request targeting `Development`.
8. Merge only after checking the implementation and tests.

Keep `main` separate from ongoing development and do not commit local secrets or generated virtual-environment files.

## Security notes

- Passwords are stored as hashes rather than plaintext.
- Login lockouts help mitigate repeated password-guessing attempts.
- Email-verification tokens have a configured lifetime.
- Stripe webhook signatures are verified before processing events.
- Payment and balance updates should be validated and handled transactionally.
- Administrative routes require administrator authorization.
- Marketing messages are restricted to eligible customers who have explicitly opted in.
- Never publish `.env`, private API credentials, or SMTP passwords.

## Project status

The application has implemented the customer shopping flow, account and balance management, administrative product tools, product reviews, Stripe test payments, email verification, and administrator marketing campaigns.

The final acceptance audit should confirm each assignment requirement against the running application and test suite before submission.
