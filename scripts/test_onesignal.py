# Quick test — validates OneSignal credentials and sends a test notification
# Usage: ONESIGNAL_APP_ID=xxx ONESIGNAL_API_KEY=xxx PYTHONUTF8=1 PYTHONPATH=. python scripts/test_onesignal.py

import os
import requests

APP_ID  = os.environ.get("ONESIGNAL_APP_ID", "")
API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")

if not APP_ID or not API_KEY:
    print("Set ONESIGNAL_APP_ID and ONESIGNAL_API_KEY env vars first")
    exit(1)

# Test send to yourself — replace with your OneSignal subscription ID
SUBSCRIPTION_ID = input("Enter your OneSignal subscription ID: ").strip()

payload = {
    "app_id": APP_ID,
    "include_subscription_ids": [SUBSCRIPTION_ID],
    "headings": {"en": "Price drop at Walmart!"},
    "contents": {"en": "Walmart has eggo frozen waffles for $2.87 — 20% below average across 21 retailers"},
    "data": {"deep_link": "/deals?source=new-deals-alert"},
}

res = requests.post(
    "https://api.onesignal.com/notifications",
    headers={"Authorization": f"Key {API_KEY}", "Content-Type": "application/json"},
    json=payload,
)
print(res.status_code, res.json())
