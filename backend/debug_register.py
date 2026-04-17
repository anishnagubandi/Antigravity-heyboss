import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('backend/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

if not url or not key:
    print("Missing Supabase credentials")
    exit(1)

sb = create_client(url, key)

print("--- Checking 'users' table ---")
try:
    res = sb.table('users').select('*').limit(1).execute()
    if res.data:
        print("Sample user columns:", res.data[0].keys())
    else:
        print("Users table is empty. Trying to fetch column names via RPC or error analysis...")
        # Try a dummy insert to see the error/missing columns
        dummy_user = {
            "user_id": "test_ping",
            "name": "Test",
            "email": "test@test.com",
            "password": "test",
            "phone": "000",
            "reminder_opt": True
        }
        res2 = sb.table('users').insert(dummy_user).execute()
        print("Insert success (unexpected):", res2.data)
        # cleanup
        sb.table('users').delete().eq('user_id', 'test_ping').execute()
except Exception as e:
    print("Capture Error:", e)

print("--- Checking 'schedules' table ---")
try:
    res = sb.table('schedules').select('*').limit(1).execute()
    if res.data:
        print("Sample schedule columns:", res.data[0].keys())
except Exception as e:
    print("Schedule Error:", e)
