# api/index.py
import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Optional integrations
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from supabase import create_client, Client
except ImportError:
    Client = None

# load_dotenv() removed to favor Vercel system environment variables

app = FastAPI()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "mock-key")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "mock-gemini")

if genai and GEMINI_API_KEY != "mock-gemini":
    genai.configure(api_key=GEMINI_API_KEY)

# Supabase init
supabase: Client = None
if Client and "mock" not in SUPABASE_URL:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Mock DB fallback (Note: This won't persist on Vercel)
mock_db = {
    "users": [],
    "schedules": [],
    "daily_logs": []
}

# --- Real-Time SSE & WebSocket Registry ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except:
                    pass

manager = ConnectionManager()
sse_queues: dict[str, asyncio.Queue] = {}

def get_user_queue(user_id: str) -> asyncio.Queue:
    if user_id not in sse_queues:
        sse_queues[user_id] = asyncio.Queue()
    return sse_queues[user_id]

async def push_notification(user_id: str, medication: str, scheduled_time: str, instructions: str):
    payload = json.dumps({
        "medication": medication,
        "time": scheduled_time,
        "instructions": instructions
    })
    await manager.send_personal_message(payload, user_id)
    if user_id in sse_queues:
        await sse_queues[user_id].put(payload)

# Models
class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str
    phone: str
    reminder_opt: bool

class ParseReq(BaseModel):
    prescription_text: str
    chat_history: list = []
    current_schedule: list = []

class SaveScheduleReq(BaseModel):
    user_id: str
    schedule: list

# WebSocket Route
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)

# API Routes
@app.post("/api/register")
async def register(req: RegisterReq):
    if not supabase:
        raise HTTPException(status_code=501, detail="Supabase required.")
    try:
        # Use native Supabase Auth to create the user
        auth_res = supabase.auth.sign_up({"email": req.email, "password": req.password})
        if not auth_res.user:
            raise HTTPException(status_code=400, detail="Sign up failed.")
        user_id = auth_res.user.id
        
        # Insert into profiles table (linked to auth.users)
        supabase.table("profiles").upsert({
            "user_id": user_id,
            "name": req.name,
            "phone": req.phone
        }).execute()
        
        return {"user": {"user_id": user_id, "name": req.name, "email": req.email}}
    except Exception as e:
        print(f"Registration Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/login")
async def login(req: LoginReq):
    if not supabase:
        raise HTTPException(status_code=501, detail="Supabase required.")
    try:
        # Use native Supabase Auth to sign in
        auth_res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        if not auth_res.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user_id = auth_res.user.id
        
        # Fetch name from profiles table
        profile_res = supabase.table("profiles").select("name, phone").eq("user_id", user_id).execute()
        name = profile_res.data[0]["name"] if profile_res.data else req.email
        
        return {"user": {"user_id": user_id, "name": name, "email": req.email}}
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/parse_prescription")
async def parse_prescription(req: ParseReq):
    if genai and GEMINI_API_KEY != "mock-gemini":
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"""
            You are a medical scheduling assistant. The user is sending an update or new prescription.
            Current Schedule: {req.current_schedule}
            Chat History: {req.chat_history}
            Input: {req.prescription_text}
            
            Return ONLY a valid JSON list of objects with: 'medication', 'time' (HH:MM), 'frequency', 'instructions'.
            """
            response = model.generate_content(prompt)
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            schedule_data = json.loads(text.strip())
            if isinstance(schedule_data, dict) and "schedule" in schedule_data:
                schedule_data = schedule_data["schedule"]
            return {"schedule": schedule_data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI Error: {e}")
    else:
        return {"schedule": [{"medication": "Sample Med", "time": "09:00", "frequency": "Daily", "instructions": "Take with water"}]}

@app.post("/api/save_schedule")
async def save_schedule(req: SaveScheduleReq):
    if not supabase:
        raise HTTPException(status_code=501, detail="Supabase required for saving.")
    
    try:
        for item in req.schedule:
            item["user_id"] = req.user_id
            # Mirror original logic: remove only created_at to avoid schema errors
            db_item = dict(item)
            db_item.pop("created_at", None)
            res = supabase.table("schedules").insert(db_item).execute()
            print(f"Schedule saved: {res.data}")
        return {"status": "ok"}
    except Exception as e:
        print(f"Save Schedule Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/schedule/{user_id}")
async def get_schedule(user_id: str):
    if supabase:
        res = supabase.table("schedules").select("*").eq("user_id", user_id).execute()
        return {"schedule": res.data}
    return {"schedule": []}

@app.delete("/api/schedule/{user_id}/{medication}/{time}")
async def delete_schedule(user_id: str, medication: str, time: str):
    if supabase:
        supabase.table("schedules").delete().eq("user_id", user_id).eq("medication", medication).eq("time", time).execute()
        return {"status": "ok"}
    raise HTTPException(status_code=501, detail="Supabase required.")

@app.get("/api/notifications/stream/{user_id}")
async def notification_stream(user_id: str):
    queue = get_user_queue(user_id)
    async def event_generator():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            sse_queues.pop(user_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Cron Endpoints ---

@app.get("/api/cron/morning")
async def morning_cron():
    if not supabase: return {"status": "no-db"}
    users = supabase.table("users").select("*").execute().data
    for user in users:
        print(f"Morning greeting for {user['name']}")
    return {"status": "ok", "users_processed": len(users)}

@app.get("/api/cron/check-meds")
async def check_meds_cron():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%H:%M")
    today_date_str = ist_now.strftime("%Y-%m-%d")
    today_weekday = ist_now.weekday()
    
    if not supabase: return {"status": "no-db"}
    
    schedules = supabase.table("schedules").select("*").execute().data
    matches = 0
    for s in schedules:
        if s.get("time") == now_str:
            is_daily = s.get("frequency") == 'daily'
            is_specific = s.get("specific_date") == today_date_str
            is_recurring = s.get("recurring_days") and (today_weekday in s.get("recurring_days"))

            if is_daily or is_specific or is_recurring:
                await push_notification(s["user_id"], s["medication"], now_str, s.get("instructions", ""))
                matches += 1
                
    return {"status": "ok", "matches_found": matches, "time_checked": now_str}
