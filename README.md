# HeyBoss Recovery Supervision App

A comprehensive web application for managing medical prescriptions and automated daily medication schedules. 

## Core Workflow
1. **User Registration & Login**: Users create an account to persist their daily schedule across devices.
2. **Medication Management**: Users can manually add their medications to their routine specifying the medication name, frequency, explicit time (AM/PM formatting), and dosage instructions.
3. **Real-time Reminders**: When the exact scheduled time for a medication arrives, a notification pushes instantly to the connected dashboard web interface reminding the user to take what's prescribed.



Lightweight medication reminder web app (backend API + simple frontend). Backend is a FastAPI app that serves the frontend and exposes REST endpoints and real-time WebSocket notification support. The project optionally integrates with Supabase (required for persistence and auth) and Gemini/Generative AI for prescription parsing when configured.

**Features:**
- User registration and login (Supabase Auth)
- Save, retrieve, and delete medication schedules
- Log medication taken / missed entries
- Real-time notifications via WebSocket and Server-Sent Events (scheduler pushes reminders)
- Optional prescription parsing / AI integrations (Gemini) when API key present
- Simple static frontend served from `/frontend` (served by FastAPI)

**Repository layout**
- `backend/` — FastAPI application and helper scripts
- `frontend/` — static HTML/CSS/JS UI
- `ui.txt` — notes / UI mock

Prerequisites
- Python 3.10+ (or compatible)
- `pip` for installing Python dependencies
A lightweight medication reminder web app (backend API + simple frontend). The backend is a FastAPI service that serves the static frontend and exposes REST endpoints plus real-time notification support (WebSocket/SSE). Optional integrations: Supabase for persistence/auth and Gemini (Generative AI) for advanced prescription parsing.

---

## Quick overview

- Registration and login (via Supabase Auth)
- Create and manage medication schedules (time, frequency, instructions)
- Log medication taken/missed
- Real-time reminders delivered via WebSocket or SSE

## Tech stack

- Backend: Python, FastAPI (optional: APScheduler)
- Frontend: Plain HTML/CSS/JS (static, served by FastAPI)
- Persistence: Supabase Postgres (optional; app falls back if not configured)

## Repo layout

- `backend/` — FastAPI app and server code
- `frontend/` — static UI files
- `ui.txt` — notes / UI mock

## Prerequisites

- Python 3.10+
- `pip`
- (Recommended) Supabase project with `SUPABASE_URL` and `SUPABASE_KEY`

## Local quickstart

1) Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2) Install dependencies:

```powershell
pip install -r backend/requirements.txt
```

3) Add optional environment variables in `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-or-api-key
GEMINI_API_KEY=sk-...     # optional
```

4) Run the backend from the repo root:

```powershell
cd backend
python main.py
```

Open `http://localhost:8000` to view the frontend.

## Developer notes

- Entry point: `backend/main.py` (it mounts `frontend/` using `StaticFiles`).
- Scheduler: `med_time_job` (uses Supabase data and `apscheduler` when installed).
- If Supabase is not configured, DB-dependent routes return 503.

## Troubleshooting

- Check backend logs for Supabase and scheduler messages.
- Confirm Supabase keys and that tables `profiles`, `schedules`, and `daily_logs` exist if you use Supabase.

## License

See `LICENSE` at the repository root.
