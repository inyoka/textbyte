"""SQLAlchemy database models."""

import json
from datetime import datetime, timezone

from app.extensions import db


class User(db.Model):
    """Represents a user authenticated via Microsoft Entra ID."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    microsoft_id = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    display_name = db.Column(db.String(256), nullable=False)
    # Role is set manually by an administrator; defaults to "student".
    role = db.Column(db.String(16), nullable=False, default="student")
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    assessments = db.relationship(
        "Assessment", back_populates="creator", lazy="dynamic"
    )
    submissions = db.relationship(
        "Submission", back_populates="student", lazy="dynamic"
    )

    @property
    def is_teacher(self):
        return self.role == "teacher"

    def __repr__(self):
        return f"<User {self.email}>"


class Assessment(db.Model):
    """An assessment (test) imported by a teacher."""

    __tablename__ = "assessments"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    creator_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    creator = db.relationship("User", back_populates="assessments")
    questions = db.relationship(
        "Question",
        back_populates="assessment",
        order_by="Question.order",
        cascade="all, delete-orphan",
    )
    submissions = db.relationship(
        "Submission",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Assessment {self.title!r}>"


class Question(db.Model):
    """A single question belonging to an assessment."""

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(
        db.Integer, db.ForeignKey("assessments.id"), nullable=False
    )
    # Supported types: single_choice, multi_choice, short_answer
    type = db.Column(db.String(32), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # JSON-encoded list of option strings (null for open questions)
    _options = db.Column("options", db.Text, nullable=True)
    # JSON-encoded correct answer (string or list)
    _answer = db.Column("answer", db.Text, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)

    assessment = db.relationship("Assessment", back_populates="questions")
    answers = db.relationship(
        "Answer", back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def options(self):
        return json.loads(self._options) if self._options else []

    @options.setter
    def options(self, value):
        self._options = json.dumps(value) if value is not None else None

    @property
    def answer(self):
        return json.loads(self._answer)

    @answer.setter
    def answer(self, value):
        self._answer = json.dumps(value)

    def __repr__(self):
        return f"<Question {self.id} ({self.type})>"


class Submission(db.Model):
    """A student's completed attempt at an assessment."""

    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    assessment_id = db.Column(
        db.Integer, db.ForeignKey("assessments.id"), nullable=False
    )
    submitted_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    student = db.relationship("User", back_populates="submissions")
    assessment = db.relationship("Assessment", back_populates="submissions")
    answers = db.relationship(
        "Answer", back_populates="submission", cascade="all, delete-orphan"
    )

    @property
    def score(self):
        """Return (correct_count, total_count) for objective questions."""
        objective = [a for a in self.answers if a.is_correct is not None]
        correct = sum(1 for a in objective if a.is_correct)
        return correct, len(objective)

    def __repr__(self):
        return f"<Submission {self.id} by user {self.student_id}>"


class Answer(db.Model):
    """A student's answer to one question within a submission."""

    __tablename__ = "answers"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer, db.ForeignKey("submissions.id"), nullable=False
    )
    question_id = db.Column(
        db.Integer, db.ForeignKey("questions.id"), nullable=False
    )
    # The raw text of the student's answer
    response = db.Column(db.Text, nullable=True)
    # None for open questions that require manual grading
    is_correct = db.Column(db.Boolean, nullable=True)

    submission = db.relationship("Submission", back_populates="answers")
    question = db.relationship("Question", back_populates="answers")

    def __repr__(self):
        return f"<Answer submission={self.submission_id} q={self.question_id}>"
