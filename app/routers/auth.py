"""Authentication router for Google OAuth2 flow."""
from fastapi import APIRouter, HTTPException
from app.services.google_auth import (
    get_google_credentials,
    get_auth_status,
    revoke_credentials,
    SCOPES
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/status")
async def auth_status():
    """
    Check current authentication status without triggering OAuth flow.

    This is a read-only endpoint that reports whether valid Google credentials
    are available, which scopes are authorized, and file existence status.

    Returns:
        dict: Authentication status with:
            - authenticated (bool): Whether valid credentials exist
            - scopes (list): List of authorized OAuth scopes
            - token_file_exists (bool): Whether tokens.json exists
            - credentials_file_exists (bool): Whether credentials.json exists
            - token_expired (bool|None): Token expiration status

    Example response:
        {
            "authenticated": false,
            "scopes": [],
            "token_file_exists": false,
            "credentials_file_exists": true,
            "token_expired": null
        }
    """
    return get_auth_status()


@router.post("/initiate")
async def initiate_auth():
    """
    Initiate Google OAuth2 authentication flow.

    WARNING: This endpoint BLOCKS while waiting for browser-based user consent.
    Only call during initial setup, not from automated workflows.

    If no valid tokens exist, this will:
    1. Open a browser window for user consent
    2. Wait for user to approve scopes
    3. Save tokens to tokens.json
    4. Return authentication status

    If valid tokens already exist, returns current status immediately.

    Returns:
        dict: Authentication result with:
            - status (str): "authenticated"
            - scopes (list): Authorized OAuth scopes

    Raises:
        HTTPException 400: If credentials.json is missing
        HTTPException 500: If OAuth flow fails

    Example response:
        {
            "status": "authenticated",
            "scopes": [
                "https://www.googleapis.com/auth/webmasters.readonly",
                "https://www.googleapis.com/auth/documents"
            ]
        }
    """
    try:
        creds = get_google_credentials()
        return {
            "status": "authenticated",
            "scopes": creds.scopes or SCOPES
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/revoke")
async def revoke_auth():
    """
    Revoke current Google OAuth2 credentials.

    This deletes the tokens.json file, requiring re-authentication.
    Useful when:
    - Scopes need to be changed
    - Tokens become corrupted
    - User wants to authenticate with different Google account

    Returns:
        dict: Revocation result with:
            - revoked (bool): Whether credentials were revoked
            - message (str): Status message

    Example response:
        {
            "revoked": true,
            "message": "Credentials revoked successfully"
        }
    """
    return revoke_credentials()
