import asyncio
from app.services.database_service import DatabaseService
from dotenv import load_dotenv

load_dotenv()

async def check_registry():
    db = DatabaseService()
    if not db.client:
        print("Supabase client not initialized. Check .env")
        return

    try:
        response = db.client.table("merchants").select("shop_url, created_at, storefront_token, credits_balance").execute()
        merchants = response.data
        
        if not merchants:
            print("No merchants found in the registry.")
        else:
            print(f"Verified {len(merchants)} Registered Merchant(s):")
            for m in merchants:
                has_sf = "YES" if m.get("storefront_token") else "NO"
                print(f"- {m['shop_url']} (Signed up: {m['created_at']}, Credits: {m['credits_balance']}, SF Token: {has_sf})")
                
    except Exception as e:
        print(f"Error checking registry: {e}")

if __name__ == "__main__":
    asyncio.run(check_registry())
