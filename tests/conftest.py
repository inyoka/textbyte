"""Pytest configuration – creates a test Flask app with an in-memory SQLite database."""

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.models import User


class TestConfig:
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AZURE_CLIENT_ID = "test-client-id"
    AZURE_CLIENT_SECRET = "test-client-secret"
    AZURE_TENANT_ID = "common"
    AZURE_REDIRECT_URI = "http://localhost/auth/callback"
    AZURE_SCOPES = ["User.Read"]
    AZURE_AUTHORITY = "https://login.microsoftonline.com/common"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture()
def app():
    application = create_app(TestConfig())
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def teacher_user(app):
    """Create a teacher user directly in the database."""
    user = User(
        microsoft_id="teacher-oid-001",
        email="teacher@school.example",
        display_name="Test Teacher",
        role="teacher",
    )
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture()
def student_user(app):
    """Create a student user directly in the database."""
    user = User(
        microsoft_id="student-oid-001",
        email="student@school.example",
        display_name="Test Student",
        role="student",
    )
    _db.session.add(user)
    _db.session.commit()
    return user
