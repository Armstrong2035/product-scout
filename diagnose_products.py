import requests
import json

url = "http://localhost:8000/search"
payload = {
    "query": "gift ideas for runners",
    "shop_url": "eniolas-sports-store.myshopify.com",
    "session_id": "test",
    "limit": 5
}

response = requests.post(url, json=payload, stream=True)
for line in response.iter_lines():
    if line:
        decoded = line.decode('utf-8')
        if decoded.startswith("data: "):
            data = json.loads(decoded[6:])
            if data["type"] == "explanation":
                print(f"Explanation for Index {data['index']}:")
                # print first line of explanation to see what product it is
                print(data['explanation'].split('\n')[0])
                print("---")
