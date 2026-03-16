import requests
import json

url = "http://localhost:8000/search"
payload = {
    "query": "shoes",
    "shop_url": "eniolas-sports-store.myshopify.com",
    "session_id": "diag-test",
    "limit": 2
}

print("Sending request...")
try:
    response = requests.post(url, json=payload, stream=True, timeout=30)
    print(f"HTTP Status: {response.status_code}")
    for i, line in enumerate(response.iter_lines()):
        if line:
            print(f"LINE {i}: {line.decode('utf-8')}")
        if i > 20:
            print("... (stopping after 20 lines)")
            break
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
