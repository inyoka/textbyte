"""Tests for assessment import, publish, take and results."""

import io

import pytest

from app.extensions import db
from app.models.models import Assessment, Question, Submission


VALID_YAML = b"""
title: Sample Test

questions:
  - type: single_choice
    question: What colour is the sky?
    options:
      - Red
      - Blue
      - Green
    answer: Blue

  - type: short_answer
    question: What is 2 + 2?
    answer: "4"
"""

INVALID_YAML_MISSING_TITLE = b"""
questions:
  - type: single_choice
    question: Placeholder?
    options: [A, B]
    answer: A
"""

INVALID_YAML_BAD_TYPE = b"""
title: Bad

questions:
  - type: essay
    question: Write an essay.
    answer: ""
"""


def _login_as(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_name"] = user.display_name


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class TestImport:
    def test_import_requires_teacher(self, client, student_user):
        _login_as(client, student_user)
        response = client.get("/assessments/import")
        assert response.status_code == 403

    def test_import_requires_login(self, client):
        response = client.get("/assessments/import")
        assert response.status_code == 302

    def test_import_get_renders_form(self, client, teacher_user):
        _login_as(client, teacher_user)
        response = client.get("/assessments/import")
        assert response.status_code == 200
        assert b"Import Assessment" in response.data

    def test_import_valid_yaml(self, client, app, teacher_user):
        _login_as(client, teacher_user)
        data = {
            "yaml_file": (io.BytesIO(VALID_YAML), "test.yaml"),
        }
        response = client.post(
            "/assessments/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Sample Test" in response.data

        with app.app_context():
            assessment = Assessment.query.filter_by(title="Sample Test").first()
            assert assessment is not None
            assert len(assessment.questions) == 2

    def test_import_missing_title_shows_error(self, client, teacher_user):
        _login_as(client, teacher_user)
        data = {
            "yaml_file": (io.BytesIO(INVALID_YAML_MISSING_TITLE), "bad.yaml"),
        }
        response = client.post(
            "/assessments/import",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        assert b"title" in response.data.lower()

    def test_import_unsupported_type_shows_error(self, client, teacher_user):
        _login_as(client, teacher_user)
        data = {
            "yaml_file": (io.BytesIO(INVALID_YAML_BAD_TYPE), "bad.yaml"),
        }
        response = client.post(
            "/assessments/import",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        assert b"essay" in response.data


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

class TestPublish:
    @pytest.fixture()
    def assessment(self, app, teacher_user):
        with app.app_context():
            a = Assessment(title="Publish Test", creator_id=teacher_user.id)
            db.session.add(a)
            q = Question(
                assessment=a,
                type="single_choice",
                text="Pick one",
                order=0,
            )
            q.options = ["A", "B"]
            q.answer = "A"
            db.session.add(q)
            db.session.commit()
            return {"id": a.id, "published": a.published}

    def test_publish_toggles_state(self, client, app, teacher_user, assessment):
        _login_as(client, teacher_user)
        assert not assessment["published"]
        client.post(f"/assessments/{assessment['id']}/publish")
        with app.app_context():
            updated = db.session.get(Assessment, assessment["id"])
            assert updated.published is True

    def test_unpublish_toggles_state(self, client, app, teacher_user, assessment):
        _login_as(client, teacher_user)
        # Publish first
        client.post(f"/assessments/{assessment['id']}/publish")
        # Unpublish
        client.post(f"/assessments/{assessment['id']}/publish")
        with app.app_context():
            updated = db.session.get(Assessment, assessment["id"])
            assert updated.published is False


# ---------------------------------------------------------------------------
# Take / Submit
# ---------------------------------------------------------------------------

class TestTake:
    @pytest.fixture()
    def published_assessment(self, app, teacher_user):
        with app.app_context():
            a = Assessment(
                title="Take Test", creator_id=teacher_user.id, published=True
            )
            db.session.add(a)
            q = Question(
                assessment=a,
                type="single_choice",
                text="Best language?",
                order=0,
            )
            q.options = ["Python", "Java"]
            q.answer = "Python"
            db.session.add(q)
            db.session.commit()
            # Return plain data instead of ORM objects to avoid DetachedInstanceError
            return {"id": a.id, "question_id": q.id}

    def test_student_can_view_assessment(self, client, student_user, published_assessment):
        _login_as(client, student_user)
        response = client.get(f"/assessments/{published_assessment['id']}/take")
        assert response.status_code == 200
        assert b"Take Test" in response.data

    def test_teacher_cannot_take(self, client, teacher_user, published_assessment):
        _login_as(client, teacher_user)
        response = client.get(f"/assessments/{published_assessment['id']}/take")
        assert response.status_code == 403

    def test_submit_creates_submission(self, client, app, student_user, published_assessment):
        _login_as(client, student_user)
        q_id = published_assessment["question_id"]
        response = client.post(
            f"/assessments/{published_assessment['id']}/take",
            data={f"q_{q_id}": "Python"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Submission Received" in response.data

        with app.app_context():
            sub = Submission.query.filter_by(
                student_id=student_user.id,
                assessment_id=published_assessment["id"],
            ).first()
            assert sub is not None
            correct, total = sub.score
            assert total == 1
            assert correct == 1

    def test_duplicate_submission_redirects(self, client, student_user, published_assessment):
        _login_as(client, student_user)
        q_id = published_assessment["question_id"]
        form_data = {f"q_{q_id}": "Python"}
        client.post(
            f"/assessments/{published_assessment['id']}/take",
            data=form_data,
        )
        response = client.post(
            f"/assessments/{published_assessment['id']}/take",
            data=form_data,
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"already submitted" in response.data
