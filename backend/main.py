# backend/main.py
import os
import json
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Optional integrations (user will need to provide keys later via .env)
# Using mock/stub where keys are absent so the app runs out of the box
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from supabase import create_client, Client
except ImportError:
    Client = None

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    Bot = None

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:
    AsyncIOScheduler = None

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("[Lifespan] Starting up medication scheduler...")
    if AsyncIOScheduler:
        scheduler = AsyncIOScheduler()
        # Mocking to run every 1 minute for testing
        scheduler.add_job(morning_job, 'cron', hour=6, minute=0)
        scheduler.add_job(eod_job, 'cron', hour=22, minute=52)
        scheduler.add_job(med_time_job, 'interval', minutes=1)
        scheduler.start()
        print("[Lifespan] Scheduler started.")
    
    if telegram_app:
        asyncio.create_task(start_telegram())
        print("[Lifespan] Telegram task initialized.")
    
    yield
    # Shutdown logic
    print("[Lifespan] Shutting down...")

app = FastAPI(lifespan=lifespan)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "mock-key")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "mock-token")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "mock-gemini")

if genai and GEMINI_API_KEY != "mock-gemini":
    genai.configure(api_key=GEMINI_API_KEY)

# Supabase init (mocked if invalid URL)
supabase: Client = None
if Client and "mock" not in SUPABASE_URL:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DB_FILE = "db.json"
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        mock_db = json.load(f)
else:
    mock_db = {
        "users": [],
        "schedules": [],
        "daily_logs": []
    }

def save_mock_db():
    with open(DB_FILE, "w") as f:
        json.dump(mock_db, f, indent=4)

# --- Real-Time SSE & WebSocket Registry ---
# Maps user_id -> list of active WebSockets
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"[WebSocket] User {user_id} connected. Active connections for user: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            print(f"[WebSocket] Pushing message to user {user_id} on {len(self.active_connections[user_id])} sockets")
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)
        else:
            print(f"[WebSocket] No active sockets for user {user_id}")

manager = ConnectionManager()

# Kept for backward compatibility if needed, but we prefer manager.send_personal_message
sse_queues: dict[str, asyncio.Queue] = {}

def get_user_queue(user_id: str) -> asyncio.Queue:
    if user_id not in sse_queues:
        sse_queues[user_id] = asyncio.Queue()
    return sse_queues[user_id]

async def push_notification(user_id: str, medication: str, scheduled_time: str, instructions: str):
    """Push a real-time notification event via WebSockets and SSE."""
    payload = json.dumps({
        "medication": medication,
        "time": scheduled_time,
        "instructions": instructions
    })
    
    # 1. WebSocket Push (New)
    await manager.send_personal_message(payload, user_id)
    
    # 2. SSE Push (Legacy/Fallback)
    if user_id in sse_queues:
        await sse_queues[user_id].put(payload)

# Telegram bot init
telegram_app = None
if Bot and TELEGRAM_TOKEN != "mock-token":
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

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
            # Keep connection alive
            data = await websocket.receive_text()
            # Handle incoming client messages if any
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)

# Static files routing
@app.get("/")
async def serve_index():
    return FileResponse("../frontend/index.html")

