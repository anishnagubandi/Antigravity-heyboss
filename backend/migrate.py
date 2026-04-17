import json
import os
from supabase import create_client, Client

url = os.getenv("SUPABASE_URL", "https://sleybsliggdcddwwqvdl.supabase.co")
key = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNsZXlic2xpZ2dkY2Rkd3dxdmRsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYwODQyNDgsImV4cCI6MjA5MTY2MDI0OH0.zrIeQ3EOu2F7xyoO6aJu8Jq1DsMjLSpZbuaccInEH-8")
supabase: Client = create_client(url, key)

def migrate():
    print("Reading local db.json...")
    try:
        with open("db.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("db.json not found. Nothing to migrate.")
        return
    except Exception as e:
        print("Error reading db.json:", e)
        return

    users = data.get("users", [])
    schedules = data.get("schedules", [])
    
    print(f"Found {len(users)} users and {len(schedules)} schedule items.")

    for user in users:
        print(f"Migrating user: {user.get('name')}...")
        try:
            supabase.table("users").upsert(user).execute()
        except Exception as e:
            print(f"Error migrating user {user.get('name')}: {e}")
            
    for sched in schedules:
        print(f"Migrating schedule item: {sched.get('medication')}...")
        try:
            supabase.table("schedules").upsert(sched).execute()
        except Exception as e:
            print("Error migrating schedule:", e)

    print("Migration execution completed!")

if __name__ == "__main__":
    migrate()
