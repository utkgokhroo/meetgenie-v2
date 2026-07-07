import streamlit as st
import json
import os
import tempfile
import time
from datetime import datetime
from services.google_auth import google_login
from services.database import save_user, get_user
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import plotly.express as px
from core.sentiment import get_dominant_sentiment
from core.processor import process_video
from core.chat_with_meeting import ask_meeting_question
from services.database import init_db, save_meeting, delete_meeting, get_all_meetings, search_meetings
from services.email_sender import send_summary_email
from services.pdf_exporter import generate_summary_pdf
from core.speaker_intelligence import calculate_talk_time, calculate_participation, get_top_speaker
from recording.recording_manager import start_recording, stop_recording, get_recording_duration, is_recording
from services.calendar_extractor import extract_calendar_events
from services.calendar_service import create_calendar_events

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

/* ── Design tokens ─────────────────────────────────────────────────────── */
:root {
    --bg-base:        #0d0f18;
    --bg-surface:     #131520;
    --bg-surface-2:   #181b2a;
    --bg-elevated:    #1e2235;
    --bg-overlay:     #141c38;
    --border:         #1e2235;
    --border-mid:     #252a3d;
    --border-strong:  #2e3450;
    --border-accent:  #2a3260;
    --border-hover:   #3a4880;
    --red:            #ff4b4b;
    --red-dim:        #3d1515;
    --red-border:     #5c2020;
    --accent:         #4f7cff;
    --accent-dim:     #1a2550;
    --accent-light:   #7c9fff;
    --green:          #22c55e;
    --green-dim:      #0d2d1a;
    --amber:          #f59e0b;
    --amber-dim:      #2d1f05;
    --text-primary:   #eceef5;
    --text-secondary: #b8bdd0;
    --text-muted:     #6e7590;
    --text-faint:     #4a5070;
    --text-ghost:     #30364d;
    --font-body:      'DM Sans', sans-serif;
    --font-mono:      'DM Mono', monospace;
    --radius-sm:      6px;
    --radius:         10px;
    --radius-lg:      14px;
}

/* ── Global reset ───────────────────────────────────────────────────────── */
html, body { font-family: var(--font-body) !important; background: var(--bg-base) !important; color: var(--text-primary) !important; }
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

/* ── Typography ─────────────────────────────────────────────────────────── */
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
    font-size: 13px !important;
    font-weight: 500 !important;
    font-family: var(--font-body) !important;
    letter-spacing: 0.01em !important;
}
hr { border-color: var(--border) !important; }

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebarContent"] * { color: var(--text-primary) !important; }
[data-testid="stSidebarNav"] { display: none; }

/* ── Text input ─────────────────────────────────────────────────────────── */
[data-testid="stTextInput"],
[data-testid="stTextInputRootElement"] { background-color: transparent !important; }
[data-testid="stTextInput"] input,
[data-testid="stTextInputRootElement"] input {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    caret-color: var(--accent) !important;
    padding: 10px 14px !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder { color: var(--text-ghost) !important; }
[data-testid="stTextInput"] input:focus,
[data-testid="stTextInputRootElement"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-dim) !important;
    outline: none !important;
}

/* ── File uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] { background-color: transparent !important; }
[data-testid="stFileUploaderDropzone"] {
    background-color: var(--bg-surface) !important;
    border: 1px dashed var(--border-mid) !important;
    border-radius: var(--radius) !important;
    transition: border-color 0.2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; }
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] small { color: var(--text-muted) !important; }
[data-testid="stFileChip"] { background-color: var(--bg-elevated) !important; border-color: var(--border-mid) !important; }
[data-testid="stFileChipName"] { color: var(--text-secondary) !important; }

/* ── Buttons ────────────────────────────────────────────────────────────── */
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    transition: all 0.15s ease !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]),
[data-testid="stDownloadButton"] button[kind="secondary"],
[data-testid="stDownloadButton"] button:not([kind="primary"]) {
    background-color: var(--bg-elevated) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-secondary) !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]):hover,
[data-testid="stDownloadButton"] button:not([kind="primary"]):hover {
    background-color: var(--bg-surface-2) !important;
    border-color: var(--accent) !important;
    color: var(--text-primary) !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background-color: var(--red) !important;
    border-color: var(--red) !important;
    color: #fff !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background-color: #ff3333 !important;
    border-color: #ff3333 !important;
}