# API Routes
@app.post("/api/register")
async def register(req: RegisterReq):
    # Use uuid for unique user ID to avoid collisions in Supabase
    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    print(f"[DEBUG] Generated new user_id: {user_id}")
    user_data = {
        "user_id": user_id,
        "name": req.name,
        "email": req.email,
        "password": req.password, # In real app, hash this!
        "phone": req.phone,
        "reminder_opt": req.reminder_opt,
        "telegram_chat_id": None
    }
    
    if supabase:
        try:
            res = supabase.table("users").insert(user_data).execute()
            if res.data:
                user_data = res.data[0]
                user_id = user_data["user_id"]
        except Exception as e:
            print(f"[Registration Error] Supabase insert failed: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    else:
        mock_db["users"].append(user_data)
        save_mock_db()
        
    return {"user": {"user_id": user_id, "name": req.name, "email": req.email}}

@app.post("/api/login")
async def login(req: LoginReq):
    if supabase:
        res = supabase.table("users").select("*").eq("email", req.email).eq("password", req.password).execute()
        if not res.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user = res.data[0]
        return {"user": {"user_id": user["user_id"], "name": user["name"], "email": user["email"]}}
    else:
        for u in mock_db["users"]:
            if u["email"] == req.email and u["password"] == req.password:
                return {"user": {"user_id": u["user_id"], "name": u["name"], "email": u["email"]}}
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/parse_prescription")
async def parse_prescription(req: ParseReq):
    print("Incoming parse_prescription request! genai:", bool(genai), "key missing:", GEMINI_API_KEY == "mock-gemini")
    if genai and GEMINI_API_KEY != "mock-gemini":
        print("Using AI!")
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = f"""
            You are a medical scheduling assistant. The user is sending an update or new prescription.
            Current Schedule loaded in app: {req.current_schedule}
            Chat History memory: {req.chat_history}
            
            Process this new input: {req.prescription_text}
            
            Return ONLY a valid JSON list representing the updated schedule (or new schedule). 
            Each entry must have 'medication', 'time' (HH:MM 24h), 'frequency', and 'instructions'.
            """
            response = model.generate_content(prompt)
            # Find json block
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            schedule_data = json.loads(text.strip())
            
            # If AI wrapped the list in a dict, e.g. {"schedule": [...]}, extract it
            if isinstance(schedule_data, dict):
                # try to find the list
                for k, v in schedule_data.items():
                    if isinstance(v, list):
                        schedule_data = v
                        break
                # if still dict, make it a list
                if isinstance(schedule_data, dict):
                    schedule_data = [schedule_data]
            
            if not isinstance(schedule_data, list):
                schedule_data = []

            return {"schedule": schedule_data}
        except Exception as e:
            print(f"AI Errored out! {e}")
            raise HTTPException(status_code=500, detail=f"AI Error: {e}")
    else:
        print("Using MOCK logic!")
        # Enhanced Mock logic simulating memory and update logic
        text = req.prescription_text.lower()
        schedule = []
        is_update = "update" in text or "change" in text or "remove" in text
        
        if is_update and req.current_schedule:
            # Clone current schedule to mutate it
            schedule = list(req.current_schedule)
            if "liv52" in text and "10" in text:
                # Advanced mock simulation: changing Liv52 morning time to 10:00
                for s in schedule:
                    if "liv52" in s["medication"].lower() and "morning" in s["frequency"].lower():
                        s["time"] = "10:00"
            elif "remove d3" in text or "delete d3" in text:
                schedule = [s for s in schedule if "d3" not in s["medication"].lower()]
        else:
            # Fallback to general parsing
            if "liv52" in text or "liv 52" in text:
                schedule.append({"medication": "Liv52 Tablets", "time": "09:00", "frequency": "Daily (Morning)", "instructions": "Take after breakfast"})
                schedule.append({"medication": "Liv52 Tablets", "time": "21:00", "frequency": "Daily (Night)", "instructions": "Take after dinner"})
            if "d3" in text:
                schedule.append({"medication": "D3 Tablets", "time": "12:00", "frequency": "Once every 2 weeks", "instructions": "Take with meal"})
                
            if not schedule:
                import re
                match = re.search(r"tablet[s]? of\s+([a-zA-Z0-9_\-]+)\s+every\s+(\d+)\s+hours", text)
                if match:
                    med_name = match.group(1).capitalize()
                    hours = int(match.group(2))
                    schedule.append({"medication": f"{med_name} Tablet", "time": "08:00", "frequency": f"Every {hours} hours", "instructions": req.prescription_text})
                    if hours == 12:
                        schedule.append({"medication": f"{med_name} Tablet", "time": "20:00", "frequency": f"Every {hours} hours", "instructions": req.prescription_text})
                    elif hours == 8:
                        schedule.append({"medication": f"{med_name} Tablet", "time": "16:00", "frequency": f"Every {hours} hours", "instructions": req.prescription_text})
                        schedule.append({"medication": f"{med_name} Tablet", "time": "00:00", "frequency": f"Every {hours} hours", "instructions": req.prescription_text})
                else:
                    schedule.append({"medication": "Mock Fallback Med", "time": "09:00", "frequency": "Daily", "instructions": "Parsed from: " + req.prescription_text})
        
        return {"schedule": schedule}

@app.post("/api/save_schedule")
async def save_schedule(req: SaveScheduleReq):
    for item in req.schedule:
        item["user_id"] = req.user_id
        # Prevent Supabase schema errors if created_at is not a configured column
        db_item = dict(item)
        if "created_at" in db_item:
            db_item.pop("created_at")
            
        if supabase:
            supabase.table("schedules").insert(db_item).execute()
        else:
            mock_db["schedules"].append(item)
    
    if not supabase: save_mock_db()
    return {"status": "ok"}

@app.get("/api/schedule/{user_id}")
async def get_schedule(user_id: str):
    if supabase:
        res = supabase.table("schedules").select("*").eq("user_id", user_id).execute()
        return {"schedule": res.data}
    else:
        result = [s for s in mock_db["schedules"] if s["user_id"] == user_id]
        return {"schedule": result}

@app.delete("/api/schedule/{user_id}/{medication}/{time}")
async def delete_schedule(user_id: str, medication: str, time: str):
    print(f"[DEBUG] DELETE request: user={user_id}, med={medication}, time={time}")
    if supabase:
        try:
            res = supabase.table("schedules").delete().eq("user_id", user_id).eq("medication", medication).eq("time", time).execute()
            print(f"[DEBUG] Supabase delete response: {res}")
            return {"status": "ok"}
        except Exception as e:
            print(f"[DEBUG] Supabase delete error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Mock delete
        mock_db["schedules"] = [s for s in mock_db["schedules"] 
                                if not (s["user_id"] == user_id and s["medication"] == medication and s["time"] == time)]
        save_mock_db()
        return {"status": "ok"}


@app.get("/api/notifications/stream/{user_id}")
async def notification_stream(user_id: str):
    """Server-Sent Event stream. The browser connects once and then receives
    push messages from the server any time a scheduled medication time arrives."""
    queue = get_user_queue(user_id)
    print(f"[SSE] Client connected: user_id={user_id}")

    async def event_generator():
        try:
            while True:
                try:
                    # Wait for up to 25s, then send a keep-alive comment
                    payload = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Send SSE keep-alive so the browser does not close the connection
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            print(f"[SSE] Client disconnected: user_id={user_id}")
            # Clean up queue when client disconnects
            sse_queues.pop(user_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# Scheduler & Telegram logic
async def morning_job():
    print("[Cron] Running Customizable Morning Notification Job...")
    users = []
    if supabase:
        try:
            res = supabase.table("users").select("*").execute()
            if res.data: users = res.data
        except: pass
    else:
        users = mock_db["users"]
        
    for user in users:
        # Step 4 Requirement: customizable message based on previous day
        # Here we mock retrieving previous day logs
        previous_day_successful = True 
        
        prompt = f"The user {user['name']} has a medication tracking app. Write a short, encouraging 2 sentence morning notification. Include a reminder to pack their medicines for today."
        if previous_day_successful:
            prompt += " Also congratulate them for taking all their medications yesterday!"
        else:
            prompt += " Gently remind them that they missed some medications yesterday and encourage them they can do it today."
            
        custom_msg = "Good morning! Don't forget your medications today."
        if genai and GEMINI_API_KEY != "mock-gemini":
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt)
                custom_msg = response.text.strip()
            except Exception as e:
                print(f"[AI Error] {e}")
        else:
            custom_msg = "[Mocked AI] " + custom_msg
            
        print(f"\n[Morning Scheduler] -> User: {user['name']}, Phone: {user.get('phone')}")
        print(f"Message Body:\n{custom_msg}\n")
        
        if telegram_app and user.get('telegram_chat_id'):
            try:
                await telegram_app.bot.send_message(chat_id=user['telegram_chat_id'], text=custom_msg)
            except Exception as e:
                print(f"[Telegram error] {e}")

async def med_time_job():
    """Checks for medications due at the current time and pushes notifications."""
    # Calculate IST time dynamically (UTC + 5:30)
    utc_now = datetime.utcnow()
    # Calculate IST time dynamically (UTC + 5:30)
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%H:%M")
    today_date_str = ist_now.strftime("%Y-%m-%d")
    today_weekday = ist_now.weekday() # 0=Mon, 6=Sun
    
    # Gather all schedules (from mock DB or Supabase)
    all_schedules = []
    if supabase:
        try:
            res = supabase.table("schedules").select("*").execute()
            if res.data:
                all_schedules = res.data
        except Exception as e:
            print(f"[MedTimer] Supabase error fetching schedules: {e}")
    else:
        all_schedules = mock_db["schedules"]

    for s in all_schedules:
        s_time = s.get("time") # Expecting "HH:MM"
        if s_time == now_str:
            # Match Logic:
            # 1. Frequency is "daily"
            # 2. specific_date matches today
            # 3. today_weekday is in recurring_days list
            is_daily = s.get("frequency") == 'daily'
            is_specific = s.get("specific_date") == today_date_str
            is_recurring = s.get("recurring_days") and (today_weekday in s.get("recurring_days"))

            if is_daily or is_specific or is_recurring:
                user_id = s.get("user_id")
                medication = s.get("medication", "")
                instructions = s.get("instructions", "")
                print(f"[MedTimer] MATCH FOUND! Pushing notification for med={medication} to user={user_id}")
                await push_notification(user_id, medication, now_str, instructions)

            # Also send Telegram if linked
            if telegram_app:
                # Need to find the user's telegram_chat_id
                target_user = None
                if supabase:
                    userData = supabase.table("users").select("*").eq("user_id", user_id).execute()
                    if userData.data: target_user = userData.data[0]
                else:
                    for u in mock_db["users"]:
                        if u["user_id"] == user_id:
                            target_user = u
                            break
                
                if target_user and target_user.get("telegram_chat_id"):
                    try:
                        await telegram_app.bot.send_message(
                            chat_id=target_user["telegram_chat_id"],
                            text=f"🔔 Reminder: Time to take your {medication}! Instructions: {instructions or 'N/A'}"
                        )
                    except Exception as e:
                        print(f"[Telegram error] {e}")

async def eod_job():
    print("[Cron] Running End of Day Summary...")

async def start_telegram():
    if telegram_app:
        try:
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling()
            print("[Lifespan] Telegram polling started.")
        except Exception as e:
            print(f"[Lifespan] Telegram failed to start: {e}. Continuing without Telegram.")

# Re-mount static files with absolute path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "frontend"))
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.normpath(os.path.join(BASE_DIR, "frontend"))

print(f"[System] Mounting frontend from: {FRONTEND_DIR}")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # Added reload=True so you don't have to restart the server every time we change code!
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
