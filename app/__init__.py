"""Flask application factory."""

from flask import Flask

from config import Config


def create_app(config_object=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=False)

    # Load configuration
    app.config.from_object(config_object or Config())

    # Initialise extensions
    from app.extensions import db
    db.init_app(app)

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.assessments.routes import assessments_bp
    from app.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(assessments_bp)

    # Create database tables on first run
    with app.app_context():
        db.create_all()

    return app
