# backend/main.py
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
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

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:
    AsyncIOScheduler = None

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("[Lifespan] Starting up medication scheduler...")
    if not supabase:
        print("[CRITICAL] Supabase client not initialized. Database features will fail.")
    
    if AsyncIOScheduler:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(morning_job, 'cron', hour=6, minute=0)
        scheduler.add_job(med_time_job, 'interval', minutes=1)
        scheduler.start()
        print("[Lifespan] Scheduler started.")
    
    yield
    print("[Lifespan] Shutting down...")

app = FastAPI(lifespan=lifespan)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "mock-gemini")

if genai and GEMINI_API_KEY != "mock-gemini":
    genai.configure(api_key=GEMINI_API_KEY)

# Supabase init - Strictly required
supabase: Client = None
if Client and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[Supabase] Init error: {e}")

def check_supabase():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection not available. Please check server logs.")

# --- Real-Time SSE & WebSocket Registry ---
from fastapi import WebSocket, WebSocketDisconnect

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
                await connection.send_text(message)

manager = ConnectionManager()
sse_queues: dict[str, asyncio.Queue] = {}

def get_user_queue(user_id: str) -> asyncio.Queue:
    if user_id not in sse_queues:
        sse_queues[user_id] = asyncio.Queue()
    return sse_queues[user_id]

async def push_notification(user_id: str, medication: str, scheduled_time: str, instructions: str):
    payload = json.dumps({"medication": medication, "time": scheduled_time, "instructions": instructions})
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
    reminder_opt: bool = True

class ParseReq(BaseModel):
    prescription_text: str
    chat_history: list = []
    current_schedule: list = []

class SaveScheduleReq(BaseModel):
    user_id: str
    schedule: list

class LogEntryReq(BaseModel):
    user_id: str
    medication: str
    status: str = "taken"

# WebSocket Route
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)

@app.get("/")
async def serve_index():
    return FileResponse("../frontend/index.html")

# API Routes
@app.post("/api/register")
async def register(req: RegisterReq):
    check_supabase()
    try:
        # 1. Sign up user in Supabase Auth
        auth_res = supabase.auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {
                "data": {"name": req.name}
            }
        })
        if not auth_res.user:
            raise HTTPException(status_code=400, detail="Auth registration failed")
        
        user_id = auth_res.user.id
        
        # 2. Add to profiles table
        profile_data = {
            "id": user_id,
            "name": req.name,
            "email": req.email,
            "phone": req.phone,
            "reminder_opt": req.reminder_opt
        }
        # We use upsert to ensure we don't crash if the trigger already created it
        supabase.table("profiles").upsert(profile_data).execute()
        
        return {"user": {"user_id": user_id, "name": req.name, "email": req.email}}
    except Exception as e:
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            error_msg = "Please check your email to confirm your account before logging in."
        elif "User already registered" in error_msg:
            error_msg = "This email is already registered. Please log in instead."
        raise HTTPException(status_code=400, detail=error_msg)

@app.post("/api/login")
async def login(req: LoginReq):
    check_supabase()
    try:
        res = supabase.auth.sign_in_with_password({"email": req.email, "password": req.password})
        if not res.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Fetch profile
        profile = supabase.table("profiles").select("*").eq("id", res.user.id).execute()
        name = profile.data[0]["name"] if profile.data else "User"
        
        return {"user": {"user_id": res.user.id, "name": name, "email": res.user.email}}
    except Exception as e:
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            error_msg = "Your email address has not been confirmed. Please check your inbox for a verification link."
        elif "Invalid login credentials" in error_msg:
            error_msg = "Invalid email or password."
        raise HTTPException(status_code=401, detail=error_msg)

@app.post("/api/save_schedule")
async def save_schedule(req: SaveScheduleReq):
    check_supabase()
    try:
        for item in req.schedule:
            item["user_id"] = req.user_id
            supabase.table("schedules").insert(item).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/schedule/{user_id}")
async def get_schedule(user_id: str):
    check_supabase()
    try:
        res = supabase.table("schedules").select("*").eq("user_id", user_id).execute()
        return {"schedule": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/schedule/{user_id}/{medication}/{time}")
async def delete_schedule(user_id: str, medication: str, time: str):
    check_supabase()
    try:
        supabase.table("schedules").delete().eq("user_id", user_id).eq("medication", medication).eq("time", time).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs")
async def log_medication(req: LogEntryReq):
    check_supabase()
    log_data = {
        "user_id": req.user_id,
        "medication": req.medication,
        "status": req.status,
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        supabase.table("daily_logs").insert(log_data).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def morning_job():
    pass

async def med_time_job():
    if not supabase: return
    
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%H:%M")
    today_date_str = ist_now.strftime("%Y-%m-%d")
    today_weekday = ist_now.weekday()
    
    try:
        res = supabase.table("schedules").select("*").execute()
        if res.data:
            for s in res.data:
                if s.get("time") == now_str:
                    is_match = s.get("frequency") == 'daily' or \
                               s.get("specific_date") == today_date_str or \
                               (s.get("recurring_days") and today_weekday in s.get("recurring_days"))
                    if is_match:
                        await push_notification(s["user_id"], s["medication"], now_str, s.get("instructions", ""))
    except Exception as e:
        print(f"[MedTimer] Job error: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "frontend"))
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
