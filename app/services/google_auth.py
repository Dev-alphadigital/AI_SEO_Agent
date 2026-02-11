"""Google OAuth2 authentication and token management service."""
import os
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from app.config import get_settings


# Scopes required for Search Console and Google Docs access
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'https://www.googleapis.com/auth/documents'
]


def get_google_credentials() -> Credentials:
    """
    Get valid Google OAuth2 credentials, initiating browser flow if needed.

    This function manages the full OAuth2 lifecycle:
    - Loads existing tokens from tokens.json if available
    - Refreshes expired tokens using refresh_token
    - Initiates browser-based consent flow if no valid tokens exist

    WARNING: This function BLOCKS during browser consent flow.
    Only call from /auth/initiate endpoint, not from regular API calls.

    Returns:
        Credentials: Valid Google OAuth2 credentials

    Raises:
        FileNotFoundError: If credentials.json doesn't exist
        google.auth.exceptions.RefreshError: If token refresh fails
    """
    settings = get_settings()
    creds = None

    # Load existing tokens if available
    if Path(settings.token_file).exists():
        creds = Credentials.from_authorized_user_file(settings.token_file, SCOPES)

    # Refresh expired tokens or initiate new flow
    if creds and creds.expired and creds.refresh_token:
        # Token expired but we have refresh token - refresh it
        creds.refresh(Request())
        # Save refreshed credentials
        with open(settings.token_file, 'w') as token:
            token.write(creds.to_json())
    elif not creds or not creds.valid:
        # No valid credentials - initiate OAuth flow
        if not Path(settings.credentials_file).exists():
            raise FileNotFoundError(
                f"credentials.json not found at {settings.credentials_file}. "
                "Download OAuth 2.0 credentials from Google Cloud Console: "
                "https://console.cloud.google.com/apis/credentials"
            )

        # InstalledAppFlow automatically sets access_type='offline' to get refresh token
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.credentials_file,
            SCOPES
        )

        # BLOCKING: Opens browser for user consent
        creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(settings.token_file, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_auth_status() -> dict:
    """
    Check current authentication status without triggering OAuth flow.

    This is a read-only check that reports the current state of authentication
    without initiating any browser flows or token refreshes.

    Returns:
        dict: Authentication status with keys:
            - authenticated (bool): Whether valid credentials are available
            - scopes (list): List of authorized scopes
            - token_file_exists (bool): Whether tokens.json exists
            - credentials_file_exists (bool): Whether credentials.json exists
            - token_expired (bool|None): Whether token is expired (None if no token)
    """
    settings = get_settings()

    status = {
        "authenticated": False,
        "scopes": [],
        "token_file_exists": Path(settings.token_file).exists(),
        "credentials_file_exists": Path(settings.credentials_file).exists(),
        "token_expired": None
    }

    # Check if tokens exist and are valid
    if status["token_file_exists"]:
        try:
            creds = Credentials.from_authorized_user_file(settings.token_file, SCOPES)
            status["scopes"] = creds.scopes or []
            status["token_expired"] = creds.expired
            status["authenticated"] = creds.valid
        except Exception:
            # Token file exists but is corrupted/invalid
            status["authenticated"] = False
            status["token_expired"] = True

    return status


def revoke_credentials() -> dict:
    """
    Revoke current credentials by deleting the token file.

    This allows re-authentication if scopes change or tokens become corrupted.

    Returns:
        dict: Status with 'revoked' boolean and 'message' string
    """
    settings = get_settings()

    if Path(settings.token_file).exists():
        os.remove(settings.token_file)
        return {"revoked": True, "message": "Credentials revoked successfully"}

    return {"revoked": False, "message": "No credentials found to revoke"}
