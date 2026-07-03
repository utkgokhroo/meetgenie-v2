import json
from pathlib import Path

import requests
import streamlit as st
from streamlit_oauth import OAuth2Component

# -----------------------------
# Load Google OAuth credentials
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_SECRET_FILE = BASE_DIR / "client_secret_web.json"

with open(CLIENT_SECRET_FILE, "r") as f:
    creds = json.load(f)["web"]

CLIENT_ID = creds["client_id"]
CLIENT_SECRET = creds["client_secret"]

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]

REDIRECT_URI = "http://localhost:8501"

oauth2 = OAuth2Component(
    CLIENT_ID,
    CLIENT_SECRET,
    AUTHORIZE_URL,
    TOKEN_URL,
)


def google_login():
    result = oauth2.authorize_button(
        name="🔐 Sign in with Google",
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        key="google_login",
    )

    if not result:
        return None

    token = result["token"]

    # Save token for this Streamlit session
    st.session_state["google_token"] = token

    # -----------------------------
    # Fetch Google profile
    # -----------------------------
    try:
        response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={
                "Authorization": f"Bearer {token['access_token']}"
            },
            timeout=10,
        )

        response.raise_for_status()
        profile = response.json()

    except requests.RequestException as e:
        st.error(f"Failed to fetch Google profile: {e}")
        return None

    token["client_id"] = CLIENT_ID
    token["client_secret"] = CLIENT_SECRET
    # -----------------------------
    # Return everything app.py needs
    # -----------------------------
    return {
        "email": profile["email"],
        "name": profile.get("name", ""),
        "picture": profile.get("picture", ""),
        "credentials": json.dumps(token),   # Ready to save in SQLite
        "token": token,                     # Keep as dict for current session if needed
    }