/* ── Alerts ─────────────────────────────────────────────────────────────── */
[data-testid="stAlert"],
[data-testid="stAlertContainer"] {
    border-radius: var(--radius-sm) !important;
    font-size: 13px !important;
    font-family: var(--font-body) !important;
}
[data-testid="stAlertContainer"][data-baseweb="notification"] { background-color: var(--bg-surface) !important; }

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary p {
    background-color: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    font-size: 14px !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
}
[data-testid="stExpanderDetails"] {
    background-color: var(--bg-surface) !important;
    border-top: 1px solid var(--border) !important;
}

/* ── Spinner ────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] p,
[data-testid="stSpinner"] span { color: var(--text-muted) !important; }

/* ── Metrics ────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] { background: transparent; }
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: var(--text-primary) !important; }

/* ── Columns ────────────────────────────────────────────────────────────── */
[data-testid="stColumn"] { background-color: transparent !important; }

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }

/* ── Plotly charts ──────────────────────────────────────────────────────── */
.js-plotly-plot .plotly .bg { fill: transparent !important; }

/* ═══════════════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS
═══════════════════════════════════════════════════════════════════════════ */

/* Nav bar */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 32px;
}
.nav-logo { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; color: #fff; }
.nav-logo span { color: var(--accent); }
.nav-tag {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

/* Sidebar nav items */
.sb-nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    margin-bottom: 4px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-muted);
    transition: all 0.15s;
}
.sb-nav-item.active {
    background: var(--accent-dim);
    color: var(--accent-light);
    border: 1px solid var(--border-accent);
}
.sb-nav-item:not(.active):hover { background: var(--bg-elevated); color: var(--text-primary); }
.sb-section-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-ghost);
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 12px;
    margin: 12px 0 6px;
}
.sb-stat-block {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px;
    margin-bottom: 8px;
}
.sb-stat-block .sb-stat-num { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.sb-stat-block .sb-stat-label { font-size: 11px; color: var(--text-faint); margin-top: 2px; font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.6px; }

/* Page titles */
.page-title { font-size: 26px; font-weight: 700; color: #fff; letter-spacing: -0.5px; margin-bottom: 4px; }
.page-subtitle { font-size: 14px; color: var(--text-muted); margin-bottom: 28px; line-height: 1.5; }

/* Section header (replaces st.subheader) */
.section-header {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 24px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* Summary section cards */
.section-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 12px;
    height: 100%;
}
.section-card h4 {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1.4px;
    margin: 0 0 12px;
}
.section-card p, .section-card li { color: var(--text-secondary); font-size: 13.5px; line-height: 1.65; margin: 0; }
.section-card ul { padding-left: 16px; margin: 0; }
.section-card li { margin-bottom: 5px; }
.section-card .empty { color: var(--text-ghost); font-style: italic; font-size: 13px; }

/* Overview card */
.overview-card {
    background: linear-gradient(135deg, #141c38 0%, var(--bg-surface) 100%);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius-lg);
    padding: 24px 28px;
    margin-bottom: 20px;
}
.overview-card .ov-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--accent-light);
    text-transform: uppercase;
    letter-spacing: 1.4px;
    margin: 0 0 10px;
}
.overview-card p { color: #d8dcee; font-size: 14.5px; line-height: 1.75; margin: 0; }

/* Stat badges (summary page top row) */
.stat-row { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-badge {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    flex: 1;
    min-width: 100px;
}
.stat-badge .stat-num { font-size: 20px; font-weight: 700; color: var(--text-primary); display: block; }
.stat-badge .stat-label { font-size: 10px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.8px; font-family: var(--font-mono); }

/* Meta pill row (language, duration) */
.meta-row { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-muted);
}

/* Action bar (Save / Download / Email) */
.action-bar {
    display: flex;
    gap: 10px;
    align-items: center;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 18px;
    margin: 20px 0;
    flex-wrap: wrap;
}

/* Transcript segment */
.seg-block {
    background: var(--bg-elevated);
    border-left: 3px solid var(--border-accent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 10px 14px;
    margin-bottom: 10px;
}
.seg-header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px; }
.seg-speaker { font-size: 12px; font-weight: 600; color: var(--accent-light); font-family: var(--font-mono); }
.seg-time { font-size: 11px; color: var(--text-ghost); font-family: var(--font-mono); }
.seg-text { font-size: 13.5px; color: var(--text-secondary); line-height: 1.6; margin: 0; }
.seg-sentiment { font-size: 11px; color: var(--text-ghost); margin-top: 4px; font-family: var(--font-mono); }
.seg-sentiment.POS { color: #22c55e; }
.seg-sentiment.NEG { color: var(--red); }

/* Speaker analytics card */
.analytics-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 12px;
}
.analytics-card .ac-header { font-size: 10px; font-family: var(--font-mono); color: var(--text-faint); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 14px; }
.speaker-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); }
.speaker-row:last-child { border-bottom: none; }
.speaker-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.speaker-meta { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
.sentiment-pill {
    font-size: 10px;
    font-family: var(--font-mono);
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.5px;
}
.sentiment-pill.POS { background: var(--green-dim); color: var(--green); border: 1px solid #1a4d2e; }
.sentiment-pill.NEU { background: var(--bg-elevated); color: var(--text-faint); border: 1px solid var(--border-mid); }
.sentiment-pill.NEG { background: var(--red-dim); color: var(--red); border: 1px solid var(--red-border); }

/* Chat card */
.chat-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 12px;
}
.chat-card .cc-label { font-size: 10px; font-family: var(--font-mono); color: var(--text-faint); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 12px; }
.chat-answer {
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: var(--radius-sm);
    padding: 14px;
    font-size: 13.5px;
    color: var(--text-secondary);
    line-height: 1.65;
    margin-top: 12px;
}

/* Meeting history cards */
.meeting-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}
.meeting-card:hover { border-color: var(--border-hover); }
.meeting-card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.meeting-card-meta { font-size: 11px; font-family: var(--font-mono); color: var(--text-faint); margin-bottom: 8px; }
.meeting-card-overview { font-size: 13px; color: var(--text-muted); line-height: 1.55; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

/* Recording controls */
.rec-container {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin: 16px 0;
}
.rec-label { font-size: 10px; font-family: var(--font-mono); color: var(--text-faint); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 14px; }
.rec-status {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--red-dim);
    border: 1px solid var(--red-border);
    border-radius: var(--radius-sm);
    padding: 10px 14px;
    margin-top: 12px;
}
.rec-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--red); flex-shrink: 0;
    animation: rec-pulse 1.4s ease-in-out infinite;
}
.rec-status-text { font-size: 13px; font-family: var(--font-mono); color: #ffaaaa; }
.rec-timer { font-size: 13px; font-family: var(--font-mono); color: var(--red); margin-left: auto; }

/* Upload area label */
.upload-hint { font-size: 11px; color: var(--text-ghost); font-family: var(--font-mono); margin-top: 4px; }

/* History stats bar */
.history-meta { font-size: 11px; font-family: var(--font-mono); color: var(--text-faint); margin-bottom: 14px; }

/* Danger button (delete) */
[data-testid="stButton"] button.danger { background: var(--red-dim) !important; border-color: var(--red-border) !important; color: var(--red) !important; }

/* Spacer utilities */
.gap-sm { height: 8px; }
.gap { height: 16px; }
.gap-lg { height: 24px; }

/* Recording animation — defined here once, not re-injected every second */
@keyframes rec-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.35; transform: scale(1.4); }
}

