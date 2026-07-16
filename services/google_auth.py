import json
import secrets
from pathlib import Path
from typing import Optional

import requests
import streamlit as st
from streamlit_oauth import OAuth2Component

# -----------------------------
# Load Google OAuth credentials
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_SECRET_FILE = BASE_DIR / "client_secret_web.json"

IS_CLOUD = "client_secret_web" in st.secrets

if IS_CLOUD:
    creds = st.secrets["client_secret_web"]
    CLIENT_ID = creds["client_id"]
    CLIENT_SECRET = creds["client_secret"]
    REDIRECT_URI = creds["redirect_uri"]
else:
    with open(CLIENT_SECRET_FILE, "r") as f:
        creds = json.load(f)["web"]

    CLIENT_ID = creds["client_id"]
    CLIENT_SECRET = creds["client_secret"]

    REDIRECT_URI = "http://localhost:8501"

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]

oauth2 = OAuth2Component(
    CLIENT_ID,
    CLIENT_SECRET,
    AUTHORIZE_URL,
    TOKEN_URL,
)

SESSION_PARAM = "sid"


def _fetch_profile(access_token: str) -> Optional[dict]:
    """Fetch Google user profile. Returns None on failure."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _refresh_access_token(token: dict) -> Optional[dict]:
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        return None

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        resp.raise_for_status()
        new_data = resp.json()

        updated = {**token, **new_data}
        if "refresh_token" not in new_data:
            updated["refresh_token"] = refresh_token
        return updated

    except requests.RequestException:
        return None


def _build_user_dict(token: dict, profile: dict) -> dict:
    token["client_id"] = CLIENT_ID
    token["client_secret"] = CLIENT_SECRET
    return {
        "email": profile["email"],
        "name": profile.get("name", ""),
        "picture": profile.get("picture", ""),
        "credentials": json.dumps(token),
        "token": token,
    }


def google_login() -> Optional[dict]:
    result = oauth2.authorize_button(
        name="Sign-in with Google",
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        key="google_login",
    )

    if not result:
        return None

    token = result["token"]
    token["client_id"] = CLIENT_ID
    token["client_secret"] = CLIENT_SECRET

    profile = _fetch_profile(token["access_token"])
    if not profile:
        st.error("Failed to fetch Google profile.")
        return None

    st.session_state["google_token"] = token
    return _build_user_dict(token, profile)


def restore_session() -> Optional[dict]:

    from services.database import get_session, get_user, update_user_credentials

    sid = st.query_params.get(SESSION_PARAM)
    if not sid:
        return None

    email = get_session(sid)
    if not email:
        return None

    db_user = get_user(email)
    if not db_user:
        return None

    user_id, db_email, db_name, credentials_json, _ = db_user  # _ = created_at

    try:
        token = json.loads(credentials_json)
    except (json.JSONDecodeError, TypeError):
        return None

    profile = _fetch_profile(token.get("access_token", ""))

    if not profile:
        refreshed = _refresh_access_token(token)
        if not refreshed:
            return None
        token = refreshed
        profile = _fetch_profile(token["access_token"])
        if not profile:
            return None
        update_user_credentials(email, json.dumps(token))

    user = _build_user_dict(token, profile)
    user["id"] = user_id
    return user


def create_session_token() -> str:
    """Generate a cryptographically random session token."""
    return secrets.token_urlsafe(32)


def set_session_param(token: str) -> None:
    """Write the session token into the URL query params."""
    st.query_params[SESSION_PARAM] = token


def clear_session_param() -> None:
    """Remove the session token from the URL query params."""
    if SESSION_PARAM in st.query_params:
        del st.query_params[SESSION_PARAM]
