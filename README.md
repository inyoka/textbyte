# textbyte
An online testing platform for teachers needing end of unit testing.  Auth from Microsoft Accounts.

## Overview

TextByte is a server-rendered Flask web application that allows:

* **Teachers** to write assessments as YAML files, import them, publish them, and export results to CSV.
* **Students** to sign in with their Microsoft school account, complete published assessments, and see their score immediately.

---

## Quick Start

### 1. Clone and install dependencies

```bash
git clone https://github.com/inyoka/textbyte
cd textbyte
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your Microsoft Entra ID credentials (see below)
```

### 3. Run the development server

```bash
python run.py
```

Open <http://localhost:5000> in your browser.

---

## Microsoft Entra ID App Registration

Authentication is handled by Microsoft's official [MSAL](https://github.com/AzureAD/microsoft-authentication-library-for-python) library.  You must create an **App Registration** in the Azure Portal before users can sign in.

### Steps

1. Go to the [Azure Portal](https://portal.azure.com/) and sign in with an administrator account.
2. Navigate to **Microsoft Entra ID → App registrations → New registration**.
3. Fill in the form:
   - **Name**: TextByte (or any name you prefer)
   - **Supported account types**: *Accounts in any organizational directory (Any Microsoft Entra ID tenant – Multitenant)* — use *Single tenant* if you only want one school's accounts.
   - **Redirect URI**: Web → `http://localhost:5000/auth/callback` (add your production URL later)
4. Click **Register**.
5. From the **Overview** page, copy:
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`
6. Go to **Certificates & secrets → New client secret**. Copy the **Value** (not the ID) → `AZURE_CLIENT_SECRET`.
7. Go to **API permissions** and confirm `User.Read` (Microsoft Graph) is listed. Grant admin consent if required.
8. Paste the values into your `.env` file.

> **Important**: Never commit your `.env` file or client secret to version control.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret key | `change-me-in-production` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///textbyte.db` |
| `AZURE_CLIENT_ID` | App Registration client ID | *(required)* |
| `AZURE_CLIENT_SECRET` | App Registration client secret | *(required)* |
| `AZURE_TENANT_ID` | Tenant ID or `common` | `common` |
| `AZURE_REDIRECT_URI` | OAuth callback URL | `http://localhost:5000/auth/callback` |

---

## Assessment YAML Format

Teachers write assessments as YAML files and import them via the web interface.

```yaml
title: Network Test

questions:
  - type: single_choice
    question: Which protocol securely transfers web pages?
    options:
      - HTTP
      - HTTPS
      - FTP
      - SMTP
    answer: HTTPS

  - type: multi_choice
    question: Which are transport-layer protocols?
    options:
      - TCP
      - UDP
      - HTTP
      - IP
    answer:
      - TCP
      - UDP

  - type: short_answer
    question: What does DNS stand for?
    answer: Domain Name System
```

### Supported question types

| Type | Description | Auto-graded? |
|---|---|---|
| `single_choice` | Radio buttons, one correct answer | ✅ Yes |
| `multi_choice` | Checkboxes, one or more correct answers | ✅ Yes |
| `short_answer` | Free-text input | ❌ Manual |

---

## User Roles

After a user signs in for the first time a local account is created with the **student** role.  To promote a user to teacher, update the `role` column directly in the database:

```python
from app import create_app
from app.extensions import db
from app.models.models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email="teacher@school.example").first()
    user.role = "teacher"
    db.session.commit()
```

---

## Project Structure

```
textbyte/
├── app/
│   ├── __init__.py          # Application factory
│   ├── extensions.py        # Shared SQLAlchemy instance
│   ├── main.py              # Index and dashboard routes
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py        # Microsoft MSAL authentication
│   ├── assessments/
│   │   ├── __init__.py
│   │   └── routes.py        # Import, publish, take, results
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py        # SQLAlchemy models
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── dashboard_teacher.html
│   │   ├── dashboard_student.html
│   │   ├── auth/
│   │   │   └── error.html
│   │   └── assessments/
│   │       ├── import.html
│   │       ├── preview.html
│   │       ├── take.html
│   │       ├── confirmation.html
│   │       ├── results.html
│   │       ├── teacher_list.html
│   │       └── student_list.html
│   └── static/
├── tests/
│   ├── conftest.py
│   ├── test_main.py
│   └── test_assessments.py
├── config.py
├── requirements.txt
├── run.py
└── .env.example
```

---

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Technology Stack

* [Python 3.10+](https://www.python.org/)
* [Flask 3](https://flask.palletsprojects.com/)
* [SQLAlchemy 2 + Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
* [SQLite](https://www.sqlite.org/) (default; swap `DATABASE_URL` for PostgreSQL in production)
* [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python) — Microsoft authentication
* [Bootstrap 5](https://getbootstrap.com/) — UI
* [PyYAML](https://pyyaml.org/) — assessment file parsing
