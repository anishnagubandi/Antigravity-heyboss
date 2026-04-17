import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api"

def run_tests():
    print("Testing End-to-End API Flow...")
    unique_id = str(uuid.uuid4())[:8]
    email = f"test_{unique_id}@example.com"
    
    # 1. Register
    print(f"\n1. Registering user {email}...")
    reg_data = {
        "name": "Test User",
        "email": email,
        "password": "password123",
        "phone": "1234567890",
        "reminder_opt": True
    }
    res = requests.post(f"{BASE_URL}/register", json=reg_data)
    if res.status_code != 200:
        print(f"Register failed: {res.text}")
        return
    user_id = res.json()["user"]["user_id"]
    print(f"Registered successfully! User ID: {user_id}")
    
    # 2. Login
    print("\n2. Logging in...")
    log_data = {
        "email": email,
        "password": "password123"
    }
    res = requests.post(f"{BASE_URL}/login", json=log_data)
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
        return
    print("Logged in successfully!")
    
    # 3. Parse Prescription
    print("\n3. Testing AI Prescription Parse...")
    parse_data = {
        "prescription_text": "Take 2 tablets of Paracetamol every 12 hours"
    }
    res = requests.post(f"{BASE_URL}/parse_prescription", json=parse_data)
    if res.status_code != 200:
        print(f"Parse failed: {res.text}")
        return
    schedule_data = res.json()["schedule"]
    print("AI Parsed Schedule:")
    print(json.dumps(schedule_data, indent=2))
    
    # 4. Save Schedule
    print("\n4. Saving Schedule...")
    save_data = {
        "user_id": user_id,
        "schedule": schedule_data
    }
    res = requests.post(f"{BASE_URL}/save_schedule", json=save_data)
    if res.status_code != 200:
        print(f"Save failed: {res.text}")
        return
    print("Schedule saved successfully!")
    
    # 5. Get Schedule
    print("\n5. Retrieving Schedule...")
    res = requests.get(f"{BASE_URL}/schedule/{user_id}")
    if res.status_code != 200:
        print(f"Get Schedule failed: {res.text}")
        return
    retrieved = res.json()["schedule"]
    if len(retrieved) > 0:
        print("Schedule retrieved successfully, E2E Test Passed!")
    else:
        print("Schedule retrieve failed: Empty schedule!")

if __name__ == "__main__":
    run_tests()
