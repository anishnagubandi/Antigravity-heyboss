# HeyBoss Recovery Supervision App

A comprehensive web application for managing medical prescriptions and automated daily medication schedules. 

## Core Workflow
1. **User Registration & Login**: Users create an account to persist their daily schedule across devices.
2. **Medication Management**: Users can manually add their medications to their routine specifying the medication name, frequency, explicit time (AM/PM formatting), and dosage instructions.
3. **Real-time Reminders**: When the exact scheduled time for a medication arrives, a notification pushes instantly to the connected dashboard web interface reminding the user to take what's prescribed.

## Technology Stack
- **Backend Components**: Python 3.x, FastAPI, APScheduler (for accurate notification triggering).
- **Communication Layer**: SSE (Server-Sent Events) for real-time web notifications.
- **Frontend Components**: Vanilla HTML5, CSS3, and JavaScript, preserving state in `localStorage`.
- **Database System**: Supabase hosted PostgreSQL database, with an automatic gracefully-degraded fallback to `db.json` local flat files if credentials are not present.

## Configuration & Environment

Create a `.env` file within the `backend/` directory to link up external services (optional but highly recommended):
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

## Running the System

### 1. Install Backend Dependencies
Ensure you have Python 3 installed. Navigate to the backend directory and install the necessary libraries:
```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the FastAPI Server
The backend serves both the API endpoints and the static frontend HTML files directly:
```bash
python main.py
```

### 3. Access the Application
Open your web browser and navigate to:
`http://localhost:8000`

Register a new profile, head to the dashboard to manually add a medication 1 minute into the future, and keep the browser window open to test the instantaneous desktop notification delivery!
