"""Application configuration."""

import os
import warnings


class Config:
    """Base configuration loaded from environment variables."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    def __init__(self):
        if self.SECRET_KEY == "change-me-in-production":
            warnings.warn(
                "SECRET_KEY is set to the default insecure value. "
                "Set the SECRET_KEY environment variable before deploying.",
                stacklevel=2,
            )

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///textbyte.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Microsoft Entra ID (Azure AD) credentials
    # Register your app at https://portal.azure.com/ and set these values.
    AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
    AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "common")

    # The redirect URI registered in your Azure App Registration.
    # During development this is typically http://localhost:5000/auth/callback
    AZURE_REDIRECT_URI = os.environ.get(
        "AZURE_REDIRECT_URI", "http://localhost:5000/auth/callback"
    )

    # MSAL scopes requested during sign-in
    AZURE_SCOPES = ["User.Read"]

    # Authority URL – use "common" to allow any Microsoft account (personal +
    # work/school).  Replace with your tenant ID to restrict to a single tenant.
    @property
    def AZURE_AUTHORITY(self):  # noqa: N802
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"
