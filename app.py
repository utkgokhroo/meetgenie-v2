import streamlit as st
import json
import os
import plotly.express as px
from processor import process_video
from chat_with_meeting import ask_meeting_question
from database import init_db, save_meeting, delete_meeting, get_all_meetings, search_meetings
from email_sender import send_summary_email
from pdf_exporter import generate_summary_pdf
from speaker_intelligence import (
    calculate_talk_time,
    calculate_participation,
    get_top_speaker
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
os.makedirs("summaries", exist_ok=True)

#  CONFIG
init_db()

st.set_page_config(
    page_title="MeetGenie v2",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

#  CUSTOM CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');


:root {
    --bg-base:         #0f1117;
    --bg-surface:      #141720;
    --bg-surface-2:    #1a1d2b;
    --bg-overlay:      #141c38;
    --border:          #1e2130;
    --border-strong:   #252836;
    --border-accent:   #2a3260;
    --border-hover:    #2e3a5c;
    --text-primary:    #e8eaf0;
    --text-secondary:  #c8ccd8;
    --text-muted:      #7a8098;
    --text-faint:      #5a6070;
    --text-dim:        #4a5068;
    --text-ghost:      #3a4060;
    --accent:          #4f7cff;
    --accent-light:    #7c9fff;
    --font-body:       'DM Sans', sans-serif;
    --font-mono:       'DM Mono', monospace;
}

html, body {
    font-family: var(--font-body) !important;
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
}


[data-testid="stApp"] {
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
}

[data-testid="stAppViewContainer"] {
    background-color: var(--bg-base) !important;
}

[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
}

[data-testid="stHeader"] {
    background-color: var(--bg-base) !important;
}

[data-testid="stBottom"] {
    background-color: var(--bg-base) !important;
}

#MainMenu, footer, header { visibility: hidden; }


[data-testid="stMarkdown"],
[data-testid="stMarkdownContainer"],
[data-testid="stText"] {
    color: var(--text-primary) !important;
}

[data-testid="stMarkdown"] > div > p,
[data-testid="stMarkdown"] > div > ul,
[data-testid="stMarkdown"] > div > ol,
[data-testid="stMarkdown"] > div > li {
    color: var(--text-primary) !important;
}

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: var(--text-muted) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    font-family: var(--font-body) !important;
}

hr {
    border-color: var(--border) !important;
}


[data-testid="stTextInput"],
[data-testid="stTextInputRootElement"] {
    background-color: transparent !important;
}

[data-testid="stTextInput"] input,
[data-testid="stTextInputRootElement"] input {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    caret-color: var(--accent) !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder {
    color: var(--text-ghost) !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextInputRootElement"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
    outline: none !important;
}

[data-testid="stFileUploader"] {
    background-color: transparent !important;
}

[data-testid="stFileUploaderDropzone"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--text-muted) !important;
}

[data-testid="stFileChip"] {
    background-color: var(--bg-surface-2) !important;
    border-color: var(--border) !important;
}

[data-testid="stFileChipName"] {
    color: var(--text-secondary) !important;
}


[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {
    border-radius: 8px !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    transition: all 0.15s ease !important;
}
            
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]),
[data-testid="stDownloadButton"] button[kind="secondary"],
[data-testid="stDownloadButton"] button:not([kind="primary"]) {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-primary) !important;
}

