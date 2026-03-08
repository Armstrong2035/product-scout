import requests
import json
import sys

def test_raw_stream(query="shoes"):
    url = "http://localhost:8000/search"
    payload = {
        "query": query,
        "shop_url": "eniolas-sports-store.myshopify.com",
        "session_id": "terminal-test-session",
        "limit": 5
    }

    print(f"Connecting to {url}...")
    print(f"Payload: {json.dumps(payload)}\n")
    print("-" * 50)
    print("RAW SSE STREAM OUTPUT:")
    print("-" * 50)

    try:
        response = requests.post(url, json=payload, stream=True)
        for line in response.iter_lines():
            if line:
                # Print the exact raw line received
                print(line.decode('utf-8'))
                sys.stdout.flush()
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    query_param = sys.argv[1] if len(sys.argv) > 1 else "shoes"
    test_raw_stream(query_param)
