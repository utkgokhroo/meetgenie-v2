import streamlit as st
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from services.google_auth import (
    google_login,
    restore_session,
    create_session_token,
    set_session_param,
    clear_session_param,
)
from services.database import (
    save_user, get_user, create_session, delete_session,
    init_db, save_meeting, delete_meeting,
    get_all_meetings, search_meetings,
    get_dashboard_stats, get_recent_meetings,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import plotly.express as px
from core.sentiment import get_dominant_sentiment
from core.processor import process_video
from core.chat_with_meeting import ask_meeting_question
from services.email_sender import send_summary_email
from services.pdf_exporter import generate_summary_pdf
from core.speaker_intelligence import calculate_talk_time, calculate_participation, get_top_speaker
from recording.recording_manager import start_recording, stop_recording, get_recording_duration, is_recording
from services.calendar_extractor import extract_calendar_events
from services.calendar_service import create_calendar_events, get_calendar_service
from services.question_suggester import generate_questions

os.makedirs("uploads", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
os.makedirs("summaries", exist_ok=True)

init_db()

st.set_page_config(
    page_title="MeetGenie",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "recording" not in st.session_state:
    st.session_state.recording = False

# ─────────────────────────────────────────────────────────────────────────────
#  STYLES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ═══════════════════════════════
   DESIGN TOKENS
═══════════════════════════════ */
:root {
    /* Backgrounds — slightly more contrast between layers */
    --bg-base:        #0b0d15;
    --bg-surface:     #12151f;
    --bg-surface-2:   #171a28;
    --bg-elevated:    #1c2030;
    --bg-overlay:     #141c38;

    /* Borders — more visible separation */
    --border:         #1e2438;
    --border-mid:     #272d42;
    --border-strong:  #303756;
    --border-accent:  #2a3260;
    --border-hover:   #3d4f8a;

    /* Brand */
    --red:            #ff4b4b;
    --red-dim:        #3d1515;
    --red-border:     #5c2020;
    --accent:         #4f7cff;
    --accent-dim:     #192050;
    --accent-light:   #7ca3ff;
    --green:          #22c55e;
    --green-dim:      #0d2d1a;
    --amber:          #f59e0b;
    --amber-dim:      #2d1f05;

    /* Typography */
    --text-primary:   #edf0fa;
    --text-secondary: #b4bad0;
    --text-muted:     #6b7194;
    --text-faint:     #454c6a;
    --text-ghost:     #2d3350;

    /* Fonts */
    --font-body:  'DM Sans', sans-serif;
    --font-mono:  'DM Mono', monospace;

    /* Radii */
    --radius-sm:  6px;
    --radius:     10px;
    --radius-lg:  14px;

    /* Spacing rhythm */
    --space-xs:   4px;
    --space-sm:   8px;
    --space-md:   16px;
    --space-lg:   24px;
    --space-xl:   36px;
}

/* ═══════════════════════════════
   GLOBAL RESET
═══════════════════════════════ */
html, body {
    font-family: var(--font-body) !important;
    background: var(--bg-base) !important;
    color: var(--text-primary) !important;
}
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stHeader"],
[data-testid="stBottom"] {
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
}

/* ═══════════════════════════════
   TYPOGRAPHY
═══════════════════════════════ */
[data-testid="stMarkdown"],
[data-testid="stMarkdownContainer"],
[data-testid="stText"] { color: var(--text-primary) !important; }

[data-testid="stMarkdown"] > div > p,
[data-testid="stMarkdown"] > div > ul,
[data-testid="stMarkdown"] > div > ol,
[data-testid="stMarkdown"] > div > li { color: var(--text-primary) !important; }

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: var(--text-muted) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    font-family: var(--font-body) !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
}

hr { border-color: var(--border) !important; }

/* ═══════════════════════════════
   SIDEBAR
═══════════════════════════════ */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebarContent"] * { color: var(--text-primary) !important; }
[data-testid="stSidebarNav"] { display: none; }

/* Invisible overlay buttons for sidebar nav */
.sb-btn-wrap { position: relative; }
.sb-btn-wrap button {
    opacity: 0 !important;
    position: absolute !important;
    inset: 0 !important;
    height: 100% !important;
    width: 100% !important;
    margin: 0 !important;
    cursor: pointer !important;
    z-index: 10 !important;
}

/* ═══════════════════════════════
   FORM INPUTS
═══════════════════════════════ */
[data-testid="stTextInput"],
[data-testid="stTextInputRootElement"] { background-color: transparent !important; }

[data-testid="stTextInput"] input,
[data-testid="stTextInputRootElement"] input {
    background-color: var(--bg-elevated) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    caret-color: var(--accent) !important;
    padding: 10px 14px !important;
    transition: border-color 0.15s !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder { color: var(--text-ghost) !important; }
[data-testid="stTextInput"] input:focus,
[data-testid="stTextInputRootElement"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(79,124,255,0.12) !important;
    outline: none !important;
}

/* ═══════════════════════════════
   FILE UPLOADER
═══════════════════════════════ */
[data-testid="stFileUploader"] { background-color: transparent !important; }
[data-testid="stFileUploaderDropzone"] {
    background-color: var(--bg-elevated) !important;
    border: 1.5px dashed var(--border-mid) !important;
    border-radius: var(--radius) !important;
    transition: border-color 0.2s, background-color 0.2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--accent) !important;
    background-color: var(--accent-dim) !important;
}
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] small { color: var(--text-muted) !important; }
[data-testid="stFileChip"] {
    background-color: var(--bg-elevated) !important;
    border-color: var(--border-mid) !important;
    border-radius: var(--radius-sm) !important;
}
[data-testid="stFileChipName"] { color: var(--text-secondary) !important; }

/* ═══════════════════════════════
   BUTTONS
═══════════════════════════════ */
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    letter-spacing: 0.01em !important;
    padding: 0 16px !important;
    height: 38px !important;
    transition: all 0.15s ease !important;
}

/* Secondary / default */
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]),
[data-testid="stDownloadButton"] button {
    background-color: var(--bg-elevated) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-secondary) !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]):hover,
[data-testid="stDownloadButton"] button:hover {
    background-color: var(--bg-surface-2) !important;
    border-color: var(--accent) !important;
    color: var(--text-primary) !important;
}

/* Primary (red) */
[data-testid="stButton"] button[kind="primary"] {
    background-color: var(--red) !important;
    border-color: var(--red) !important;
    color: #fff !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #e63e3e !important;
    border-color: #e63e3e !important;
    box-shadow: 0 0 0 3px rgba(255,75,75,0.2) !important;
}

/* ═══════════════════════════════
   ALERTS
═══════════════════════════════ */
[data-testid="stAlert"],
[data-testid="stAlertContainer"] {
    border-radius: var(--radius-sm) !important;
    font-size: 13px !important;
    font-family: var(--font-body) !important;
}
[data-testid="stAlertContainer"][data-baseweb="notification"] {
    background-color: var(--bg-surface) !important;
}

/* ═══════════════════════════════
   EXPANDERS
═══════════════════════════════ */
[data-testid="stExpander"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary p {
    background-color: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
    font-size: 13.5px !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    padding: 2px 0 !important;
}
[data-testid="stExpanderDetails"] {
    background-color: var(--bg-surface) !important;
    border-top: 1px solid var(--border) !important;
    padding-top: 4px !important;
}

/* ═══════════════════════════════
   MISC WIDGETS
═══════════════════════════════ */
[data-testid="stSpinner"] p,
[data-testid="stSpinner"] span { color: var(--text-muted) !important; }

[data-testid="stMetric"] { background: transparent; }
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: var(--text-primary) !important; }

[data-testid="stColumn"] { background-color: transparent !important; }

/* ═══════════════════════════════
   SCROLLBAR
═══════════════════════════════ */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }

/* Plotly transparent background */
.js-plotly-plot .plotly .bg { fill: transparent !important; }

