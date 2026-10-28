# Online Shop

A Flask-based online shopping application built with Python, Flask, SQLAlchemy, and SQLite. It includes customer accounts, product browsing, persistent shopping carts, checkout, account balances, product reviews, administrator tools, loyalty discounts, Stripe test payments, and email verification.

## Features

### Customer accounts and security

- User registration, login, and logout using Flask-Login.
- Password hashing and password-complexity validation.
- Escalating, time-based login lockouts after repeated failed attempts.
- Time-limited email verification links.
- Verification email resend with a cooldown.
- Customer email preferences and promotional-email consent.

### Shopping and checkout

- Browse products and sort the catalogue using supported sorting options.
- View product information, prices, discounts, ratings, and stock availability.
- Add products to a persistent shopping cart and update quantities.
- Purchase items through checkout with stock, availability, and balance validation.
- Save orders, order items, and purchase-time prices in the database.
- View order history and balance transaction history.
- Review purchased products using a rating from 1 to 5 stars.

### Loyalty discounts

- Award a 5% loyalty discount when a customer has at least four completed purchases within the previous 90 days.
- Award a 5% loyalty discount when total spending across completed orders exceeds €500, even if the customer does not meet the purchase-count threshold.
- Award a 10% loyalty discount when a customer has at least ten completed purchases within the previous 90 days.
- Exclude pending, failed, and cancelled orders from eligibility calculations.
- Apply the loyalty discount during checkout, in addition to any product discount.

### Balance and payments

- View the current customer balance.
- Top up an account using Stripe Checkout in test mode.
- Store payment records and payment statuses in the database.
- Verify Stripe webhook signatures before processing payment events.
- Credit successful top-ups through webhook processing and prevent duplicate balance credits.
- Record balance transactions and handle unsuccessful or pending payments.

### Administration

- View the administrator dashboard and store statistics.
- Create and edit products.
- Configure product discounts, restock products, and remove products from sale without deleting their product history.
- View, deactivate, and delete customer accounts.
- Manage promotional email campaigns.
- Send marketing emails only to active, verified customers who have opted in.
- Review daily sales and order counts.
- Review monthly revenue, product costs, and gross profit.
- Identify the highest-gross-profit month when the required cost data is complete.
- View the best-rated products.
- Avoid inventing profit figures when historical product costs are unknown.

## Technology stack

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy and SQLAlchemy
- Flask-WTF and WTForms
- Flask-Migrate and Alembic
- SQLite
- Stripe Checkout and Stripe CLI
- SMTP email delivery
- pytest
- GitHub Actions
- Jira for task management

## Project structure

```text
online_shop/
├── app/
│   ├── crud/             # Database access and CRUD operations
│   ├── models/           # SQLAlchemy models
│   ├── routes/           # Flask routes and blueprints
│   ├── services/         # Business logic and integrations
│   ├── templates/        # Jinja2 HTML templates
│   ├── static/           # CSS and other static assets
│   ├── extensions.py     # Flask extension instances
│   └── forms.py          # WTForms definitions
├── migrations/           # Alembic migration history
├── tests/                # Automated tests
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions test workflow
├── config.py             # Application configuration
├── requirements.txt      # Pinned Python dependencies
├── run.py                # Application entry point
└── README.md
```

## Requirements

- Python installed and available in PowerShell.
- Git.
- Internet access for installing dependencies and using external services.
- A Stripe test-mode account and Stripe CLI for payment testing.
- SMTP credentials for real email delivery.

## Installation on Windows

Open PowerShell in the project directory.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you already use another virtual environment for this project, activate that environment instead.

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root. Use the template below, replacing the example values with your own local configuration.

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

Never commit real credentials or the `.env` file to GitHub.

### Environment variable reference

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Protects Flask sessions and signed tokens. |
| `DATABASE_URL` | Database connection string. SQLite is used by default. |
| `STRIPE_SECRET_KEY` | Stripe API secret key. Use a test-mode key for development. |
| `STRIPE_WEBHOOK_SECRET` | Verifies signed Stripe webhook events. |
| `STRIPE_CURRENCY` | Currency used for Stripe payments; defaults to `eur`. |
| `MAIL_SERVER` | SMTP server hostname. |
| `MAIL_PORT` | SMTP port, normally `587` for STARTTLS. |
| `MAIL_USE_TLS` | Enables SMTP TLS. |
| `MAIL_USERNAME` | SMTP username. |
| `MAIL_PASSWORD` | SMTP password or provider-specific app password. |
| `MAIL_DEFAULT_SENDER` | Outgoing email sender address. Defaults to the mail username. |
| `EMAIL_VERIFICATION_TOKEN_MAX_AGE` | Verification token lifetime in seconds. Defaults to `3600`. |
| `REQUIRE_EMAIL_VERIFICATION` | Requires email verification before login when enabled. |

