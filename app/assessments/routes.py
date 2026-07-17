"""Assessment blueprint – import, publish, take, and results."""

import csv
import io

import yaml
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)

from app.extensions import db
from app.models.models import Answer, Assessment, Question, Submission, User

assessments_bp = Blueprint("assessments", __name__, url_prefix="/assessments")

SUPPORTED_QUESTION_TYPES = {"single_choice", "multi_choice", "short_answer"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_user():
    """Return the logged-in User object, or None."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.session.get(User, user_id)


def _require_login():
    """Redirect to login if no active session."""
    if session.get("user_id") is None:
        flash("Please sign in to continue.", "warning")
        return redirect(url_for("auth.login"))
    return None


def _require_teacher(user):
    """Abort with 403 if the user is not a teacher."""
    if not user or not user.is_teacher:
        abort(403)


def _validate_yaml(data):
    """Validate parsed YAML structure.

    Returns a list of error strings; empty list means valid.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Top-level YAML value must be a mapping."]

    if not data.get("title"):
        errors.append("Missing required field: title.")

    questions = data.get("questions")
    if not questions:
        errors.append("Missing required field: questions (must be a non-empty list).")
        return errors

    if not isinstance(questions, list):
        errors.append("'questions' must be a list.")
        return errors

    for i, q in enumerate(questions, start=1):
        prefix = f"Question {i}"
        if not isinstance(q, dict):
            errors.append(f"{prefix}: must be a mapping.")
            continue

        qtype = q.get("type")
        if not qtype:
            errors.append(f"{prefix}: missing 'type'.")
        elif qtype not in SUPPORTED_QUESTION_TYPES:
            errors.append(
                f"{prefix}: unsupported type {qtype!r}. "
                f"Supported types: {', '.join(sorted(SUPPORTED_QUESTION_TYPES))}."
            )

        if not q.get("question"):
            errors.append(f"{prefix}: missing 'question' text.")

        if qtype in ("single_choice", "multi_choice"):
            if not q.get("options"):
                errors.append(f"{prefix}: 'options' is required for {qtype}.")
            if "answer" not in q:
                errors.append(f"{prefix}: 'answer' is required for {qtype}.")

    return errors


def _import_assessment(data, creator):
    """Persist a validated YAML assessment to the database."""
    assessment = Assessment(
        title=data["title"],
        creator=creator,
    )
    db.session.add(assessment)

    for order, q in enumerate(data["questions"]):
        question = Question(
            assessment=assessment,
            type=q["type"],
            text=q["question"],
            order=order,
        )
        if q.get("options"):
            question.options = q["options"]
        question.answer = q.get("answer", "")
        db.session.add(question)

    db.session.commit()
    return assessment


def _grade_submission(submission):
    """Automatically grade objective answers and save is_correct flags."""
    for answer in submission.answers:
        q = answer.question
        if q.type == "short_answer":
            answer.is_correct = None  # requires manual grading
        else:
            correct = q.answer
            if isinstance(correct, list):
                student_answers = [
                    a.strip()
                    for a in (answer.response or "").split(",")
                ]
                answer.is_correct = sorted(student_answers) == sorted(
                    str(c) for c in correct
                )
            else:
                answer.is_correct = (answer.response or "").strip() == str(
                    correct
                ).strip()
    db.session.commit()


# ---------------------------------------------------------------------------
# Routes – Teacher
# ---------------------------------------------------------------------------


@assessments_bp.route("/import", methods=["GET", "POST"])
def import_assessment():
    """Allow a teacher to upload a YAML assessment file."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    _require_teacher(user)

    errors = []
    if request.method == "POST":
        uploaded_file = request.files.get("yaml_file")
        if not uploaded_file or uploaded_file.filename == "":
            errors.append("No file selected.")
        else:
            try:
                raw = uploaded_file.read().decode("utf-8")
                data = yaml.safe_load(raw)
                errors = _validate_yaml(data)
                if not errors:
                    assessment = _import_assessment(data, user)
                    flash(f"Assessment '{assessment.title}' imported successfully.", "success")
                    return redirect(
                        url_for("assessments.preview", assessment_id=assessment.id)
                    )
            except (yaml.YAMLError, UnicodeDecodeError) as exc:
                errors.append(f"Could not parse YAML file: {exc}")

    return render_template(
        "assessments/import.html", user=user, errors=errors
    )


@assessments_bp.route("/<int:assessment_id>/preview")
def preview(assessment_id):
    """Preview an assessment (teacher only)."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    _require_teacher(user)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None or assessment.creator_id != user.id:
        abort(404)

    return render_template(
        "assessments/preview.html", user=user, assessment=assessment
    )


@assessments_bp.route("/<int:assessment_id>/publish", methods=["POST"])
def publish(assessment_id):
    """Toggle an assessment's published state."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    _require_teacher(user)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None or assessment.creator_id != user.id:
        abort(404)

    assessment.published = not assessment.published
    db.session.commit()

    state = "published" if assessment.published else "unpublished"
    flash(f"Assessment '{assessment.title}' {state}.", "success")
    return redirect(url_for("assessments.preview", assessment_id=assessment.id))


@assessments_bp.route("/<int:assessment_id>/results")
def results(assessment_id):
    """View submission results for an assessment (teacher only)."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    _require_teacher(user)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None or assessment.creator_id != user.id:
        abort(404)

    submissions = (
        Submission.query.filter_by(assessment_id=assessment_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    return render_template(
        "assessments/results.html",
        user=user,
        assessment=assessment,
        submissions=submissions,
    )


@assessments_bp.route("/<int:assessment_id>/results/export")
def export_results(assessment_id):
    """Export submission results as a CSV file (teacher only)."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    _require_teacher(user)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None or assessment.creator_id != user.id:
        abort(404)

    submissions = (
        Submission.query.filter_by(assessment_id=assessment_id)
        .order_by(Submission.submitted_at)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    headers = ["Student", "Email", "Submitted At", "Score", "Total"]
    for q in assessment.questions:
        headers.append(f"Q{q.order + 1}: {q.text[:40]}")
    writer.writerow(headers)

    for sub in submissions:
        correct, total = sub.score
        row = [
            sub.student.display_name,
            sub.student.email,
            sub.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
            correct,
            total,
        ]
        answers_by_qid = {a.question_id: a for a in sub.answers}
        for q in assessment.questions:
            ans = answers_by_qid.get(q.id)
            row.append(ans.response if ans else "")
        writer.writerow(row)

    output.seek(0)
    filename = f"results_{assessment.title.replace(' ', '_')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Routes – Student
# ---------------------------------------------------------------------------


@assessments_bp.route("/")
def list_assessments():
    """List all published assessments available to students."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    if user.is_teacher:
        # Teachers see all their own assessments
        my_assessments = (
            Assessment.query.filter_by(creator_id=user.id)
            .order_by(Assessment.created_at.desc())
            .all()
        )
        return render_template(
            "assessments/teacher_list.html",
            user=user,
            assessments=my_assessments,
        )

    # Students see published assessments and their own submission status
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
        "assessments/student_list.html",
        user=user,
        assessments=published,
        submitted_ids=submitted_ids,
    )


@assessments_bp.route("/<int:assessment_id>/take", methods=["GET", "POST"])
def take(assessment_id):
    """Let a student take (or re-take) an assessment."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    if user.is_teacher:
        abort(403)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None or not assessment.published:
        abort(404)

    # Prevent duplicate submissions
    existing = Submission.query.filter_by(
        student_id=user.id, assessment_id=assessment_id
    ).first()
    if existing:
        flash("You have already submitted this assessment.", "info")
        return redirect(url_for("assessments.confirmation", assessment_id=assessment_id))

    if request.method == "POST":
        submission = Submission(student=user, assessment=assessment)
        db.session.add(submission)
        db.session.flush()  # obtain submission.id before adding answers

        for question in assessment.questions:
            if question.type == "multi_choice":
                selected = request.form.getlist(f"q_{question.id}")
                response = ",".join(selected)
            else:
                response = request.form.get(f"q_{question.id}", "").strip()
            answer = Answer(
                submission=submission,
                question=question,
                response=response,
            )
            db.session.add(answer)

        db.session.commit()
        _grade_submission(submission)

        flash("Your answers have been submitted.", "success")
        return redirect(
            url_for("assessments.confirmation", assessment_id=assessment_id)
        )

    return render_template(
        "assessments/take.html", user=user, assessment=assessment
    )


@assessments_bp.route("/<int:assessment_id>/confirmation")
def confirmation(assessment_id):
    """Show a confirmation page after submission."""
    redirect_response = _require_login()
    if redirect_response:
        return redirect_response

    user = _current_user()
    if user.is_teacher:
        abort(403)

    assessment = db.session.get(Assessment, assessment_id)
    if assessment is None:
        abort(404)

    submission = Submission.query.filter_by(
        student_id=user.id, assessment_id=assessment_id
    ).first()

    return render_template(
        "assessments/confirmation.html",
        user=user,
        assessment=assessment,
        submission=submission,
    )