/* ═══════════════════════════════
   NAV BAR  (top of each page)
═══════════════════════════════ */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0 18px;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--space-lg);
}
.nav-logo { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; color: #fff; }
.nav-logo span { color: var(--accent); }
.nav-tag {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    padding: 4px 12px;
    border-radius: 20px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* ═══════════════════════════════
   SIDEBAR COMPONENTS
═══════════════════════════════ */
.sb-logo {
    font-size: 19px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.4px;
    padding: 2px 0 20px;
}
.sb-logo span { color: var(--accent); }

.sb-user-block {
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: var(--radius);
    padding: 12px 14px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.sb-avatar {
    width: 34px; height: 34px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    border: 1.5px solid var(--border-accent);
}
.sb-user-name { font-size: 13px; font-weight: 600; color: var(--text-primary); line-height: 1.3; }
.sb-user-email { font-size: 10px; color: var(--text-faint); font-family: var(--font-mono); margin-top: 1px; }

.sb-section-label {
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--text-ghost);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding: 2px 0;
    margin: 14px 0 4px;
}

.sb-nav-item {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 12px;
    border-radius: var(--radius-sm);
    margin-bottom: 1px;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--text-muted);
    transition: all 0.12s;
    cursor: pointer;
    /* Reserve 1px border space always to prevent layout shift */
    border: 1px solid transparent;
}
.sb-nav-item.active {
    background: var(--accent-dim);
    color: var(--accent-light);
    border-color: var(--border-accent);
}
.sb-nav-item:not(.active):hover {
    background: var(--bg-elevated);
    color: var(--text-primary);
    border-color: var(--border);
}

.sb-divider { border-top: 1px solid var(--border); margin: 10px 0; }

.sb-stat-block {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    margin-top: 10px;
}
.sb-stat-num { font-size: 17px; font-weight: 700; color: var(--text-primary); }
.sb-stat-label {
    font-size: 9px; color: var(--text-faint);
    font-family: var(--font-mono); text-transform: uppercase;
    letter-spacing: 0.8px; margin-top: 2px;
}

/* ═══════════════════════════════
   PAGE TITLES & SECTION HEADERS
═══════════════════════════════ */
.page-title {
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.4px;
    margin: 0 0 4px;
    line-height: 1.2;
}
.page-subtitle {
    font-size: 13.5px;
    color: var(--text-muted);
    margin-bottom: var(--space-lg);
    line-height: 1.55;
}
.section-header {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: var(--space-lg) 0 var(--space-sm);
    padding-bottom: var(--space-sm);
    border-bottom: 1px solid var(--border);
}

/* ═══════════════════════════════
   SPACERS
═══════════════════════════════ */
.gap-xs { height: var(--space-xs); }
.gap-sm { height: var(--space-sm); }
.gap    { height: var(--space-md); }
.gap-lg { height: var(--space-lg); }
.gap-xl { height: var(--space-xl); }

/* ═══════════════════════════════
   DASHBOARD
═══════════════════════════════ */
.dash-stat-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
}
.dash-stat-num {
    font-size: 30px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -1px;
    line-height: 1;
    margin-bottom: 6px;
}
.dash-stat-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.9px;
}
.dash-stat-sub {
    font-size: 11.5px;
    color: var(--text-muted);
    margin-top: 4px;
}

.dash-section-title {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
    margin-top: var(--space-lg);
}

.dash-meeting-row {
    padding: 11px 0;
    border-bottom: 1px solid var(--border);
}
.dash-meeting-row:last-child { border-bottom: none; }
.dash-meeting-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.dash-meeting-date {
    font-size: 10.5px;
    color: var(--text-faint);
    font-family: var(--font-mono);
    margin-top: 2px;
}
.dash-meeting-preview {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.dash-cal-event {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.dash-cal-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.dash-cal-time {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    margin-top: 3px;
}

.dash-quick-action {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 16px;
    text-align: center;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: border-color 0.15s, background-color 0.15s;
}
.dash-quick-action:hover {
    border-color: var(--border-hover);
    background: var(--bg-elevated);
}
.dash-qa-icon { font-size: 22px; margin-bottom: 8px; }
.dash-qa-label { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.dash-qa-sub { font-size: 11.5px; color: var(--text-muted); }

/* ═══════════════════════════════
   PROFILE
═══════════════════════════════ */
.profile-hero {
    background: linear-gradient(135deg, #13193a 0%, var(--bg-surface) 100%);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-lg);
    padding: 32px 36px;
    display: flex;
    align-items: center;
    gap: 28px;
    margin-bottom: var(--space-lg);
}
.profile-avatar-wrap { position: relative; flex-shrink: 0; }
.profile-avatar {
    width: 88px; height: 88px;
    border-radius: 50%;
    object-fit: cover;
    border: 3px solid var(--border-accent);
    display: block;
}
.profile-avatar-fallback {
    width: 88px; height: 88px;
    border-radius: 50%;
    background: var(--accent-dim);
    border: 3px solid var(--border-accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 34px;
}
.profile-info { flex: 1; min-width: 0; }
.profile-name {
    font-size: 26px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.4px;
    margin-bottom: 8px;
    line-height: 1.2;
}
.profile-email-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border-mid);
    border-radius: 20px; padding: 4px 12px;
    font-size: 11.5px; font-family: var(--font-mono); color: var(--text-muted);
}
.profile-google-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border-mid);
    border-radius: 20px; padding: 4px 12px;
    font-size: 11px; color: var(--text-muted); margin-top: 8px;
}
.profile-stat-row { display: flex; gap: 12px; margin-bottom: var(--space-lg); flex-wrap: wrap; }
.profile-stat-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    flex: 1; min-width: 130px;
}
.profile-stat-num {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.5px;
    line-height: 1;
}
.profile-stat-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 6px;
}
.profile-detail-grid {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: var(--space-lg);
}
.profile-detail-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 15px 20px;
    border-bottom: 1px solid var(--border);
}
.profile-detail-row:last-child { border-bottom: none; }
.profile-detail-label { font-size: 13px; font-weight: 500; color: var(--text-muted); }
.profile-detail-value { font-size: 13px; color: var(--text-primary); text-align: right; }
.profile-detail-value.mono {
    font-family: var(--font-mono);
    font-size: 11.5px;
    color: var(--text-secondary);
}
.profile-connected-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--green-dim);
    border: 1px solid #1a4d2e;
    border-radius: 20px; padding: 3px 10px;
    font-size: 11px; color: var(--green);
}
.profile-logout-zone {
    background: var(--red-dim);
    border: 1px solid var(--red-border);
    border-radius: var(--radius);
    padding: 18px 22px;
}
.profile-logout-text { font-size: 14px; font-weight: 600; color: #ffaaaa; }
.profile-logout-sub { font-size: 12px; color: var(--text-faint); margin-top: 4px; }

/* ═══════════════════════════════
   MEETING HISTORY
═══════════════════════════════ */
.hcard {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 10px;
    transition: border-color 0.15s, box-shadow 0.15s;
    overflow: hidden;
}
.hcard:hover {
    border-color: var(--border-hover);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.hcard-header { padding: 16px 18px 14px; }
.hcard-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 6px;
}
.hcard-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.2px;
    line-height: 1.3;
    flex: 1;
    min-width: 0;
}
.hcard-date {
    font-size: 10.5px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    white-space: nowrap;
    flex-shrink: 0;
}
.hcard-overview {
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.hcard-chips {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    margin-top: 10px;
}
.hcard-chip {
    display: inline-flex; align-items: center; gap: 3px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 10.5px;
    font-family: var(--font-mono);
    color: var(--text-faint);
}
.hcard-chip.accent {
    color: var(--accent-light);
    border-color: var(--border-accent);
    background: var(--accent-dim);
}

.history-empty {
    text-align: center;
    padding: 56px 24px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}
.history-empty-icon { font-size: 36px; margin-bottom: 14px; }
.history-empty-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
.history-empty-sub { font-size: 13px; color: var(--text-muted); line-height: 1.6; max-width: 360px; margin: 0 auto; }

/* ═══════════════════════════════
   SETTINGS
═══════════════════════════════ */
.settings-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 15px 0; border-bottom: 1px solid var(--border);
}
.settings-row:last-child { border-bottom: none; }
.settings-label { font-size: 13.5px; font-weight: 500; color: var(--text-primary); }
.settings-sub { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }

/* ═══════════════════════════════
   SUMMARY RESULT CARDS
═══════════════════════════════ */
.overview-card {
    background: linear-gradient(135deg, #141c38 0%, var(--bg-surface) 100%);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-lg);
    padding: 22px 26px;
    margin-bottom: var(--space-lg);
}
.overview-card .ov-label {
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--accent-light);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 10px;
}
.overview-card p {
    color: #d4d9ee;
    font-size: 14px;
    line-height: 1.75;
    margin: 0;
}

.stat-row { display: flex; gap: 8px; margin-bottom: var(--space-lg); flex-wrap: wrap; }
.stat-badge {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 10px 14px;
    flex: 1;
    min-width: 90px;
}
.stat-badge .stat-num {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    display: block;
    line-height: 1;
}
.stat-badge .stat-label {
    font-size: 9.5px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-family: var(--font-mono);
    margin-top: 4px;
    display: block;
}

.meta-row { display: flex; gap: 6px; margin-bottom: var(--space-md); flex-wrap: wrap; }
.meta-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: 20px; padding: 4px 11px;
    font-size: 11.5px; font-family: var(--font-mono); color: var(--text-muted);
}

