import json
import httpx
import asyncio

async def test_stream():
    url = "http://localhost:8000/search"  # Adjust if your port is different
    payload = {
        "query": "waterproof hiking boots",
        "site_id": "photobooks-io.myshopify.com",
        "limit": 5
    }
    
    print(f"--- Sending Search Query: '{payload['query']}' ---")
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"Error: Server returned {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        event = data.get("event")
                        
                        if event == "products":
                            print("\n[STAGE 1: INSTANT RESULTS]")
                            for p in data["data"]:
                                print(f" - {p['handle']} (Score: {p['score']:.2f})")
                                
                        elif event == "refined":
                            print("\n[STAGE 2: RERANKED RESULTS]")
                            for p in data["data"]:
                                print(f" - {p['handle']} (Score: {p['score']:.2f})")
                                
                        elif event == "reasoning":
                            print("\n[STAGE 3: THE BRAIN'S REASONING]")
                            print(f"> {data['text']}")
                            
                        elif event == "empty":
                            print("\nNo results found.")
                        elif event == "error":
                            print(f"\nAPI Error: {data.get('message')}")
                            
    except Exception as e:
        print(f"\nConnection Error: {e}")
        print("Tip: Make sure your FastAPI server is running (uvicorn main:app --reload)")

if __name__ == "__main__":
    asyncio.run(test_stream())
