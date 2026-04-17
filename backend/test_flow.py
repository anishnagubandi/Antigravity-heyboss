# backend/test_flow.py
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_flow():
    timestamp = int(time.time())
    email = f"test_{timestamp}@example.com"
    user = {
        "name": "Test User",
        "email": email,
        "password": "Password123!",
        "phone": "1234567890",
        "reminder_opt": True
    }
    
    print(f"--- 1. Testing Registration for {email} ---")
    reg_res = requests.post(f"{BASE_URL}/api/register", json=user)
    print(f"Status: {reg_res.status_code}")
    print(f"Response: {reg_res.text}")
    
    if reg_res.status_code != 200:
        print("Registration failed/requires confirmation. Skipping further tests.")
        return

    user_info = reg_res.json()["user"]
    user_id = user_info["user_id"]
    print(f"Registration Successful! User ID: {user_id}")

    print("\n--- 2. Testing Schedule Save ---")
    item = {
        "medication": "Vitamin C",
        "frequency": "daily",
        "time": "10:00",
        "instructions": "Take after breakfast"
    }
    save_res = requests.post(f"{BASE_URL}/api/save_schedule", json={"user_id": user_id, "schedule": [item]})
    print(f"Status: {save_res.status_code}")
    
    print("\n--- 3. Testing Schedule Retrieval ---")
    get_res = requests.get(f"{BASE_URL}/api/schedule/{user_id}")
    print(f"Status: {get_res.status_code}")
    schedule = get_res.json().get("schedule", [])
    print(f"Items: {len(schedule)}")

    print("\n--- 4. Testing Medication Intake Logging ---")
    log_res = requests.post(f"{BASE_URL}/api/logs", json={"user_id": user_id, "medication": "Vitamin C", "status": "taken"})
    print(f"Status: {log_res.status_code}")
    print(f"Response: {log_res.text}")

    print("\n--- 5. Testing Schedule Item Deletion ---")
    del_res = requests.delete(f"{BASE_URL}/api/schedule/{user_id}/Vitamin%20C/10:00")
    print(f"Status: {del_res.status_code}")

    print("\n--- Final Check: Schedule should be empty ---")
    final_res = requests.get(f"{BASE_URL}/api/schedule/{user_id}")
    print(f"Final Count: {len(final_res.json().get('schedule', []))}")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        print(f"Test crashed: {e}")
