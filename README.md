# Antigravity - HeyBoss

Lightweight medication reminder web app (backend API + simple frontend). Backend is a FastAPI app that serves the frontend and exposes REST endpoints and real-time WebSocket notification support. The project optionally integrates with Supabase (required for persistence and auth) and Gemini/Generative AI for prescription parsing when configured.

**Features:**
- User registration and login (Supabase Auth)
- Save, retrieve, and delete medication schedules
- Log medication taken/ missed entries
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
- Supabase project (recommended) with `SUPABASE_URL` and `SUPABASE_KEY` if you want persistence/auth
- (Optional) `gh` CLI authenticated if you use GitHub automation

Quickstart (local)

1) Create and activate a virtual environment:

   python -m venv .venv
   .\.venv\Scripts\activate    # Windows PowerShell

2) Install backend dependencies:

   pip install -r backend/requirements.txt

3) Create a `.env` file in `backend/` with the following (example):

   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-service-role-or-api-key
   GEMINI_API_KEY=sk-...      # optional, only if using AI features

4) Run the backend (from repo root):

   cd backend
   python main.py

   The app will run on `http://0.0.0.0:8000` and serve the frontend at `/`.

How to use (basic)
- Open `http://localhost:8000` in your browser to load the frontend.
- Register a new user (or sign in) — registration uses Supabase Auth and writes profile data to `profiles`.
- Use the schedule UI to add medication entries (time, medication, frequency). The backend saves them to the `schedules` table.
- When a scheduled time is reached the server attempts to push a JSON payload over WebSocket/SSE to connected clients.

Developer notes
- The backend entrypoint is `backend/main.py` and mounts `frontend/` as static files.
- Scheduling is implemented via `apscheduler` if available; the `med_time_job` checks `schedules` and calls `push_notification()`.
- Supabase client initialization is optional at import-time — the app will raise 503 for DB routes if `SUPABASE_URL`/`SUPABASE_KEY` are not set.
- To enable Gemini/AI features install the `google-generativeai` SDK and set `GEMINI_API_KEY`.

Testing & troubleshooting
- Check backend logs for scheduler and Supabase connection messages.
- If you hit CORS or auth issues, verify your Supabase keys and that the `profiles`/`schedules`/`daily_logs` tables exist.

License
- See `LICENSE` in repository root.

Questions or next steps
- I can add a short `Makefile`/PowerShell run script, CI workflow, or expand the frontend README. Which would you like next?
