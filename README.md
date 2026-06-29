# MeetGenie

AI-powered meeting intelligence. Upload a recording or transcript and get a structured summary with speaker analytics, action items, decisions, and more.

## Features

- **Upload or record** — supports MP3, WAV, MP4, and TXT transcripts, plus live microphone + system audio capture
- **Transcription** — OpenAI Whisper with automatic speaker diarization via pyannote.audio
- **AI summarization** — Gemini extracts overview, action items, decisions, risks, questions, and follow-ups
- **Speaker analytics** — talk time, participation breakdown, per-speaker sentiment
- **Chat with your meeting** — ask questions about the transcript using Gemini
- **Export** — download as PDF, send via email, or save to history
- **Meeting history** — searchable database of all past summaries

## Project Structure

```
meetgenie/
├── app.py                  # Streamlit UI
├── core/
│   ├── processor.py        # Orchestrates transcription → summary → analytics
│   ├── transcriber.py      # Whisper transcription + speaker diarization
│   ├── summarizer.py       # Gemini summarization
│   ├── diarizer.py         # pyannote speaker diarization
│   ├── sentiment.py        # Per-segment sentiment analysis
│   ├── speaker_intelligence.py  # Talk time and participation stats
│   └── chat_with_meeting.py     # Gemini Q&A over transcript
├── recording/
│   ├── recording_manager.py     # Orchestrates recording threads
│   ├── audio_recorder.py        # Microphone capture
│   ├── system_audio_recorder.py # WASAPI loopback (Windows)
│   └── merge.py                 # ffmpeg audio mixing
└── services/
    ├── database.py         # SQLite meeting history
    ├── email_sender.py     # yagmail email delivery
    ├── pdf_exporter.py     # FPDF summary export
    └── gemini_client.py    # Shared Gemini API client
```

## Requirements

- Python 3.11
- ffmpeg on PATH
- Windows (for live system audio capture via WASAPI)

## Setup

```bash
# Clone and create virtual environment
git clone https://github.com/your-username/meetgenie.git
cd meetgenie
python -m venv .venv311
.venv311\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your API keys to .env
```

## Environment Variables

```env
GEMINI_API_KEY=your_gemini_api_key
HF_TOKEN=your_huggingface_token
EMAIL_ADDRESS=your_gmail_address
EMAIL_PASSWORD=your_gmail_app_password
```

- **GEMINI_API_KEY** — [Google AI Studio](https://aistudio.google.com/app/apikey)
- **HF_TOKEN** — [HuggingFace](https://huggingface.co/settings/tokens) (required for speaker diarization)
- **EMAIL_ADDRESS / EMAIL_PASSWORD** — Gmail + [App Password](https://myaccount.google.com/apppasswords) for email export

## Run

```bash
streamlit run app.py
```

## Tech Stack

| Component | Library |
|---|---|
| UI | Streamlit |
| Transcription | OpenAI Whisper |
| Diarization | pyannote.audio 3.1 |
| Summarization | Google Gemini 2.5 Flash |
| Sentiment | HuggingFace Transformers (RoBERTa) |
| Audio capture | sounddevice, pyaudiowpatch |
| Database | SQLite |
| PDF export | fpdf2 |
| Charts | Plotly |
