"""Main blueprint – index and dashboard."""

from flask import Blueprint, redirect, render_template, session, url_for

from app.extensions import db
from app.models.models import Assessment, Submission, User

main_bp = Blueprint("main", __name__)


def _current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.session.get(User, user_id)


@main_bp.route("/")
def index():
    """Landing page."""
    user = _current_user()
    if user:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    """Personalised dashboard for the signed-in user."""
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login"))

    if user.is_teacher:
        assessments = (
            Assessment.query.filter_by(creator_id=user.id)
            .order_by(Assessment.created_at.desc())
            .all()
        )
        return render_template(
            "dashboard_teacher.html", user=user, assessments=assessments
        )

    # Student dashboard
    published = (
        Assessment.query.filter_by(published=True)
        .order_by(Assessment.created_at.desc())
        .all()
    )
    submitted_ids = {
        s.assessment_id
        for s in Submission.query.filter_by(student_id=user.id).all()
    }
    return render_template(
        "dashboard_student.html",
        user=user,
        assessments=published,
        submitted_ids=submitted_ids,
    )


@main_bp.route("/login")
def login():
    """Convenience redirect to the auth login route."""
    return redirect(url_for("auth.login"))
