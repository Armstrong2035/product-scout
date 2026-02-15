import asyncio
import os
import httpx
from dotenv import load_dotenv

# Load .env file
load_dotenv()

async def check_scopes():
    print("--- Checking Shopify Access Scopes ---")
    shop_url = os.getenv("CUSTOM_SHOP_URL") or os.getenv("SHOPIFY_SHOP_URL")
    access_token = os.getenv("CUSTOM_SHOP_ADMIN_ACCESS_TOKEN")
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-01")
    
    if not shop_url or not access_token:
        print("[ERROR] Shopify credentials not configured in .env")
        return

    url = f"https://{shop_url}/admin/oauth/access_scopes.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                scopes = response.json().get("access_scopes", [])
                print("\nGranted Scopes:")
                for s in scopes:
                    print(f"- {s.get('handle')}")
                
                # Specifically check for metafields
                has_metafields = any(s.get('handle') == 'read_metafields' for s in scopes)
                print(f"\nMetafields Access: {'ENABLED' if has_metafields else 'DISABLED'}")
            else:
                print(f"[ERROR] Failed to fetch scopes: {response.text}")
                
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_scopes())
