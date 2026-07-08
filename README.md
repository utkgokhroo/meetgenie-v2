# MeetGenie

AI-powered meeting intelligence built with Streamlit. Sign in with Google, upload or record a meeting, and get structured summaries with speaker analytics, action items, calendar event detection, and more.

## Features

- **Google sign-in** — OAuth login stores your profile and credentials for Gmail and Google Calendar
- **Upload or record** — supports MP3, WAV, MP4, and TXT transcripts, plus live microphone + system audio capture
- **Transcription** — OpenAI Whisper with automatic speaker diarization via pyannote.audio
- **AI summarization** — Gemini extracts overview, discussion points, action items, decisions, task assignments, next steps, risks, questions, and follow-ups
- **Speaker analytics** — talk time, participation breakdown, per-speaker sentiment, and interactive charts
- **Calendar event detection** — Gemini extracts dates and times from the transcript; review and add events to Google Calendar in one click
- **Chat with your meeting** — ask questions about the transcript using Gemini
- **Export & share** — download as PDF, send via email, or save to your personal history
- **Meeting history** — searchable, per-user SQLite database of all past summaries

## Project Structure

```
meetgenie/
├── app.py                         # Streamlit UI (login, upload, results, history)
├── core/
│   ├── processor.py               # Orchestrates transcription → summary → analytics
│   ├── transcriber.py             # Whisper transcription + speaker diarization
│   ├── summarizer.py              # Gemini summarization
│   ├── diarizer.py                # pyannote speaker diarization
│   ├── sentiment.py               # Per-segment sentiment analysis
│   ├── speaker_intelligence.py    # Talk time and participation stats
│   └── chat_with_meeting.py       # Gemini Q&A over transcript
├── recording/
│   ├── recording_manager.py       # Orchestrates recording threads
│   ├── audio_recorder.py          # Microphone capture
│   ├── system_audio_recorder.py   # WASAPI loopback (Windows)
│   ├── recorder.py                # Recording session helpers
│   └── merge.py                   # ffmpeg audio mixing
└── services/
    ├── database.py                # SQLite users + meetings storage
    ├── google_auth.py             # Google OAuth sign-in
    ├── calendar_extractor.py      # Gemini calendar event extraction
    ├── calendar_service.py        # Google Calendar API integration
    ├── email_sender.py            # yagmail email delivery
    ├── pdf_exporter.py            # FPDF summary export
    └── gemini_client.py           # Shared Gemini API client
```

## Requirements

- Python 3.11+
- ffmpeg on PATH
- Windows (for live system audio capture via WASAPI loopback)
- Google Cloud OAuth credentials (`client_secret_web.json`)
- A `.env` file in the project root (see Setup below)
- API keys for Gemini and HuggingFace

## Setup

```bash
# Clone and create virtual environment
git clone https://github.com/your-username/meetgenie.git
cd meetgenie
python -m venv .venv311
.venv311\Scripts\activate   # Windows
# source .venv311/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create your environment file (required — the app loads this via python-dotenv)
# On Windows:
copy NUL .env
# On macOS/Linux:
# touch .env
```

Then open `.env` and add your keys:

```env
GEMINI_API_KEY=your_gemini_api_key
HF_TOKEN=your_huggingface_token
EMAIL_ADDRESS=your_gmail_address
EMAIL_PASSWORD=your_gmail_app_password
```

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | [Google AI Studio](https://aistudio.google.com/app/apikey) — summarization, chat, calendar extraction |
| `HF_TOKEN` | Yes | [HuggingFace](https://huggingface.co/settings/tokens) — pyannote speaker diarization |
| `EMAIL_ADDRESS` / `EMAIL_PASSWORD` | No | Gmail + [App Password](https://myaccount.google.com/apppasswords) — email export only |

The `.env` file is gitignored. Do not commit it.

### Google OAuth

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Calendar API**.
3. Create **OAuth 2.0 Web application** credentials.
4. Add `http://localhost:8501` as an authorized redirect URI.
5. Download the credentials JSON and save it as `client_secret_web.json` in the project root.

This file is gitignored — do not commit it.

## Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501), sign in with Google, then upload or record a meeting.

## How It Works

1. **Sign in** with Google — your account is saved to SQLite and OAuth tokens enable Calendar and email features
2. **Upload or record** a meeting (MP3, WAV, MP4, or TXT)
3. **Whisper** transcribes audio; **pyannote** identifies speakers
4. **Gemini** generates the summary and detects calendar events mentioned in the meeting
5. **Review results** — analytics, sentiment, chat, PDF/email export, and one-click Google Calendar creation
6. **History** — all summaries are saved per user and searchable from the sidebar

## Database

MeetGenie uses a local SQLite database (`meetings.db`, gitignored) with two tables:

- **users** — Google account email, name, and stored OAuth credentials
- **meetings** — transcript, summary JSON, metadata, scoped to the logged-in user

The database is initialized automatically on app startup via `init_db()`.

## Tech Stack

| Component | Library |
|---|---|
| UI | Streamlit |
| Auth | streamlit-oauth, Google OAuth 2.0 |
| Transcription | OpenAI Whisper |
| Diarization | pyannote.audio |
| Summarization & chat | Google Gemini 2.5 Flash |
| Calendar | Google Calendar API |
| Sentiment | HuggingFace Transformers (RoBERTa) |
| Audio capture | sounddevice, PyAudioWPatch |
| Database | SQLite |
| Email | yagmail |
| PDF export | fpdf2 |
| Charts | Plotly |