[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stButton"] button:not([kind="primary"]):not([kind="tertiary"]):hover,
[data-testid="stDownloadButton"] button:not([kind="primary"]):hover {
    background-color: var(--bg-surface-2) !important;
    border-color: var(--accent) !important;
    color: var(--text-primary) !important;
}

[data-testid="stButton"] button[kind="primary"] {
    background-color: #ff4b4b !important;
    border-color: #ff4b4b !important;
    color: #ffffff !important;
}

[data-testid="stAlert"],
[data-testid="stAlertContainer"] {
    border-radius: 8px !important;
    font-size: 13px !important;
    font-family: var(--font-body) !important;
}

[data-testid="stAlertContainer"][data-baseweb="notification"] {
    background-color: var(--bg-surface) !important;
}

[data-testid="stExpander"] {
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary p {
    background-color: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    font-size: 14px !important;
    font-family: var(--font-body) !important;
}

[data-testid="stExpanderDetails"] {
    background-color: var(--bg-surface) !important;
    border-top: 1px solid var(--border) !important;
}

[data-testid="stSpinner"] p,
[data-testid="stSpinner"] span {
    color: var(--text-muted) !important;
}

[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebarContent"] * {
    color: var(--text-primary) !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

[data-testid="stColumn"] {
    background-color: transparent !important;
}


/* Nav bar */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 0 24px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 36px;
}
.nav-logo {
    font-size: 28px !important;
    font-weight: 700 !important;
    letter-spacing: -0.4px;
    color: #ffffff !important;
}
.nav-logo span { color: #4f7cff !important; }
.nav-tag {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-faint);
    background: var(--bg-surface-2);
    border: 1px solid var(--border-strong);
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* Section card */
.section-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 16px;
}
.section-card h4 {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: 0 0 14px 0;
}
.section-card p, .section-card li {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.7;
    margin: 0;
}
.section-card ul { padding-left: 18px; margin: 0; }
.section-card li { margin-bottom: 6px; }

/* Overview card */
.overview-card {
    background: linear-gradient(135deg, var(--bg-overlay) 0%, var(--bg-surface) 100%);
    border: 1px solid var(--border-accent);
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 24px;
}
.overview-card h4 {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--accent-light);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: 0 0 12px 0;
}
.overview-card p {
    color: #dde2f0;
    font-size: 15px;
    line-height: 1.75;
    margin: 0;
}

/* Meeting history card */
.meeting-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.meeting-card:hover { border-color: var(--border-hover); }
.meeting-card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.meeting-card-meta {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-dim);
    margin-bottom: 10px;
}
.meeting-card-overview {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* Stat badges */
.stat-row {
    display: flex;
    gap: 12px;
    margin-bottom: 28px;
    flex-wrap: wrap;
}
.stat-badge {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 18px;
    flex: 1;
    min-width: 120px;
}
.stat-badge .stat-num {
    font-size: 22px;
    font-weight: 600;
    color: var(--accent);
    display: block;
}
.stat-badge .stat-label {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-family: var(--font-mono);
}

/* Page titles */
.page-title {
    font-size: 28px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
}
.page-subtitle {
    font-size: 14px;
    color: var(--text-faint);
    margin-bottom: 32px;
}

/* Upload hint */
.upload-hint {
    font-size: 12px;
    color: var(--text-ghost);
    font-family: var(--font-mono);
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

#  SESSION STATE
for key, default in [("page", "upload"), ("result", None), ("error", None), ("filename", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


#  HELPERS
def nav_bar(current_page):
    page_labels = {"upload": "New Meeting", "results": "Summary", "history": "History"}
    label = page_labels.get(current_page, "")
    st.markdown(f"""
    <div class="nav-bar">
        <div class="nav-logo">Meet<span>Genie</span> v2</div>
        <div class="nav-tag">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def section_card(title, items, icon=""):
    if not items:
        content = '<p style="color:#3a4060;font-style:italic;font-size:13px;">None recorded</p>'
    else:
        lis = "".join(f"<li>{item}</li>" for item in items)
        content = f"<ul>{lis}</ul>"
    st.markdown(f"""
    <div class="section-card">
        <h4>{icon} {title}</h4>
        {content}
    </div>
    """, unsafe_allow_html=True)


def stat_badges(result):
    counts = [
        (len(result.get("discussion_points", [])), "Discussion"),
        (len(result.get("action_items", [])), "Actions"),
        (len(result.get("decisions", [])), "Decisions"),
        (len(result.get("questions", [])), "Questions"),
        (len(result.get("risks", [])), "Risks"),
    ]
    badges = "".join(
        f'<div class="stat-badge"><span class="stat-num">{n}</span><span class="stat-label">{label}</span></div>'
        for n, label in counts
    )
    st.markdown(f'<div class="stat-row">{badges}</div>', unsafe_allow_html=True)


#  PAGE 1 — UPLOAD
def upload_page():
    nav_bar("upload")

    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown('<div class="page-title">New Meeting Summary</div>', unsafe_allow_html=True)
        st.markdown('<div class="page-subtitle">Upload a recording or transcript to generate an AI-powered summary.</div>', unsafe_allow_html=True)

        meeting_name = st.text_input("Meeting name", placeholder="e.g. Q2 Planning - June 2026")

        uploaded_file = st.file_uploader(
            "Recording or transcript",
            type=["mp3", "wav", "mp4", "txt"],
            help="Supported formats: MP3, WAV, MP4 (audio/video), TXT (transcript)"
        )
        st.markdown('<div class="upload-hint">MP3 · WAV · MP4 · TXT</div>', unsafe_allow_html=True)

        if uploaded_file:
            st.success(f"✓ Ready to process **{uploaded_file.name}**")
            st.session_state.filename = meeting_name.strip()

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Generate Summary →", type="primary", use_container_width=True):
            if not uploaded_file:
                st.warning("Please upload a file before generating a summary.")
                return
            if not meeting_name.strip():
                st.warning("Please enter a meeting name.")
                return

            try:
                with st.spinner("Transcribing and summarising — this may take a minute…"):
                    ext = uploaded_file.name.rsplit(".", 1)[-1]
                    temp_path = f"temp.{ext}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.read())

                    result = process_video(temp_path)
                    st.session_state.result = result
                    st.session_state.page = "results"
                    os.remove(temp_path)

                st.rerun()

            except Exception as e:
                st.session_state.error = str(e)

    with col_side:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="section-card">
            <h4>How it works</h4>
            <ul>
                <li>Upload your meeting recording or paste a transcript (.txt)</li>
                <li>Whisper transcribes audio files automatically</li>
                <li>Gemini AI extracts key insights, action items and decisions</li>
                <li>Download the summary as PDF or email it directly</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("📋  View Meeting History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

    if st.session_state.error:
        st.error(f"⚠ {st.session_state.error}")
        st.session_state.error = None

def results_page():
    nav_bar("results")

    result = st.session_state.result
    st.write(result.get("speaker_count"))
    st.write(result.get("top_speaker"))
    st.write(result.get("participation"))
    if not result:
        st.error("No summary data found. Please go back and process a meeting.")
        if st.button("← Back", key="results_back"):
            st.session_state.page = "upload"
            st.rerun()
        return
    
    title_col, btn_col = st.columns([4, 1])
    with title_col:
        name = st.session_state.filename or "Meeting Summary"
        st.markdown(f'<div class="page-title">{name}</div>', unsafe_allow_html=True)
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← New Meeting", use_container_width=True, key="new_meeting_btn"):
            st.session_state.page = "upload"
            st.session_state.result = None
            st.rerun()

    stat_badges(result)
    language = result.get("language", "unknown")
    duration = result.get("duration", 0)

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"🌐 Language: {language}")

    with col2:
        st.info(f"Duration: {round(duration / 60, 1)} min")

    with st.expander("Transcript"):

        segments = result.get("segments", [])

        if segments:

            for seg in segments:

                start = int(seg["start"])
                end = int(seg["end"])

                start_ts = f"{start//60:02d}:{start%60:02d}"
                end_ts = f"{end//60:02d}:{end%60:02d}"

                speaker = seg.get("speaker", "Unknown")

            # DEBUG: remove later
                #st.write(seg)

                st.markdown(
                    f"**{speaker}** "
                    f"**[{start_ts} - {end_ts}]**"
            )

                st.write(seg["text"])

                sentiment = seg.get("sentiment", "UNKNOWN")
                score = seg.get("sentiment_score", 0)

                st.caption(
                    f" Sentiment: {sentiment} ({score:.2f})"
            )

        else:

            st.text_area(
                "Transcript",
                result.get("transcript", ""),
                height=300
        )

    # =========================
# Speaker Analytics
# =========================

    if segments:

        stats = calculate_talk_time(segments)

        participation = calculate_participation(stats)

        top_speaker = get_top_speaker(stats)

        st.subheader("📊 Speaker Analytics")

        if top_speaker:

            st.metric(
                "Most Active Speaker",
                top_speaker
            )

        st.subheader("Participation")

        for speaker, percent in participation.items():

            talk_time = round(
                stats[speaker],
                1
            )

            st.write(
                f"**{speaker}** → "
                f"{percent}% "
                f"({talk_time}s)"
            )

        if participation:

            fig = px.pie(
                values=list(participation.values()),
                names=list(participation.keys()),
                title="Speaker Participation"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        st.subheader("💬 Chat With Meeting")

        question = st.text_input(
            "Ask anything about this meeting"
        )

        if question:

            with st.spinner("Thinking..."):

                answer = ask_meeting_question(
                    result["transcript"],
                    question
                )

                st.success(answer)

    overview = result.get("overview", "").strip()
    st.markdown(f"""
    <div class="overview-card">
        <h4>📄 &nbsp;Meeting Overview</h4>
        <p>{overview if overview else '<span style="color:#3a4060;font-style:italic">No overview generated.</span>'}</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        section_card("Key Discussion Points", result.get("discussion_points", []), "🔑")
        section_card("Decisions", result.get("decisions", []), "📌")
    with c2:
        section_card("Action Items", result.get("action_items", []), "✅")
        section_card("Task Assignments", result.get("task_assignments", []), "👥")
    with c3:
        section_card("Risks", result.get("risks", []), "⚠️")
        section_card("Questions", result.get("questions", []), "❓")
        section_card("Follow Ups", result.get("follow_ups", []), "🔄")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Save to History", use_container_width=True, key="save_history_btn"):
            if overview:
                save_meeting(st.session_state.filename, result)
                st.success("Meeting saved successfully.")
            else:
                st.error("Cannot save a summary with no overview.")

        pdf_bytes = generate_summary_pdf(
            result,
            st.session_state.filename or "Meeting Summary"
        )

        st.download_button(
            "Download PDF",
            data=bytes(pdf_bytes),
            file_name=f"{(st.session_state.filename or 'meeting').replace(' ', '_')}_summary.pdf",
            mime="application/pdf",
            key="download_pdf_results",
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    email_col, btn_col = st.columns([3, 1])
    with email_col:
        email = st.text_input(
            "Send summary via email",
            placeholder="recipient@example.com",
            key="results_email"
        )
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Send Email →", use_container_width=True, key="send_email_btn"):
            if not email:
                st.warning("Please enter a recipient email address.")
            else:
                try:
                    send_summary_email(email, result)
                    st.success(f"Summary sent to **{email}**.")
                except Exception as e:
                    st.error(f"Failed to send email: {e}")

def history_page():
    nav_bar("history")

    title_col, back_col = st.columns([4, 1])
    with title_col:
        st.markdown('<div class="page-title">Meeting History</div>', unsafe_allow_html=True)
    with back_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Back", use_container_width=True, key="history_back"):
            st.session_state.page = "upload"
            st.rerun()

    search_query = st.text_input(
        "Search meetings",
        placeholder="🔍  Search meetings by name, keyword, or content…",
        label_visibility="collapsed",
        key="history_search"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    meetings = search_meetings(search_query) if search_query.strip() else get_all_meetings()

    total_meetings = len(get_all_meetings())
    st.markdown(f"""
    <div style="
        background-color:#1f2433;
        padding:16px;
        border-radius:10px;
        margin-bottom:16px;
        text-align:center;
    ">
        <div style="font-size:12px;color:#aab0c5;">Total Meetings</div>
        <div style="font-size:24px;font-weight:bold;color:white;">{total_meetings}</div>
    </div>
    """, unsafe_allow_html=True)

    if not meetings:
        if search_query:
            st.info(f'No meetings found matching "**{search_query}**".')
        else:
            st.info("No meetings saved yet. Process a meeting and click **Save to History**.")
        return

    count_label = (
        f"{len(meetings)} meeting{'s' if len(meetings) != 1 else ''} found"
        if search_query
        else f"{len(meetings)} saved meeting{'s' if len(meetings) != 1 else ''}"
    )

    st.markdown(
        f'<div style="font-size:12px;color:#4a5068;font-family:DM Mono,monospace;margin-bottom:16px;">{count_label}</div>',
        unsafe_allow_html=True
    )

    for meeting in meetings:
        meeting_id, filename, created_at, overview, summary_json = meeting

        st.markdown(f"""
        <div class="meeting-card">
            <div class="meeting-card-title">{filename or "Untitled Meeting"}</div>
            <div class="meeting-card-meta">{created_at}</div>
            <div class="meeting-card-overview">{overview or "No overview available."}</div>
        </div>
        """, unsafe_allow_html=True)

        detail_col, del_col = st.columns([5, 1])

        with detail_col:
            with st.expander("View full summary"):

                try:
                    parsed = json.loads(summary_json)
                except:
                    parsed = {}

                section_card("Overview", [parsed.get("overview", "")], "📄")

                ec1, ec2 = st.columns(2)
                with ec1:
                    section_card("Discussion Points", parsed.get("discussion_points", []), "🔑")
                    section_card("Action Items", parsed.get("action_items", []), "✅")
                with ec2:
                    section_card("Decisions", parsed.get("decisions", []), "📌")
                    section_card("Task Assignments", parsed.get("task_assignments", []), "👥")

                section_card("Next Steps", parsed.get("next_steps", []), "➡️")

                pdf_bytes = generate_summary_pdf(parsed, filename or "Meeting Summary")

                st.download_button(
                    "⬇ Download PDF",
                    data=bytes(pdf_bytes),
                    file_name=f"{(filename or 'meeting').replace(' ', '_')}_summary.pdf",
                    mime="application/pdf",
                    key=f"pdf_{meeting_id}"
                )

        with del_col:
            if st.button("🗑", key=f"del_{meeting_id}", help="Delete this meeting"):
                delete_meeting(meeting_id)
                st.rerun()

        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    page = st.session_state.get("page", "upload")
    
    if page == "upload":
        upload_page()
    elif page == "results":
        results_page()
    elif page == "history":
        history_page()