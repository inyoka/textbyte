"""Tests for the main blueprint (index and dashboard routes)."""


def _login_as(client, user):
    """Inject a user_id into the session so subsequent requests are authenticated."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_name"] = user.display_name


class TestIndex:
    def test_index_unauthenticated(self, client):
        """Landing page should be visible without authentication."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"TextByte" in response.data

    def test_index_redirects_when_logged_in(self, client, student_user):
        """Signed-in users should be redirected to their dashboard."""
        _login_as(client, student_user)
        response = client.get("/")
        assert response.status_code == 302
        assert "/dashboard" in response.headers["Location"]


class TestDashboard:
    def test_dashboard_requires_login(self, client):
        """Dashboard must redirect to login if not authenticated."""
        response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_teacher_dashboard(self, client, teacher_user):
        _login_as(client, teacher_user)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Teacher Dashboard" in response.data

    def test_student_dashboard(self, client, student_user):
        _login_as(client, student_user)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Student Dashboard" in response.data