For Gmail, configure `MAIL_SERVER=smtp.gmail.com`, port `587`, TLS enabled, and use a Gmail App Password when required by your account's security settings.

## Database setup

Apply the migrations included in the repository:

```powershell
flask --app run.py db upgrade
```

Check the current migration revision:

```powershell
flask --app run.py db current
```

When changing the database schema during development, generate and inspect a migration before applying it:

```powershell
flask --app run.py db migrate -m "Describe the schema change"
flask --app run.py db upgrade
```

Do not generate a migration just to start the application. Apply the migrations already included in the repository when setting up an existing version of the project.

## Run the application

Start the application from the project root:

```powershell
python run.py
```

Open the local address shown in the terminal. The default development address is normally:

`http://127.0.0.1:5000/`

The Flask development server is intended for local development, not production deployment.

## Stripe test payments

1. Configure `STRIPE_SECRET_KEY` with a Stripe test-mode secret key.
2. Install the Stripe CLI and authenticate:

   ```powershell
   stripe login
   ```

3. Start webhook forwarding in a separate terminal:

   ```powershell
   stripe listen --forward-to http://localhost:5000/payments/webhook --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired
   ```

4. Use the webhook signing secret printed by the CLI as the local `STRIPE_WEBHOOK_SECRET` value.
5. Restart Flask after changing configuration.
6. Complete a test checkout using Stripe's documented test payment details.
7. Verify that the webhook returns a successful response and that the account balance and transaction history update correctly.

Keep the Stripe CLI listener running during local tests. A redirect to a success page by itself does not prove that the webhook was processed successfully.

Never use live payment credentials for development tests, and never publish API keys or webhook secrets.

## Email verification and marketing

Configure the SMTP variables in `.env` when real email delivery is required.

During local debugging, the application may log a verification URL when SMTP is not configured and the development fallback is enabled. This fallback is useful for testing verification logic but is not a substitute for real email delivery.

Customers can manage promotional-email preferences. The administrator marketing feature selects only active customers whose email addresses are verified and whose marketing preference is enabled.

## Run the automated tests

Activate the virtual environment, install the dependencies, and run:

```powershell
python -m pytest -q
```

To run an individual test module:

```powershell
python -m pytest tests/test_admin_marketing.py -q
```

The test suite covers authentication, registration, products, administrator tools, shopping carts, checkout, loyalty discounts, account balances, Stripe payment processing, reviews, order history, email verification, and marketing campaigns.

**Latest recorded local test result:** 172 tests passed on October 28, 2026, after the KAN-30 loyalty-discount changes were merged into `Development`. Run the suite again after subsequent changes and report the actual result.

## GitHub Actions

The repository includes `.github/workflows/ci.yml`, which runs the automated Python tests using dependencies from `requirements.txt`.

The workflow runs on pushes, pull requests targeting `Development`, and manual workflow dispatches.

Check the **Actions** tab on GitHub to inspect workflow runs and test results.

## Development workflow

The project uses Jira to organize tasks and GitHub pull requests to review and merge changes.

1. Start from `Development`.
2. Pull the latest changes from `origin/Development`.
3. Create a dedicated task branch.
4. Implement the changes and run the relevant tests.
5. Run `git diff --check`.
6. Commit and push the task branch.
7. Open a pull request targeting `Development`.
8. Check the code and automated test results before merging.

Keep `main` as the stable branch, keep `Development` for integrated work, and use task branches for individual Jira tasks.

## Security notes

- Passwords are stored as hashes rather than plaintext.
- Timed login lockouts help mitigate repeated password-guessing attempts.
- Email verification tokens have a configured lifetime.
- Stripe webhook signatures are verified before payment events are processed.
- Payment and balance updates are performed transactionally.
- Administrative routes require administrator authorization.
- Marketing messages are restricted to eligible customers who explicitly opted in.
- Keep `.env`, API credentials, webhook secrets, SMTP passwords, and other private configuration out of Git.
- Use a strong, unique Flask `SECRET_KEY` outside disposable local test environments.
- Do not deploy the Flask development server or development configuration to production without appropriate production setup.

## Project status

The project includes the core customer shopping flow, administrative tools, loyalty discounts, monthly profit reporting, Stripe test payments, email verification, marketing campaigns, database migrations, automated tests, and GitHub Actions CI.

Before final submission, verify the assignment requirements against the running application, confirm the repository's branch and commit history, and run the complete test suite.