/* How-it-works card side column */
.how-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
}
.how-card .how-label { font-size: 10px; font-family: var(--font-mono); color: var(--text-faint); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 14px; }
.how-step { display: flex; gap: 12px; margin-bottom: 12px; align-items: flex-start; }
.how-num { width: 20px; height: 20px; border-radius: 50%; background: var(--accent-dim); border: 1px solid var(--border-accent); font-size: 10px; font-family: var(--font-mono); color: var(--accent-light); display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.how-text { font-size: 13px; color: var(--text-muted); line-height: 1.5; }
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
        max_workers=1,
        thread_name_prefix="MeetGenieRecordingProcessor",
    )


def _process_recorded_audio(meeting_file):
    try:
        return process_video(meeting_file)
    finally:
        try:
            os.remove(meeting_file)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:

        st.markdown(
            '<div style="padding:4px 0 20px;"><span style="font-size:18px;font-weight:700;color:#fff;letter-spacing:-0.3px;">Meet<span style="color:#4f7cff;">Genie</span></span></div>',
            unsafe_allow_html=True,
        )

        # --------------------------------------------------
        # Logged in user
        # --------------------------------------------------
        user = st.session_state.get("user")

        if user:
            with st.container(border=True):
                st.markdown(f"### 👤 {user['name']}")
                st.caption(user["email"])

        page = st.session_state.get("page", "upload")

        nav_items = [
            ("🎙️", "New Meeting", "upload"),
            ("📋", "History", "history"),
        ]

        for icon, label, target in nav_items:
            active = "active" if page == target else ""

            st.markdown(
                f'<div class="sb-nav-item {active}">{icon}&nbsp;&nbsp;{label}</div>',
                unsafe_allow_html=True,
            )

            if st.button(
                label,
                key=f"sb_{target}",
                width="stretch",
                help=f"Go to {label}",
            ):
                st.session_state["page"] = target

                if target != "results":
                    st.session_state["result"] = None

                st.rerun()

        if st.session_state.result:
            active = "active" if page == "results" else ""

            st.markdown(
                f'<div class="sb-nav-item {active}">✨&nbsp;&nbsp;Last Summary</div>',
                unsafe_allow_html=True,
            )

            if st.button(
                "Last Summary",
                key="sb_results",
                width="stretch",
            ):
                st.session_state["page"] = "results"
                st.rerun()

        st.markdown(
            '<div class="sb-section-label">Quick Stats</div>',
            unsafe_allow_html=True,
        )

        all_meetings = get_all_meetings(st.session_state.user["id"])

        st.markdown(
            f"""
            <div class="sb-stat-block">
                <div class="sb-stat-num">{len(all_meetings)}</div>
                <div class="sb-stat-label">Meetings saved</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_recording():
            elapsed = get_recording_duration()
            mins, secs = divmod(int(elapsed), 60)

            st.markdown(
                f"""<div class="sb-stat-block" style="border-color:var(--red-border);background:var(--red-dim);display:flex;align-items:center;justify-content:space-between;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <div class="rec-dot"></div>
                        <span class="sb-stat-num" style="color:var(--red);">{mins:02d}:{secs:02d}</span>
                    </div>
                    <span class="sb-stat-label" style="color:#ffaaaa;">Recording active</span>
                </div>""",
                unsafe_allow_html=True,
            )

        # --------------------------------------------------
        # Sign out
        # --------------------------------------------------
        st.markdown("<br>", unsafe_allow_html=True)

        if user:
            if st.button(
                "🚪 Sign Out",
                key="logout_btn",
                width="stretch",
            ):
                st.session_state.clear()
                st.rerun()

        st.markdown(
            '<div class="gap-lg"></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="font-size:10px;color:var(--text-ghost);font-family:DM Mono,monospace;padding:0 12px;">MeetGenie · Whisper + Gemini</div>',
            unsafe_allow_html=True,
        )
# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def nav_bar(current_page):
    labels = {"upload": "New Meeting", "results": "Summary", "history": "History"}
    st.markdown(f"""
    <div class="nav-bar">
        <div class="nav-logo">Meet<span>Genie</span></div>
        <div class="nav-tag">{labels.get(current_page, '')}</div>
    </div>
    """, unsafe_allow_html=True)


def section_card(title, items, icon=""):
    if not items:
        content = '<p class="empty">None recorded</p>'
    else:
        lis = "".join(f"<li>{item}</li>" for item in items if item)
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
#  PAGE 0 — LOGIN
# ─────────────────────────────────────────────────────────────────────────────

def login_page():

    st.markdown(
        """
<style>

.login-container{
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    text-align:center;
    margin-top:100px;
    margin-bottom:40px;
}

.login-title{
    font-size:56px;
    font-weight:700;
    color:white;
    margin-bottom:20px;
}

.login-subtitle{
    color:#9ca3af;
    font-size:22px;
    line-height:1.7;
    max-width:750px;
}

</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="login-container">

<div class="login-title">
Meet<span style="color:#4F7FFF;">Genie</span>
</div>

<div class="login-subtitle">
AI-powered meeting summaries, action items and automatic
Google Calendar integration.<br>
Sign in to continue.
</div>

</div>
""",
        unsafe_allow_html=True,
    )

    # Center Google Sign-In button
    left, center, right = st.columns([3, 2, 3])

    with center:
        user = google_login()

    if user:

        save_user(
            email=user["email"],
            name=user["name"],
            credentials=user["credentials"],
        )

        db_user = get_user(user["email"])
        user["id"] = db_user[0]

        st.session_state["logged_in"] = True
        st.session_state["user"] = user
        st.session_state["google_token"] = user["token"]
        st.session_state["page"] = "upload"

        st.rerun()
# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 1 — UPLOAD
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

        # ── Upload section ─────────────────────────────────────────────────
        st.markdown('<div class="gap"></div>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Drop your recording or transcript here",
            type=["mp3", "wav", "mp4", "txt"],
            help="MP3, WAV, MP4 for audio/video — TXT for raw transcripts",
            label_visibility="visible",
        )
        st.markdown('<div class="upload-hint">MP3 · WAV · MP4 · TXT &nbsp;·&nbsp; Max 500 MB</div>', unsafe_allow_html=True)

        if uploaded_file:
            st.success(f"✓ **{uploaded_file.name}** ready to process")
            if meeting_name.strip():
                st.session_state.filename = meeting_name.strip()

        # ── Upload processing in progress ──────────────────────────────────
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

        if st.button("Generate Summary →", type="primary", width='stretch'):
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

                    def _process_upload(path):
                        try:
                            return process_video(path)
                        finally:
                            try:
                                os.remove(path)
                            except OSError:
                                pass

                    st.session_state.upload_future = (
                        st.session_state.recording_executor.submit(
                            _process_upload, temp_path
                        )
                    )
                except Exception as exc:
                    st.session_state.error = str(exc)
                st.rerun()

        if st.session_state.error:
            st.error(f"⚠ {st.session_state.error}")
            st.session_state.error = None

        # ── Recording section ──────────────────────────────────────────────
        currently_recording = is_recording()

        st.markdown("""
        <div class="rec-container">
            <div class="rec-label">🎙 Live Recording</div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # closed below after buttons

        # Re-open for Streamlit widgets (can't mix HTML and widgets inside one markdown block)
        st.markdown('<div class="rec-container" style="margin-top:-12px;border-top:none;border-radius:0 0 10px 10px;padding-top:0;">', unsafe_allow_html=True)

        if st.session_state.recording_error:
            st.error(f"Recording failed: {st.session_state.recording_error}")
            st.session_state.recording_error = None

        recording_future = st.session_state.recording_future
        if recording_future is not None:
            if recording_future.done():
                try:
                    st.session_state.result = recording_future.result()
                    st.session_state.filename = (
                        st.session_state.recording_processing_name
                        or meeting_name.strip()
                    )
                    st.session_state.chat_answer = None
                    st.session_state.pop("calendar_events", None)
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
            if st.button("▶  Start Recording", width='stretch'):
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
            if st.button("⏹  Stop & Summarise", type="primary", width='stretch'):
                try:
                    with st.spinner("Saving audio…"):
                        meeting_file = stop_recording()
                    st.session_state.recording = False
                    st.session_state.recording_processing_name = meeting_name.strip()
                    st.session_state.recording_future = (
                        st.session_state.recording_executor.submit(
                            _process_recorded_audio,
                            meeting_file,
                        )
                    )
                except Exception as exc:
                    st.session_state.recording = False
                    st.session_state.recording_error = str(exc)
                st.rerun()

            # Live status indicator — @keyframes defined in main CSS, not here
            elapsed = get_recording_duration()
            mins, secs = divmod(int(elapsed), 60)
            st.markdown(f"""
            <div class="rec-status">
                <div class="rec-dot"></div>
                <span class="rec-status-text">Recording in progress</span>
                <span class="rec-timer">{mins:02d}:{secs:02d}</span>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(1)
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_side:
        st.markdown('<div class="gap-lg"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="how-card">
            <div class="how-label">How it works</div>
            <div class="how-step"><div class="how-num">1</div><div class="how-text">Upload a recording (MP3/WAV/MP4) or a text transcript</div></div>
            <div class="how-step"><div class="how-num">2</div><div class="how-text">Whisper transcribes your audio with speaker detection</div></div>
            <div class="how-step"><div class="how-num">3</div><div class="how-text">Gemini AI extracts insights, actions, risks and decisions</div></div>
            <div class="how-step"><div class="how-num">4</div><div class="how-text">Download as PDF, email to your team, or save to History</div></div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 2 — RESULTS
# ─────────────────────────────────────────────────────────────────────────────
def results_page():
    nav_bar("results")

    result = st.session_state.result

    # Automatically detect calendar events once
    if "calendar_events" not in st.session_state:
        transcript = result.get("transcript", "")

        if transcript.strip():
            try:
                st.session_state.calendar_events = extract_calendar_events(transcript)
            except Exception as e:
                st.session_state.calendar_events = []
                st.warning(f"Calendar extraction failed: {e}")
    if not result:
        st.error("No summary found. Please process a meeting first.")
        if st.button("← New Meeting", key="results_back"):
            st.session_state.page = "upload"
            st.rerun()
        return

    # ── Header ────────────────────────────────────────────────────────────
    name = st.session_state.filename or "Meeting Summary"
    st.markdown(f'<div class="page-title">{name}</div>', unsafe_allow_html=True)

    meta_pills(result.get("language"), result.get("duration", 0))
    stat_badges(result)

    # ── Overview ──────────────────────────────────────────────────────────
    overview = result.get("overview", "").strip()
    st.markdown(f"""
    <div class="overview-card">
        <div class="ov-label">📄 &nbsp;Meeting Overview</div>
        <p>{overview or '<span style="color:var(--text-ghost);font-style:italic;">No overview generated.</span>'}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Action bar ────────────────────────────────────────────────────────
    act_col1, act_col2, act_col3 = st.columns([1, 1, 2])
    with act_col1:
        if st.button("💾  Save to History", width='stretch', key="save_history_btn"):
            if overview:
                save_meeting(st.session_state.user["id"], st.session_state.filename, result)
                st.success("Saved.")
            else:
                st.error("Cannot save — no overview generated.")
    with act_col2:
        pdf_bytes = generate_summary_pdf(result, name)
        st.download_button(
            "⬇  Download PDF",
            data=pdf_bytes,
            file_name=f"{name.replace(' ', '_')}_summary.pdf",
            mime="application/pdf",
            key="download_pdf_results",
            width='stretch',
        )
    with act_col3:
        email_inner_col, email_btn_col = st.columns([3, 1])
        with email_inner_col:
            email = st.text_input("Recipient email", placeholder="Email summary to…", key="results_email", label_visibility="collapsed")
        with email_btn_col:
            if st.button("Send →", width='stretch', key="send_email_btn"):
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

    # ── Speaker analytics & sentiment ─────────────────────────────────────
    segments = result.get("segments", [])

    # Compute speaker summary once (works for both diarized and plain transcripts)
    speaker_sentiments: dict = defaultdict(list)
    for seg in segments:
        speaker_sentiments[seg.get("speaker", "Unknown")].append(seg.get("sentiment", "NEUTRAL"))
    speaker_summary = {spk: get_dominant_sentiment(sents) for spk, sents in speaker_sentiments.items()}

    if segments:
        st.markdown('<div class="section-header">Analytics</div>', unsafe_allow_html=True)

        stats = result.get("talk_time") or calculate_talk_time(segments)
        participation = result.get("participation") or calculate_participation(stats)

        ana_col, chart_col = st.columns([1, 1])

        with ana_col:
            rows = ""
            for spk, pct in participation.items():
                talk_s = round(stats[spk], 1)
                dom    = speaker_summary.get(spk, "NEUTRAL")
                pill   = sentiment_pill(dom)
                rows += (
                    f'<div class="speaker-row">'
                    f'<div>'
                    f'<div class="speaker-name">{spk}</div>'
                    f'<div class="speaker-meta">{pct}% &nbsp;&middot;&nbsp; {talk_s}s</div>'
                    f'</div>'
                    f'{pill}'
                    f'</div>'
                )
            html_block = (
                f'<div class="analytics-card">'
                f'<div class="ac-header">Speaker Breakdown</div>'
                f'{rows}'
                f'</div>'
            )
            st.html(html_block)

        with chart_col:
            if participation:
                fig = px.pie(
                    values=list(participation.values()),
                    names=list(participation.keys()),
                    hole=0.45,
                    color_discrete_sequence=["#4f7cff", "#ff4b4b", "#22c55e", "#f59e0b", "#a855f7"],
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans, sans-serif", color="#b8bdd0", size=12),
                    margin=dict(l=0, r=0, t=20, b=0),
                    legend=dict(font=dict(color="#b8bdd0"), bgcolor="rgba(0,0,0,0)"),
                    showlegend=True,
                )
                fig.update_traces(textfont_color="#eceef5", textfont_size=12)
                st.plotly_chart(fig, width='stretch')

    # ── Transcript ────────────────────────────────────────────────────────
    with st.expander("📝  Full Transcript", expanded=False):
        if segments:
            html_segs = ""
            for seg in segments:
                s, e = int(seg["start"]), int(seg["end"])
                ts   = f"{s//60:02d}:{s%60:02d} – {e//60:02d}:{e%60:02d}"
                spk  = seg.get("speaker", "Unknown")
                txt  = seg.get("text", "").strip()
                sent = seg.get("sentiment", "NEUTRAL")
                scr  = seg.get("sentiment_score", 0)
                cls  = {"POSITIVE": "POS", "NEGATIVE": "NEG"}.get(sent, "NEU")
                html_segs += f"""
                <div class="seg-block">
                    <div class="seg-header">
                        <span class="seg-speaker">{spk}</span>
                        <span class="seg-time">{ts}</span>
                    </div>
                    <p class="seg-text">{txt}</p>
                    <div class="seg-sentiment {cls}">{sent} {scr:.2f}</div>
                </div>"""
            st.markdown(html_segs, unsafe_allow_html=True)
        else:
            st.text_area("", result.get("transcript", ""), height=300, label_visibility="collapsed")

    # ── Chat with meeting ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">Chat With This Meeting</div>', unsafe_allow_html=True)
    st.markdown('<div class="chat-card"><div class="cc-label">💬 Ask anything about this meeting</div>', unsafe_allow_html=True)

    question = st.text_input(
        "Ask a question",
        placeholder="e.g. What action items were assigned to Sarah?",
        key="chat_question",
        label_visibility="collapsed",
    )
    if question:
        with st.spinner("Thinking…"):
            answer = ask_meeting_question(result.get("transcript", ""), question)
            st.session_state.chat_answer = answer

    if st.session_state.chat_answer:
        st.markdown(f'<div class="chat-answer">{st.session_state.chat_answer}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close chat-card

    # ─────────────────────────────────────────────────────────────
    # Calendar Events
    # ─────────────────────────────────────────────────────────────

    events = st.session_state.get("calendar_events", [])

    if events:

        st.markdown(
            '<div class="section-header">📅 Calendar Events</div>',
            unsafe_allow_html=True,
        )

        edited_events = []

        for i, event in enumerate(events):

            with st.container(border=True):

                st.markdown(f"## 📅 Event {i+1}")

                enabled = st.checkbox(
                    "Add this event",
                    value=True,
                    key=f"event_enable_{i}",
                )

                title = st.text_input(
                    "Title",
                    value=event["title"],
                    key=f"title_{i}",
                )

                col1, col2 = st.columns(2)

                with col1:

                    date = st.date_input(
                        "Date",
                        value=datetime.strptime(
                            event["date"],
                            "%Y-%m-%d"
                        ).date(),
                        key=f"date_{i}",
                    )

                with col2:

                    time = st.time_input(
                        "Time",
                        value=datetime.strptime(
                            event["time"],
                            "%H:%M"
                        ).time(),
                        key=f"time_{i}",
                    )

                col3, col4 = st.columns(2)

                with col3:

                    duration = st.number_input(
                        "Duration (minutes)",
                        min_value=15,
                        max_value=480,
                        value=event.get(
                            "duration_minutes",
                            60,
                        ),
                        step=15,
                        key=f"duration_{i}",
                    )

                with col4:

                    reminder = st.selectbox(
                        "Reminder",
                        [5,10,15,30,60,120],
                        index=[5,10,15,30,60,120].index(
                            event.get(
                                "reminder_minutes",
                                30,
                            )
                        ),
                        key=f"reminder_{i}",
                    )

                description = st.text_area(
                    "Description",
                    value=event.get(
                        "description",
                        "",
                    ),
                    key=f"description_{i}",
                )

                if enabled:

                    edited_events.append({

                        "title": title,

                        "date": date.strftime("%Y-%m-%d"),

                        "time": time.strftime("%H:%M"),

                        "duration_minutes": duration,

                        "description": description,

                        "reminder_minutes": reminder,

                    })

        st.write("")

        if st.button(
            "📅 Add Selected Events to Google Calendar",
            type="primary",
            use_container_width=True,
        ):

            if not edited_events:

                st.warning("Please select at least one event.")

            else:

                token = st.session_state.get("google_token")

                if token is None:

                    st.error("Please login with Google.")

                else:

                    try:

                        created = create_calendar_events(
                            edited_events,
                            token,
                        )

                        st.success(
                            f"✅ Added {len(created)} event(s) to Google Calendar!"
                        )

                    except Exception as e:

                        st.error(str(e))

    else:

        st.info("No calendar events detected.")


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE 3 — HISTORY
# ─────────────────────────────────────────────────────────────────────────────
def history_page():
    nav_bar("history")

    st.markdown('<div class="page-title">Meeting History</div>', unsafe_allow_html=True)

    search_query = st.text_input(
        "Search meetings",
        placeholder="🔍  Search by name, keyword, or content…",
        key="history_search",
        label_visibility="collapsed",
    )
    st.markdown('<div class="gap-sm"></div>', unsafe_allow_html=True)
    meetings     = search_meetings(st.session_state.user["id"], search_query) if search_query.strip() else get_all_meetings(st.session_state.user["id"])
    total        = len(get_all_meetings(st.session_state.user["id"])) if search_query.strip() else len(meetings)
    count_label  = (
        f"{len(meetings)} result{'s' if len(meetings) != 1 else ''} for \"{search_query}\""
        if search_query.strip()
        else f"{total} saved meeting{'s' if total != 1 else ''}"
    )
    st.markdown(f'<div class="history-meta">{count_label}</div>', unsafe_allow_html=True)

    if not meetings:
        if search_query:
            st.info(f'No meetings match "{search_query}".')
        else:
            st.info("No meetings saved yet. Process a meeting and click **Save to History**.")
        return

    for meeting in meetings:
        meeting_id, filename, created_at, overview, summary_json = meeting

        st.markdown(f"""
        <div class="meeting-card">
            <div class="meeting-card-title">{filename or "Untitled Meeting"}</div>
            <div class="meeting-card-meta">{created_at}</div>
            <div class="meeting-card-overview">{overview or "No overview available."}</div>
        </div>
        """, unsafe_allow_html=True)

        detail_col, del_col = st.columns([6, 1])

        with detail_col:
            with st.expander("View summary"):
                try:
                    parsed = json.loads(summary_json)
                except (json.JSONDecodeError, TypeError):
                    parsed = {}

                ov_text = parsed.get("overview", "")
                if ov_text:
                    st.markdown(f"""
                    <div class="overview-card" style="margin-bottom:16px;">
                        <div class="ov-label">📄 Overview</div>
                        <p>{ov_text}</p>
                    </div>
                    """, unsafe_allow_html=True)

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

        with del_col:
            st.markdown('<div class="gap"></div>', unsafe_allow_html=True)
            if st.button("Delete", key=f"del_{meeting_id}", help="Delete this meeting"):
                delete_meeting(meeting_id, st.session_state.user["id"])
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTER
# ─────────────────────────────────────────────────────────────────────────────
pages = {
    "login": login_page,
    "upload": upload_page,
    "results": results_page,
    "history": history_page,
}

# Show sidebar only after the user has signed in
if st.session_state.get("logged_in", False):
    render_sidebar()

# Render the current page
pages.get(
    st.session_state.get("page", "login"),
    login_page,
)()