.section-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    margin-bottom: 10px;
    height: 100%;
}
.section-card h4 {
    font-size: 9.5px;
    font-family: var(--font-mono);
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 10px;
}
.section-card p, .section-card li {
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.65;
    margin: 0;
}
.section-card ul { padding-left: 15px; margin: 0; }
.section-card li { margin-bottom: 5px; }
.section-card .empty { color: var(--text-ghost); font-style: italic; font-size: 12.5px; }

/* ═══════════════════════════════
   TRANSCRIPT
═══════════════════════════════ */
.seg-block {
    background: var(--bg-elevated);
    border-left: 2px solid var(--border-accent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 9px 13px;
    margin-bottom: 8px;
}
.seg-header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 3px; }
.seg-speaker { font-size: 11px; font-weight: 600; color: var(--accent-light); font-family: var(--font-mono); }
.seg-time { font-size: 10px; color: var(--text-ghost); font-family: var(--font-mono); }
.seg-text { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 0; }
.seg-sentiment { font-size: 10px; color: var(--text-ghost); margin-top: 3px; font-family: var(--font-mono); }
.seg-sentiment.POS { color: #22c55e; }
.seg-sentiment.NEG { color: var(--red); }

/* ═══════════════════════════════
   ANALYTICS
═══════════════════════════════ */
.analytics-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    margin-bottom: 10px;
}
.analytics-card .ac-header {
    font-size: 9.5px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 12px;
}
.speaker-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 0; border-bottom: 1px solid var(--border);
}
.speaker-row:last-child { border-bottom: none; }
.speaker-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.speaker-meta { font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono); }
.sentiment-pill {
    font-size: 10px; font-family: var(--font-mono);
    padding: 2px 8px; border-radius: 10px; letter-spacing: 0.4px;
}
.sentiment-pill.POS { background: var(--green-dim); color: var(--green); border: 1px solid #1a4d2e; }
.sentiment-pill.NEU { background: var(--bg-elevated); color: var(--text-faint); border: 1px solid var(--border-mid); }
.sentiment-pill.NEG { background: var(--red-dim); color: var(--red); border: 1px solid var(--red-border); }

/* ═══════════════════════════════
   CHAT
═══════════════════════════════ */
.chat-answer {
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 14px 16px;
    font-size: 13.5px;
    color: var(--text-secondary);
    line-height: 1.7;
    margin-top: 10px;
}

/* ═══════════════════════════════
   RECORDING
═══════════════════════════════ */
.rec-container {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    margin: 14px 0;
}
.rec-label {
    font-size: 9.5px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 12px;
}
.rec-status {
    display: flex; align-items: center; gap: 10px;
    background: var(--red-dim);
    border: 1px solid var(--red-border);
    border-radius: var(--radius-sm);
    padding: 10px 14px; margin-top: 10px;
}
.rec-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--red); flex-shrink: 0;
    animation: rec-pulse 1.4s ease-in-out infinite;
}
.rec-status-text { font-size: 12.5px; font-family: var(--font-mono); color: #ffaaaa; }
.rec-timer { font-size: 12.5px; font-family: var(--font-mono); color: var(--red); margin-left: auto; }

/* ═══════════════════════════════
   UPLOAD HINTS
═══════════════════════════════ */
.upload-hint {
    font-size: 10.5px;
    color: var(--text-ghost);
    font-family: var(--font-mono);
    margin-top: 4px;
    letter-spacing: 0.3px;
}

/* ═══════════════════════════════
   HOW IT WORKS CARD
═══════════════════════════════ */
.how-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
}
.how-card .how-label {
    font-size: 9.5px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 14px;
}
.how-step { display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; }
.how-step:last-child { margin-bottom: 0; }
.how-num {
    width: 20px; height: 20px; border-radius: 50%;
    background: var(--accent-dim); border: 1px solid var(--border-accent);
    font-size: 10px; font-family: var(--font-mono); color: var(--accent-light);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; margin-top: 1px;
}
.how-text { font-size: 12.5px; color: var(--text-muted); line-height: 1.55; }

