"""Authentication blueprint using Microsoft MSAL."""

import uuid

import msal
from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.extensions import db
from app.models.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _build_msal_app(cache=None):
    """Create a confidential MSAL client application."""
    cfg = current_app.config
    return msal.ConfidentialClientApplication(
        cfg["AZURE_CLIENT_ID"],
        authority=cfg["AZURE_AUTHORITY"],
        client_credential=cfg["AZURE_CLIENT_SECRET"],
        token_cache=cache,
    )


def _build_auth_url(state=None):
    """Return the Microsoft login URL."""
    cfg = current_app.config
    return _build_msal_app().get_authorization_request_url(
        scopes=cfg["AZURE_SCOPES"],
        state=state or str(uuid.uuid4()),
        redirect_uri=cfg["AZURE_REDIRECT_URI"],
    )


def _load_cache():
    """Load the MSAL token cache from the Flask session."""
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache


def _save_cache(cache):
    """Persist the MSAL token cache back to the Flask session."""
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()


def _get_token_from_cache(scopes):
    """Return a cached access token, refreshing silently if needed."""
    cache = _load_cache()
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:
        result = cca.acquire_token_silent(scopes, account=accounts[0])
        _save_cache(cache)
        return result
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@auth_bp.route("/login")
def login():
    """Redirect the browser to Microsoft's login page."""
    state = str(uuid.uuid4())
    session["auth_state"] = state
    auth_url = _build_auth_url(state=state)
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    """Handle the OAuth 2.0 redirect from Microsoft."""
    # Validate the state parameter to prevent CSRF
    if request.args.get("state") != session.get("auth_state"):
        return render_template("auth/error.html", error="State mismatch - possible CSRF attack."), 400

    if "error" in request.args:
        return render_template(
            "auth/error.html",
            error=request.args.get("error_description", request.args["error"]),
        ), 400

    code = request.args.get("code")
    if not code:
        return render_template("auth/error.html", error="No authorisation code received."), 400

    cfg = current_app.config
    cache = _load_cache()
    cca = _build_msal_app(cache=cache)
    result = cca.acquire_token_by_authorization_code(
        code,
        scopes=cfg["AZURE_SCOPES"],
        redirect_uri=cfg["AZURE_REDIRECT_URI"],
    )

    if "error" in result:
        return render_template(
            "auth/error.html",
            error=result.get("error_description", result["error"]),
        ), 400

    _save_cache(cache)

    claims = result.get("id_token_claims", {})
    microsoft_id = claims.get("oid") or claims.get("sub", "")
    email = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn", "")
    )
    display_name = claims.get("name", email)

    # Create or update the local user record
    user = User.query.filter_by(microsoft_id=microsoft_id).first()
    if user is None:
        user = User(
            microsoft_id=microsoft_id,
            email=email,
            display_name=display_name,
        )
        db.session.add(user)
    else:
        user.email = email
        user.display_name = display_name
    db.session.commit()

    session["user_id"] = user.id
    session["user_name"] = user.display_name

    return redirect(url_for("main.dashboard"))


@auth_bp.route("/logout")
def logout():
    """Clear the local session and redirect to Microsoft's logout endpoint."""
    session.clear()
    cfg = current_app.config
    logout_url = (
        f"https://login.microsoftonline.com/{cfg['AZURE_TENANT_ID']}"
        "/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={url_for('main.index', _external=True)}"
    )
    return redirect(logout_url)