/* ═══════════════════════════════
   MEETING LIST (old classes kept for compat)
═══════════════════════════════ */
.meeting-card {
    background: var(--bg-surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px 18px; margin-bottom: 8px;
    transition: border-color 0.15s;
}
.meeting-card:hover { border-color: var(--border-hover); }
.meeting-card-title { font-size: 13.5px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.meeting-card-meta { font-size: 10.5px; font-family: var(--font-mono); color: var(--text-faint); margin-bottom: 6px; }
.meeting-card-overview { font-size: 12.5px; color: var(--text-muted); line-height: 1.55;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.history-meta { font-size: 10.5px; font-family: var(--font-mono); color: var(--text-faint); margin-bottom: 12px; }

/* ═══════════════════════════════
   ANIMATION
═══════════════════════════════ */
@keyframes rec-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.3; transform: scale(1.5); }
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("page", "login"),
    ("result", None),
    ("error", None),
    ("filename", None),
    ("recording_error", None),
    ("recording_future", None),
    ("recording_processing_name", None),
    ("upload_future", None),
    ("chat_answer", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "recording_executor" not in st.session_state:
    st.session_state.recording_executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="MeetGenieProcessor"
    )

# ── Session restore on refresh ────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    restored = restore_session()
    if restored:
        st.session_state["logged_in"] = True
        st.session_state["user"] = restored
        st.session_state["google_token"] = restored["token"]
        if st.session_state.get("page", "login") == "login":
            st.session_state["page"] = "dashboard"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def clear_for_new_meeting() -> None:
    for key in [
        "result", "filename", "upload_future", "recording_future",
        "recording_processing_name", "chat_answer", "calendar_events",
        "error", "recording_error", "suggested_questions",
    ]:
        st.session_state[key] = None


def _process_recorded_audio(meeting_file):
    try:
        return process_video(meeting_file)
    finally:
        try:
            os.remove(meeting_file)
        except OSError:
            pass


def nav_bar(current_page):
    labels = {
        "dashboard": "Dashboard", "upload": "New Meeting",
        "results": "Summary", "history": "Meeting History",
        "calendar": "Calendar", "profile": "Profile", "settings": "Settings",
    }
    st.markdown(f"""
    <div class="nav-bar">
        <div class="nav-logo">Meet<span>Genie</span></div>
        <div class="nav-tag">{labels.get(current_page, '')}</div>
    </div>
    """, unsafe_allow_html=True)


def _nav_button(icon, label, target, current_page):
    """Render a sidebar nav item with a visible HTML label and a real Streamlit button."""
    active = "active" if current_page == target else ""
    st.markdown(
        f'<div class="sb-nav-item {active}">{icon}&nbsp;&nbsp;{label}</div>',
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown('<div class="sb-btn-wrap">', unsafe_allow_html=True)
        clicked = st.button(label, key=f"nav_{target}", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        st.session_state["page"] = target
        st.rerun()


def section_card(title, items, icon=""):
    if not items:
        content = '<p class="empty">None recorded</p>'
    else:
        lis = ""
        for item in items:
            if not item:
                continue
            if isinstance(item, dict):
                assignee = (item.get("assignee") or item.get("owner") or "").strip()
                task = item.get("task", "").strip()
                if assignee and task:
                    lis += f"<li><strong>{assignee}</strong> — {task}</li>"
                elif task:
                    lis += f"<li>{task}</li>"
                elif assignee:
                    lis += f"<li>{assignee}</li>"
            else:
                lis += f"<li>{item}</li>"
        content = f"<ul>{lis}</ul>" if lis else '<p class="empty">None recorded</p>'
    st.markdown(f"""
    <div class="section-card">
        <h4>{icon}&nbsp;{title}</h4>
        {content}
    </div>
    """, unsafe_allow_html=True)


def stat_badges(result):
    counts = [
        (len(result.get("discussion_points", [])), "Discussion"),
        (len(result.get("action_items", [])),       "Actions"),
        (len(result.get("decisions", [])),           "Decisions"),
        (len(result.get("risks", [])),               "Risks"),
        (len(result.get("questions", [])),           "Questions"),
        (len(result.get("follow_ups", [])),          "Follow-ups"),
    ]
    badges = "".join(
        f'<div class="stat-badge"><span class="stat-num">{n}</span><span class="stat-label">{lbl}</span></div>'
        for n, lbl in counts
    )
    st.markdown(f'<div class="stat-row">{badges}</div>', unsafe_allow_html=True)


def meta_pills(language, duration):
    lang_str = (language or "unknown").upper()
    dur_str = f"{round(duration / 60, 1)} min" if duration else "—"
    st.markdown(f"""
    <div class="meta-row">
        <span class="meta-pill">🌐 {lang_str}</span>
        <span class="meta-pill">⏱ {dur_str}</span>
    </div>
    """, unsafe_allow_html=True)


def sentiment_pill(label):
    cls = {"POSITIVE": "POS", "NEGATIVE": "NEG"}.get(label, "NEU")
    icon = {"POSITIVE": "↑", "NEGATIVE": "↓"}.get(label, "·")
    return f'<span class="sentiment-pill {cls}">{icon} {label}</span>'


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="sb-logo">Meet<span>Genie</span></div>', unsafe_allow_html=True)

        user = st.session_state.get("user", {})
        picture = user.get("picture", "")
        name = user.get("name", "User")
        email = user.get("email", "")

        if picture:
            st.markdown(f"""
            <div class="sb-user-block">
                <img class="sb-avatar" src="{picture}" />
                <div>
                    <div class="sb-user-name">{name}</div>
                    <div class="sb-user-email">{email}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="sb-user-block">
                <div style="width:36px;height:36px;border-radius:50%;background:var(--accent-dim);
                    display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">👤</div>
                <div>
                    <div class="sb-user-name">{name}</div>
                    <div class="sb-user-email">{email}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        page = st.session_state.get("page", "dashboard")

        st.markdown('<div class="sb-section-label">Main</div>', unsafe_allow_html=True)
        _nav_button("🏠", "Dashboard",       "dashboard", page)
        _nav_button("🎥", "New Meeting",     "upload",    page)
        _nav_button("📜", "Meeting History", "history",   page)
        _nav_button("📅", "Calendar",        "calendar",  page)

        st.markdown('<div class="sb-section-label">Account</div>', unsafe_allow_html=True)
        _nav_button("👤", "Profile",  "profile",  page)
        _nav_button("⚙", "Settings", "settings", page)

        if st.session_state.get("result"):
            st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
            _nav_button("✨", "Last Summary", "results", page)

        # Recording indicator
        if is_recording():
            elapsed = get_recording_duration()
            mins, secs = divmod(int(elapsed), 60)
            st.markdown(f"""
            <div class="sb-stat-block" style="border-color:var(--red-border);background:var(--red-dim);margin-top:12px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <div class="rec-dot"></div>
                    <span class="sb-stat-num" style="color:var(--red);">{mins:02d}:{secs:02d}</span>
                </div>
                <div class="sb-stat-label" style="color:#ffaaaa;">Recording active</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="flex:1"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        if st.button("🚪  Sign Out", key="logout_btn", use_container_width=True):
            sid = st.query_params.get("sid")
            if sid:
                delete_session(sid)
            clear_session_param()
            st.session_state.clear()
            st.rerun()

        st.markdown(
            '<div style="font-size:10px;color:var(--text-ghost);font-family:DM Mono,monospace;padding:12px 0 4px;">MeetGenie · Whisper + Gemini</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 0 — LOGIN
# ─────────────────────────────────────────────────────────────────────────────
def login_page():
    st.markdown("""
<style>
.login-container { display:flex; flex-direction:column; justify-content:center; align-items:center;
    text-align:center; margin-top:100px; margin-bottom:40px; }
.login-title { font-size:56px; font-weight:700; color:white; margin-bottom:20px; }
.login-subtitle { color:#9ca3af; font-size:22px; line-height:1.7; max-width:750px; }
</style>""", unsafe_allow_html=True)

    st.markdown("""
<div class="login-container">
<div class="login-title">Meet<span style="color:#4F7FFF;">Genie</span></div>
<div class="login-subtitle">AI-powered meeting summaries, action items and automatic
Google Calendar integration.<br>Sign in to continue.</div>
</div>""", unsafe_allow_html=True)

    left, center, right = st.columns([3, 2, 3])
    with center:
        user = google_login()

    if user:
        save_user(email=user["email"], name=user["name"], credentials=user["credentials"])
        db_user = get_user(user["email"])
        user["id"] = db_user[0]

        session_token = create_session_token()
        create_session(session_token, user["email"])

        # Set query param BEFORE touching session_state so Streamlit
        # writes it to the URL in this render pass. Calling st.rerun()
        # immediately after set_session_param() raises RerunException
        # which can unwind before the param is committed, causing the
        # ?sid= token to vanish on the very next load.
        # We set it here, then set session_state and let the natural
        # next render do the routing instead of forcing a rerun.
        set_session_param(session_token)

        st.session_state["logged_in"] = True
        st.session_state["user"] = user
        st.session_state["google_token"] = user["token"]
        st.session_state["page"] = "dashboard"
        # Do NOT call st.rerun() here — let the query param write complete.


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def dashboard_page():
    nav_bar("dashboard")

    user = st.session_state.get("user", {})
    user_id = user.get("id")
    name = user.get("name", "").split()[0] if user.get("name") else "there"

    st.markdown(f'<div class="page-title">Good day, {name} 👋</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Here\'s your meeting intelligence overview.</div>', unsafe_allow_html=True)

    # ── Stats row ─────────────────────────────────────────────────────────
    stats = get_dashboard_stats(user_id)
    all_meetings = get_all_meetings(user_id)

    total_actions = 0
    for m in all_meetings:
        try:
            parsed = json.loads(m[4] or "{}")
            total_actions += len(parsed.get("action_items", []))
        except Exception:
            pass

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"""
        <div class="dash-stat-card">
            <div class="dash-stat-num">{stats['meeting_count']}</div>
            <div class="dash-stat-label">Meetings Processed</div>
            <div class="dash-stat-sub">All time</div>
        </div>""", unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="dash-stat-card">
            <div class="dash-stat-num">{stats['hours_processed']}</div>
            <div class="dash-stat-label">Hours Processed</div>
            <div class="dash-stat-sub">Total audio duration</div>
        </div>""", unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="dash-stat-card">
            <div class="dash-stat-num">{total_actions}</div>
            <div class="dash-stat-label">Action Items</div>
            <div class="dash-stat-sub">Across all meetings</div>
        </div>""", unsafe_allow_html=True)

    # ── Main content: Recent Meetings + Upcoming Calendar ─────────────────
    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        st.markdown('<div class="dash-section-title">Recent Meetings</div>', unsafe_allow_html=True)
        recent = get_recent_meetings(user_id, limit=5)

        if not recent:
            st.markdown('<div style="color:var(--text-ghost);font-size:13px;padding:20px 0;">No meetings yet. Process your first meeting to see it here.</div>', unsafe_allow_html=True)
        else:
            for m in recent:
                mid, fname, created_at, overview, _ = m
                st.markdown(f"""
                <div class="dash-meeting-row">
                    <div style="flex:1;min-width:0;">
                        <div class="dash-meeting-name">{fname or "Untitled Meeting"}</div>
                        <div class="dash-meeting-date">{created_at}</div>
                        <div class="dash-meeting-preview">{overview or "No overview."}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

        if recent:
            st.markdown('<div class="gap-sm"></div>', unsafe_allow_html=True)
            if st.button("View all meetings →", key="dash_view_history"):
                st.session_state["page"] = "history"
                st.rerun()

    with right_col:
        st.markdown('<div class="dash-section-title">Upcoming Calendar Events</div>', unsafe_allow_html=True)
        token = st.session_state.get("google_token")
        if token:
            try:
                service = get_calendar_service(token)
                now = datetime.utcnow().isoformat() + "Z"
                upcoming_raw = (
                    service.events()
                    .list(
                        calendarId="primary",
                        timeMin=now,
                        maxResults=5,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                upcoming = upcoming_raw.get("items", [])
                if upcoming:
                    for ev in upcoming:
                        title = ev.get("summary", "Untitled")
                        start = ev.get("start", {})
                        start_str = start.get("dateTime") or start.get("date") or ""
                        try:
                            dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            display_time = dt.strftime("%b %d · %I:%M %p")
                        except Exception:
                            display_time = start_str
                        st.markdown(f"""
                        <div class="dash-cal-event">
                            <div class="dash-cal-title">{title}</div>
                            <div class="dash-cal-time">{display_time}</div>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.markdown('<div style="color:var(--text-ghost);font-size:13px;padding:20px 0;">No upcoming events.</div>', unsafe_allow_html=True)
            except Exception:
                st.markdown('<div style="color:var(--text-ghost);font-size:13px;">Could not load calendar events.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:var(--text-ghost);font-size:13px;">Sign in with Google to see calendar events.</div>', unsafe_allow_html=True)

    # ── Quick Actions ─────────────────────────────────────────────────────
    st.markdown('<div class="dash-section-title">Quick Actions</div>', unsafe_allow_html=True)
    qa1, qa2, qa3, qa4 = st.columns(4)

    with qa1:
        st.markdown("""
        <div class="dash-quick-action">
            <div class="dash-qa-icon">🎥</div>
            <div class="dash-qa-label">New Meeting</div>
            <div class="dash-qa-sub">Upload or record</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Start", key="qa_new", use_container_width=True):
            clear_for_new_meeting()
            st.session_state["page"] = "upload"
            st.rerun()

    with qa2:
        st.markdown("""
        <div class="dash-quick-action">
            <div class="dash-qa-icon">📜</div>
            <div class="dash-qa-label">Meeting History</div>
            <div class="dash-qa-sub">Browse past summaries</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Browse", key="qa_history", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()

    with qa3:
        st.markdown("""
        <div class="dash-quick-action">
            <div class="dash-qa-icon">📅</div>
            <div class="dash-qa-label">Calendar</div>
            <div class="dash-qa-sub">View & manage events</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="qa_calendar", use_container_width=True):
            st.session_state["page"] = "calendar"
            st.rerun()

    with qa4:
        st.markdown("""
        <div class="dash-quick-action">
            <div class="dash-qa-icon">✨</div>
            <div class="dash-qa-label">Last Summary</div>
            <div class="dash-qa-sub">Resume where you left off</div>
        </div>""", unsafe_allow_html=True)
        has_result = bool(st.session_state.get("result"))
        if st.button("View", key="qa_last", use_container_width=True, disabled=not has_result):
            st.session_state["page"] = "results"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 2 — NEW MEETING (upload)
# ─────────────────────────────────────────────────────────────────────────────
def upload_page():
    nav_bar("upload")

    col_main, col_side = st.columns([3, 1], gap="large")

    with col_main:
        st.markdown('<div class="page-title">New Meeting Summary</div>', unsafe_allow_html=True)
        st.markdown('<div class="page-subtitle">Upload a recording or transcript and get an AI-powered summary in seconds.</div>', unsafe_allow_html=True)

        meeting_name = st.text_input(
            "Meeting name",
            placeholder="e.g. Q3 Planning · June 2026",
            help="Give this meeting a name so you can find it in History later.",
        )

        st.markdown('<div class="gap"></div>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Drop your recording or transcript here",
            type=["mp3", "wav", "mp4", "txt"],
            help="MP3, WAV, MP4 for audio/video — TXT for raw transcripts",
        )
        st.markdown('<div class="upload-hint">MP3 · WAV · MP4 · TXT &nbsp;·&nbsp; Max 500 MB</div>', unsafe_allow_html=True)

        if uploaded_file:
            st.success(f"✓ **{uploaded_file.name}** ready to process")
            if meeting_name.strip():
                st.session_state.filename = meeting_name.strip()

        # ── Upload processing polling ──────────────────────────────────────
        upload_future = st.session_state.get("upload_future")
        if upload_future is not None:
            if upload_future.done():
                try:
                    st.session_state.result = upload_future.result()
                    st.session_state.page = "results"
                except Exception as exc:
                    st.session_state.error = str(exc)
                finally:
                    st.session_state.upload_future = None
                st.rerun()
            else:
                st.info("⏳ Transcribing and summarising — this may take a minute…")
                time.sleep(1)
                st.rerun()

        st.markdown('<div class="gap"></div>', unsafe_allow_html=True)

        if st.button("Generate Summary →", type="primary", width="stretch"):
            if not uploaded_file:
                st.warning("Please upload a file first.")
            elif not meeting_name.strip():
                st.warning("Please enter a meeting name.")
            else:
                try:
                    ext = uploaded_file.name.rsplit(".", 1)[-1]
                    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
                        temp_path = f.name
                        f.write(uploaded_file.read())

                    st.session_state.filename = meeting_name.strip()
                    st.session_state.chat_answer = None
                    st.session_state.pop("calendar_events", None)
                    st.session_state.pop("suggested_questions", None)

                    def _process_upload(path):
                        try:
                            return process_video(path)
                        finally:
                            try:
                                os.remove(path)
                            except OSError:
                                pass

                    st.session_state.upload_future = (
                        st.session_state.recording_executor.submit(_process_upload, temp_path)
                    )
                except Exception as exc:
                    st.session_state.error = str(exc)
                st.rerun()

        if st.session_state.error:
            st.error(f"⚠ {st.session_state.error}")
            st.session_state.error = None

        # ── Recording section ──────────────────────────────────────────────
        currently_recording = is_recording()

        st.markdown('<div class="rec-container">', unsafe_allow_html=True)
        st.markdown('<div class="rec-label">🎙 Live Recording</div>', unsafe_allow_html=True)

        if st.session_state.recording_error:
            st.error(f"Recording failed: {st.session_state.recording_error}")
            st.session_state.recording_error = None

        recording_future = st.session_state.recording_future
        if recording_future is not None:
            if recording_future.done():
                try:
                    st.session_state.result = recording_future.result()
                    st.session_state.filename = st.session_state.recording_processing_name or meeting_name.strip()
                    st.session_state.chat_answer = None
                    st.session_state.pop("calendar_events", None)
                    st.session_state.pop("suggested_questions", None)
                    st.session_state.page = "results"
                except Exception as exc:
                    st.session_state.recording_error = str(exc)
                finally:
                    st.session_state.recording_future = None
                    st.session_state.recording_processing_name = None
                    st.session_state.recording = False
                st.rerun()
            else:
                st.info("Transcribing and summarising the recording...")
                time.sleep(1)
                st.rerun()

        if not currently_recording:
            if st.button("▶  Start Recording", width="stretch"):
                if not meeting_name.strip():
                    st.warning("Enter a meeting name before recording.")
                else:
                    try:
                        start_recording()
                        st.session_state.recording = True
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not start recording: {exc}")
        else:
            if st.button("⏹  Stop & Summarise", type="primary", width="stretch"):
                try:
                    with st.spinner("Saving audio…"):
                        meeting_file = stop_recording()
                    st.session_state.recording = False
                    st.session_state.recording_processing_name = meeting_name.strip()
                    st.session_state.recording_future = (
                        st.session_state.recording_executor.submit(_process_recorded_audio, meeting_file)
                    )
                except Exception as exc:
                    st.session_state.recording = False
                    st.session_state.recording_error = str(exc)
                st.rerun()

            elapsed = get_recording_duration()
            mins, secs = divmod(int(elapsed), 60)
            st.markdown(f"""
            <div class="rec-status">
                <div class="rec-dot"></div>
                <span class="rec-status-text">Recording in progress</span>
                <span class="rec-timer">{mins:02d}:{secs:02d}</span>
            </div>""", unsafe_allow_html=True)
            time.sleep(1)
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_side:
        st.markdown('<div class="gap-lg"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="how-card">
            <div class="how-label">How it works</div>
            <div class="how-step"><div class="how-num">1</div><div class="how-text">Sign in with Google for Calendar integration</div></div>
            <div class="how-step"><div class="how-num">2</div><div class="how-text">Upload a recording (MP3/WAV/MP4) or transcript</div></div>
            <div class="how-step"><div class="how-num">3</div><div class="how-text">Whisper transcribes with speaker detection</div></div>
            <div class="how-step"><div class="how-num">4</div><div class="how-text">Gemini extracts insights, actions, risks and decisions</div></div>
            <div class="how-step"><div class="how-num">5</div><div class="how-text">Add events to Google Calendar in one click</div></div>
            <div class="how-step"><div class="how-num">6</div><div class="how-text">Download PDF, email your team, or save to History</div></div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 3 — RESULTS (summary)
# ─────────────────────────────────────────────────────────────────────────────
def results_page():
    nav_bar("results")

    result = st.session_state.result

    if "calendar_events" not in st.session_state:
        transcript = result.get("transcript", "") if result else ""
        if transcript.strip():
            try:
                st.session_state.calendar_events = extract_calendar_events(transcript)
            except Exception:
                st.session_state.calendar_events = []

    if not result:
        st.error("No summary found. Please process a meeting first.")
        if st.button("← New Meeting", key="results_back"):
            st.session_state["page"] = "upload"
            st.rerun()
        return

    name = st.session_state.filename or "Meeting Summary"
    st.markdown(f'<div class="page-title">{name}</div>', unsafe_allow_html=True)

    meta_pills(result.get("language"), result.get("duration", 0))
    stat_badges(result)

    overview = result.get("overview", "").strip()
    st.markdown(f"""
    <div class="overview-card">
        <div class="ov-label">📄 &nbsp;Meeting Overview</div>
        <p>{overview or '<span style="color:var(--text-ghost);font-style:italic;">No overview generated.</span>'}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Action bar ────────────────────────────────────────────────────────
    act_col1, act_col2, act_col3, act_col4 = st.columns([1, 1, 1, 3])
    with act_col1:
        if st.button("＋  New Meeting", width="stretch", key="new_meeting_btn"):
            clear_for_new_meeting()
            st.session_state["page"] = "upload"
            st.rerun()
    with act_col2:
        if st.button("💾  Save", width="stretch", key="save_history_btn"):
            if overview:
                save_meeting(st.session_state.user["id"], st.session_state.filename, result)
                st.success("Saved.")
            else:
                st.error("Cannot save — no overview generated.")
    with act_col3:
        pdf_bytes = generate_summary_pdf(result, name)
        st.download_button(
            "⬇  PDF",
            data=pdf_bytes,
            file_name=f"{name.replace(' ', '_')}_summary.pdf",
            mime="application/pdf",
            key="download_pdf_results",
            width="stretch",
        )
    with act_col4:
        email_inner_col, email_btn_col = st.columns([4, 1])
        with email_inner_col:
            email = st.text_input("Recipient email", placeholder="Email summary to…", key="results_email", label_visibility="collapsed")
        with email_btn_col:
            if st.button("Send →", width="stretch", key="send_email_btn"):
                if not email:
                    st.warning("Enter a recipient email.")
                else:
                    try:
                        send_summary_email(email, result)
                        st.success(f"Sent to {email}")
                    except Exception as exc:
                        st.error(f"Email failed: {exc}")

    # ── Summary sections ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">Summary</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        section_card("Key Discussion Points", result.get("discussion_points", []), "🔑")
        section_card("Decisions",             result.get("decisions", []),          "📌")
    with c2:
        section_card("Action Items",          result.get("action_items", []),       "✅")
        section_card("Task Assignments",      result.get("task_assignments", []),   "👥")
    with c3:
        section_card("Next Steps",            result.get("next_steps", []),         "➡️")
        section_card("Risks & Blockers",      result.get("risks", []),              "⚠️")
    c4, c5 = st.columns(2)
    with c4:
        section_card("Open Questions", result.get("questions", []),  "❓")
    with c5:
        section_card("Follow Ups",     result.get("follow_ups", []), "🔄")

    # ── Speaker analytics ─────────────────────────────────────────────────
    segments = result.get("segments", [])
    speaker_sentiments: dict = defaultdict(list)
    for seg in segments:
        speaker_sentiments[seg.get("speaker", "Unknown")].append(seg.get("sentiment", "NEUTRAL"))
    speaker_summary = {spk: get_dominant_sentiment(sents) for spk, sents in speaker_sentiments.items()}

    if segments:
        st.markdown('<div class="section-header">Analytics</div>', unsafe_allow_html=True)
        stats_tt = result.get("talk_time") or calculate_talk_time(segments)
        participation = result.get("participation") or calculate_participation(stats_tt)

        ana_col, chart_col = st.columns([1, 1])
        with ana_col:
            rows = ""
            for spk, pct in participation.items():
                talk_s = round(stats_tt[spk], 1)
                dom = speaker_summary.get(spk, "NEUTRAL")
                pill = sentiment_pill(dom)
                rows += (
                    f'<div class="speaker-row">'
                    f'<div><div class="speaker-name">{spk}</div>'
                    f'<div class="speaker-meta">{pct}% &nbsp;&middot;&nbsp; {talk_s}s</div></div>'
                    f'{pill}</div>'
                )
            st.html(f'<div class="analytics-card"><div class="ac-header">Speaker Breakdown</div>{rows}</div>')

        with chart_col:
            if participation:
                fig = px.pie(
                    values=list(participation.values()),
                    names=list(participation.keys()),
                    hole=0.45,
                    color_discrete_sequence=["#4f7cff", "#ff4b4b", "#22c55e", "#f59e0b", "#a855f7"],
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans, sans-serif", color="#b8bdd0", size=12),
                    margin=dict(l=0, r=0, t=20, b=0),
                    legend=dict(font=dict(color="#b8bdd0"), bgcolor="rgba(0,0,0,0)"),
                )
                fig.update_traces(textfont_color="#eceef5", textfont_size=12)
                st.plotly_chart(fig, width="stretch")

    # ── Transcript ────────────────────────────────────────────────────────
    with st.expander("📝  Full Transcript", expanded=False):
        if segments:
            html_segs = ""
            for seg in segments:
                s, e = int(seg["start"]), int(seg["end"])
                ts  = f"{s//60:02d}:{s%60:02d} – {e//60:02d}:{e%60:02d}"
                spk = seg.get("speaker", "Unknown")
                txt = seg.get("text", "").strip()
                sent = seg.get("sentiment", "NEUTRAL")
                scr  = seg.get("sentiment_score", 0)
                cls  = {"POSITIVE": "POS", "NEGATIVE": "NEG"}.get(sent, "NEU")
                html_segs += f"""
                <div class="seg-block">
                    <div class="seg-header"><span class="seg-speaker">{spk}</span><span class="seg-time">{ts}</span></div>
                    <p class="seg-text">{txt}</p>
                    <div class="seg-sentiment {cls}">{sent} {scr:.2f}</div>
                </div>"""
            st.markdown(html_segs, unsafe_allow_html=True)
        else:
            st.text_area("", result.get("transcript", ""), height=300, label_visibility="collapsed")

    # ── Suggested questions + Chat ─────────────────────────────────────────
    if "suggested_questions" not in st.session_state:
        st.session_state.suggested_questions = generate_questions(result.get("transcript", ""))

    st.markdown('<div class="section-header">Chat With This Meeting</div>', unsafe_allow_html=True)

    question = st.text_input(
        "Ask a question",
        placeholder="💬 Ask anything about this meeting",
        key="chat_question",
        label_visibility="collapsed",
    )

    st.caption("Suggested Questions")
    sq = st.session_state.suggested_questions or []
    if sq:
        cols = st.columns(min(3, len(sq)))
        for i, q in enumerate(sq):
            with cols[i % len(cols)]:
                if st.button(q, key=f"suggested_q_{i}", use_container_width=True):
                    question = q

    if question:
        meeting_context = f"""Speaker Count: {result.get('speaker_count','Unknown')}
Top Speaker: {result.get('top_speaker','Unknown')}
Participation: {result.get('participation','')}
Talk Time: {result.get('talk_time','')}
Speaker Sentiment: {result.get('speaker_sentiment','')}
Transcript: {result.get('transcript','')}"""
        with st.spinner("Thinking…"):
            answer = ask_meeting_question(meeting_context, question)
            st.session_state.chat_answer = answer

    if st.session_state.chat_answer:
        st.markdown(f'<div class="chat-answer">{st.session_state.chat_answer}</div>', unsafe_allow_html=True)

    # ── Calendar events detected in this meeting ──────────────────────────
    events = st.session_state.get("calendar_events", [])
    if events:
        st.markdown('<div class="section-header">📅 Detected Calendar Events</div>', unsafe_allow_html=True)
        token = st.session_state.get("google_token")

        reminder_options = {
            "No reminder": 0, "5 minutes before": 5, "10 minutes before": 10,
            "15 minutes before": 15, "30 minutes before": 30, "45 minutes before": 45,
            "1 hour before": 60, "2 hours before": 120, "1 day before": 1440,
        }

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Select All", key="res_sel_all"):
                for i in range(len(events)):
                    st.session_state[f"res_event_enable_{i}"] = True
                st.rerun()
        with col2:
            if st.button("❌ Deselect All", key="res_desel_all"):
                for i in range(len(events)):
                    st.session_state[f"res_event_enable_{i}"] = False
                st.rerun()

        edited_events = []
        for i, event in enumerate(events):
            with st.container(border=True):
                st.markdown(f"**📅 {event['title']}**")
                enabled = st.checkbox("Add this event", value=True, key=f"res_event_enable_{i}")
                title = st.text_input("Title", value=event["title"], key=f"res_title_{i}")
                col1, col2 = st.columns(2)
                with col1:
                    from datetime import date as _date
                    date = st.date_input("Date", value=datetime.strptime(event["date"], "%Y-%m-%d").date(), key=f"res_date_{i}")
                with col2:
                    t = st.time_input("Time", value=datetime.strptime(event["time"], "%H:%M").time(), key=f"res_time_{i}")
                col3, col4 = st.columns(2)
                with col3:
                    duration = st.number_input("Duration (minutes)", min_value=15, max_value=480,
                                               value=event.get("duration_minutes", 60), step=15, key=f"res_duration_{i}")
                with col4:
                    reminder_label = st.selectbox(
                        "Reminder", list(reminder_options.keys()),
                        index=list(reminder_options.values()).index(event.get("reminder_minutes", 30))
                        if event.get("reminder_minutes", 30) in reminder_options.values() else 4,
                        key=f"res_reminder_{i}",
                    )
                    reminder = reminder_options[reminder_label]
                description = st.text_area("Description", value=event.get("description", ""), key=f"res_description_{i}")
                if enabled:
                    edited_events.append({
                        "title": title, "date": date.strftime("%Y-%m-%d"),
                        "time": t.strftime("%H:%M"), "duration_minutes": duration,
                        "description": description, "reminder_minutes": reminder,
                    })

        if st.button("📅 Add Selected Events to Google Calendar", type="primary",
                     use_container_width=True, key="res_add_cal"):
            if not edited_events:
                st.warning("Please select at least one event.")
            elif not token:
                st.error("Please sign in with Google.")
            else:
                try:
                    created = create_calendar_events(edited_events, token)
                    st.success(f"🎉 Added {len(created)} event(s) to your Google Calendar!")
                    st.balloons()
                except Exception as e:
                    st.error(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 4 — MEETING HISTORY
# ─────────────────────────────────────────────────────────────────────────────
def history_page():
    nav_bar("history")

    st.markdown('<div class="page-title">Meeting History</div>', unsafe_allow_html=True)

    uid = st.session_state.user["id"]

    # ── Search ────────────────────────────────────────────────────────────
    search_col, count_col = st.columns([4, 1])
    with search_col:
        search_query = st.text_input(
            "Search meetings",
            placeholder="🔍  Search by name, keyword, or content…",
            key="history_search",
            label_visibility="collapsed",
        )

    meetings = search_meetings(uid, search_query) if search_query.strip() else get_all_meetings(uid)
    total    = len(get_all_meetings(uid)) if search_query.strip() else len(meetings)

    with count_col:
        st.markdown(
            f'<div style="padding:10px 0;text-align:right;font-size:12px;font-family:var(--font-mono);color:var(--text-faint);">'
            f'{len(meetings)} / {total}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="gap-sm"></div>', unsafe_allow_html=True)

    # ── Empty state ───────────────────────────────────────────────────────
    if not meetings:
        if search_query:
            st.markdown(f"""
            <div class="history-empty">
                <div class="history-empty-icon">🔍</div>
                <div class="history-empty-title">No results for "{search_query}"</div>
                <div class="history-empty-sub">Try a different keyword, or clear the search to see all meetings.</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="history-empty">
                <div class="history-empty-icon">🎙️</div>
                <div class="history-empty-title">No meetings saved yet</div>
                <div class="history-empty-sub">Process your first meeting and click <strong>Save to History</strong> to see it here.</div>
            </div>""", unsafe_allow_html=True)
            if st.button("＋  Process a Meeting", type="primary", key="history_empty_cta"):
                st.session_state["page"] = "upload"
                st.rerun()
        return

    # ── Meeting cards ─────────────────────────────────────────────────────
    for meeting in meetings:
        meeting_id, filename, created_at, overview, summary_json = meeting

        # Parse summary for chip counts
        try:
            parsed = json.loads(summary_json or "{}")
        except (json.JSONDecodeError, TypeError):
            parsed = {}

        action_count   = len(parsed.get("action_items", []))
        decision_count = len(parsed.get("decisions", []))
        duration_s     = parsed.get("duration", 0)
        lang           = (parsed.get("language") or "").upper()
        duration_label = f"{round(duration_s / 60, 1)} min" if duration_s else ""

        # Format date
        try:
            dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            date_label = dt.strftime("%b %d, %Y · %I:%M %p")
        except Exception:
            date_label = str(created_at)[:16] if created_at else ""

        # Build chips HTML
        chips = ""
        if action_count:
            chips += f'<span class="hcard-chip accent">✅ {action_count} action{"s" if action_count != 1 else ""}</span>'
        if decision_count:
            chips += f'<span class="hcard-chip">📌 {decision_count} decision{"s" if decision_count != 1 else ""}</span>'
        if duration_label:
            chips += f'<span class="hcard-chip">⏱ {duration_label}</span>'
        if lang:
            chips += f'<span class="hcard-chip">🌐 {lang}</span>'

        st.markdown(f"""
        <div class="hcard">
            <div class="hcard-header">
                <div class="hcard-top">
                    <div class="hcard-title">{filename or "Untitled Meeting"}</div>
                    <div class="hcard-date">{date_label}</div>
                </div>
                <div class="hcard-overview">{overview or "No overview available."}</div>
                {'<div class="hcard-chips">' + chips + '</div>' if chips else ""}
            </div>
        </div>""", unsafe_allow_html=True)

        # ── Action buttons ─────────────────────────────────────────────────
        btn_col1, btn_col2, btn_col3 = st.columns([3, 2, 7])

        with btn_col1:
            if st.button("Open →", key=f"open_{meeting_id}", use_container_width=True, type="primary"):
                # Load this meeting into session state and navigate to results
                st.session_state["result"]   = parsed
                st.session_state["filename"] = filename or "Untitled Meeting"
                st.session_state["chat_answer"] = None
                st.session_state.pop("suggested_questions", None)
                st.session_state.pop("calendar_events", None)
                st.session_state["page"] = "results"
                st.rerun()

        with btn_col2:
            if st.button("Delete", key=f"del_{meeting_id}", use_container_width=True):
                delete_meeting(meeting_id, uid)
                st.rerun()

        with btn_col3:
            # Expand full summary inline
            with st.expander("View full summary"):
                ov_text = parsed.get("overview", "")
                if ov_text:
                    st.markdown(f"""
                    <div class="overview-card" style="margin-bottom:16px;">
                        <div class="ov-label">📄 Overview</div>
                        <p>{ov_text}</p>
                    </div>""", unsafe_allow_html=True)

                hc1, hc2, hc3 = st.columns(3)
                with hc1:
                    section_card("Discussion Points", parsed.get("discussion_points", []), "🔑")
                    section_card("Decisions",         parsed.get("decisions", []),          "📌")
                with hc2:
                    section_card("Action Items",      parsed.get("action_items", []),       "✅")
                    section_card("Task Assignments",  parsed.get("task_assignments", []),   "👥")
                with hc3:
                    section_card("Next Steps",        parsed.get("next_steps", []),         "➡️")
                    section_card("Risks",             parsed.get("risks", []),              "⚠️")

                hd1, hd2 = st.columns(2)
                with hd1:
                    section_card("Questions",  parsed.get("questions", []),  "❓")
                with hd2:
                    section_card("Follow Ups", parsed.get("follow_ups", []), "🔄")

                pdf_bytes = generate_summary_pdf(parsed, filename or "Meeting Summary")
                st.download_button(
                    "⬇  Download PDF",
                    data=pdf_bytes,
                    file_name=f"{(filename or 'meeting').replace(' ', '_')}_summary.pdf",
                    mime="application/pdf",
                    key=f"pdf_{meeting_id}",
                )

        st.markdown('<div class="gap-sm"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 5 — CALENDAR
# ─────────────────────────────────────────────────────────────────────────────
def calendar_page():
    nav_bar("calendar")

    st.markdown('<div class="page-title">Calendar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">View upcoming events and add meeting events to Google Calendar.</div>', unsafe_allow_html=True)

    token = st.session_state.get("google_token")

    # ── Upcoming events ───────────────────────────────────────────────────
    st.markdown('<div class="section-header">Upcoming Events</div>', unsafe_allow_html=True)

    if token:
        try:
            service = get_calendar_service(token)
            now = datetime.utcnow().isoformat() + "Z"
            result = service.events().list(
                calendarId="primary", timeMin=now,
                maxResults=10, singleEvents=True, orderBy="startTime",
            ).execute()
            events = result.get("items", [])
            if events:
                for ev in events:
                    title = ev.get("summary", "Untitled")
                    start = ev.get("start", {})
                    start_str = start.get("dateTime") or start.get("date") or ""
                    location = ev.get("location", "")
                    description = ev.get("description", "")
                    try:
                        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        display_time = dt.strftime("%A, %B %d · %I:%M %p")
                    except Exception:
                        display_time = start_str
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{title}**")
                            st.caption(display_time)
                            if location:
                                st.caption(f"📍 {location}")
                            if description:
                                st.caption(description[:120] + ("…" if len(description) > 120 else ""))
            else:
                st.info("No upcoming events in your Google Calendar.")
        except Exception as e:
            st.error(f"Could not load calendar: {e}")
    else:
        st.warning("Sign in with Google to view your calendar.")

    # ── Events from last meeting ──────────────────────────────────────────
    events = st.session_state.get("calendar_events", [])
    if events:
        st.markdown('<div class="section-header">Events Detected in Last Meeting</div>', unsafe_allow_html=True)

        reminder_options = {
            "No reminder": 0, "5 minutes before": 5, "10 minutes before": 10,
            "15 minutes before": 15, "30 minutes before": 30, "45 minutes before": 45,
            "1 hour before": 60, "2 hours before": 120, "1 day before": 1440,
        }

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Select All"):
                for i in range(len(events)):
                    st.session_state[f"event_enable_{i}"] = True
                st.rerun()
        with col2:
            if st.button("❌ Deselect All"):
                for i in range(len(events)):
                    st.session_state[f"event_enable_{i}"] = False
                st.rerun()

        edited_events = []
        for i, event in enumerate(events):
            with st.container(border=True):
                st.markdown(f"## 📅 {event['title']}")
                enabled = st.checkbox("Add this event", value=True, key=f"event_enable_{i}")
                title = st.text_input("Title", value=event["title"], key=f"title_{i}")
                col1, col2 = st.columns(2)
                with col1:
                    date = st.date_input("Date", value=datetime.strptime(event["date"], "%Y-%m-%d").date(), key=f"date_{i}")
                with col2:
                    t = st.time_input("Time", value=datetime.strptime(event["time"], "%H:%M").time(), key=f"time_{i}")
                col3, col4 = st.columns(2)
                with col3:
                    duration = st.number_input("Duration (minutes)", min_value=15, max_value=480, value=event.get("duration_minutes", 60), step=15, key=f"duration_{i}")
                with col4:
                    reminder_label = st.selectbox(
                        "Reminder", list(reminder_options.keys()),
                        index=list(reminder_options.values()).index(event.get("reminder_minutes", 30))
                        if event.get("reminder_minutes", 30) in reminder_options.values() else 4,
                        key=f"reminder_{i}",
                    )
                    reminder = reminder_options[reminder_label]
                description = st.text_area("Description", value=event.get("description", ""), key=f"description_{i}")
                if enabled:
                    edited_events.append({
                        "title": title, "date": date.strftime("%Y-%m-%d"),
                        "time": t.strftime("%H:%M"), "duration_minutes": duration,
                        "description": description, "reminder_minutes": reminder,
                    })

        if st.button("📅 Add Selected Events to Google Calendar", type="primary", use_container_width=True):
            if not edited_events:
                st.warning("Please select at least one event.")
            elif not token:
                st.error("Please sign in with Google.")
            else:
                try:
                    created = create_calendar_events(edited_events, token)
                    st.success(f"🎉 Added {len(created)} event(s) to your Google Calendar!")
                    st.balloons()
                except Exception as e:
                    st.error(str(e))
    else:
        st.markdown('<div class="section-header">Events Detected in Last Meeting</div>', unsafe_allow_html=True)
        st.info("Process a meeting to detect calendar events automatically.")


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 6 — PROFILE
# ─────────────────────────────────────────────────────────────────────────────
def profile_page():
    nav_bar("profile")

    user = st.session_state.get("user", {})
    picture = user.get("picture", "")
    name    = user.get("name", "User")
    email   = user.get("email", "")
    uid     = user.get("id")

    # Fetch created_at from DB (index 4 after the get_user update)
    member_since = ""
    db_user = get_user(email)
    if db_user and len(db_user) >= 5 and db_user[4]:
        raw_ts = str(db_user[4])
        try:
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            member_since = dt.strftime("%B %d, %Y")
        except Exception:
            member_since = raw_ts[:10]

    stats = get_dashboard_stats(uid) if uid else {"meeting_count": 0, "hours_processed": 0}

    # ── Hero block ────────────────────────────────────────────────────────
    if picture:
        avatar_html = f'<img class="profile-avatar" src="{picture}" />'
    else:
        avatar_html = '<div class="profile-avatar-fallback">👤</div>'

    st.markdown(f"""
    <div class="profile-hero">
        <div class="profile-avatar-wrap">{avatar_html}</div>
        <div class="profile-info">
            <div class="profile-name">{name}</div>
            <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
                <span class="profile-email-pill">✉ {email}</span>
                <span class="profile-google-badge">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    Google Account
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Stat cards ────────────────────────────────────────────────────────
    st.markdown('<div class="profile-stat-row">', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"""
        <div class="profile-stat-card">
            <div class="profile-stat-num">{stats['meeting_count']}</div>
            <div class="profile-stat-label">Meetings Processed</div>
        </div>""", unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="profile-stat-card">
            <div class="profile-stat-num">{stats['hours_processed']}</div>
            <div class="profile-stat-label">Hours Processed</div>
        </div>""", unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="profile-stat-card">
            <div class="profile-stat-num">{member_since or "—"}</div>
            <div class="profile-stat-label">Member Since</div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Account details grid ──────────────────────────────────────────────
    st.markdown('<div class="section-header">Account Details</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="profile-detail-grid">
        <div class="profile-detail-row">
            <div class="profile-detail-label">Full Name</div>
            <div class="profile-detail-value">{name}</div>
        </div>
        <div class="profile-detail-row">
            <div class="profile-detail-label">Email Address</div>
            <div class="profile-detail-value mono">{email}</div>
        </div>
        <div class="profile-detail-row">
            <div class="profile-detail-label">Connected Account</div>
            <div class="profile-detail-value">
                <span class="profile-connected-badge">✓ Google · {email}</span>
            </div>
        </div>
        <div class="profile-detail-row">
            <div class="profile-detail-label">Google Calendar</div>
            <div class="profile-detail-value">
                <span class="profile-connected-badge">✓ Connected</span>
            </div>
        </div>
        <div class="profile-detail-row">
            <div class="profile-detail-label">Account Created</div>
            <div class="profile-detail-value">{member_since or "—"}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sign-out zone ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Session</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="profile-logout-zone">
        <div>
            <div class="profile-logout-text">Sign out of MeetGenie</div>
            <div class="profile-logout-sub">You will need to sign in with Google again to access your meetings.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="gap-sm"></div>', unsafe_allow_html=True)
    if st.button("🚪  Sign Out", key="profile_logout", type="primary"):
        sid = st.query_params.get("sid")
        if sid:
            delete_session(sid)
        clear_session_param()
        st.session_state.clear()
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 7 — SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
def settings_page():
    nav_bar("settings")

    st.markdown('<div class="page-title">Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Configure MeetGenie to fit your workflow.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">AI Model</div>', unsafe_allow_html=True)
    model = st.selectbox(
        "Gemini model",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0,
        key="settings_model",
        help="gemini-2.5-flash gives the best summaries. Switch to a lower model if you hit quota limits.",
    )
    if st.button("Save Model Setting", key="save_model"):
        st.session_state["gemini_model_override"] = model
        st.success(f"Model set to {model}. Restart the app to apply.")

    st.markdown('<div class="section-header">Transcription</div>', unsafe_allow_html=True)
    whisper_model = st.selectbox(
        "Whisper model",
        ["tiny", "base", "small"],
        index=0,
        key="settings_whisper",
        help="tiny uses least RAM (~150 MB). small gives better accuracy (~460 MB).",
    )
    if st.button("Save Whisper Setting", key="save_whisper"):
        st.session_state["whisper_model_override"] = whisper_model
        st.success(f"Whisper model set to {whisper_model}. Restart to apply.")

    st.markdown('<div class="section-header">Notifications</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="settings-row">
        <div>
            <div class="settings-label">Email reminders</div>
            <div class="settings-sub">Receive a summary email after each meeting is processed</div>
        </div>
    </div>""", unsafe_allow_html=True)
    st.toggle("Enable email reminders", value=False, key="settings_email_reminder", disabled=True)
    st.caption("Coming soon")

    st.markdown('<div class="section-header">Data</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="settings-row">
        <div>
            <div class="settings-label">Meeting database</div>
            <div class="settings-sub">All meetings are stored locally in meetings.db</div>
        </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("⚠️  Danger Zone"):
        st.warning("Deleting all meetings cannot be undone.")
        if st.button("Delete all my meetings", key="delete_all_meetings"):
            uid = st.session_state.user.get("id")
            if uid:
                all_m = get_all_meetings(uid)
                for m in all_m:
                    delete_meeting(m[0], uid)
                st.success(f"Deleted {len(all_m)} meetings.")
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTER
# ─────────────────────────────────────────────────────────────────────────────
pages = {
    "login":     login_page,
    "dashboard": dashboard_page,
    "upload":    upload_page,
    "results":   results_page,
    "history":   history_page,
    "calendar":  calendar_page,
    "profile":   profile_page,
    "settings":  settings_page,
}

if st.session_state.get("logged_in", False):
    render_sidebar()

pages.get(st.session_state.get("page", "login"), login_page)()
