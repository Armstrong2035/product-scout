import asyncio
import os
from app.services.database_service import DatabaseService
from dotenv import load_dotenv

load_dotenv()

async def test_registry():
    print("--- Supabase Registry Test ---")
    db = DatabaseService()
    
    if not db.client:
        print("[FAIL] Supabase client not initialized. Check your keys in .env.")
        return

    test_shop = "test-store-antigravity.myshopify.com"
    
    # 1. Save Test Merchant
    print(f"Testing 'save_merchant' for {test_shop}...")
    success = await db.save_merchant({
        "shop_url": test_shop,
        "access_token": "shpat_test_token_123",
        "credits_balance": 100,
        "plan_level": "free"
    })
    
    if success:
        print("[PASS] save_merchant worked.")
    else:
        print("[FAIL] save_merchant failed.")
        return

    # 2. Get Test Merchant
    print(f"Testing 'get_merchant'...")
    merchant = await db.get_merchant(test_shop)
    if merchant and merchant["shop_url"] == test_shop:
        print(f"[PASS] Found merchant! Credits: {merchant['credits_balance']}")
    else:
        print("[FAIL] Could not retrieve merchant.")

    # 3. Update Credits
    print("Testing credit deduction (-10)...")
    success = await db.update_credits(test_shop, -10)
    if success:
        merchant = await db.get_merchant(test_shop)
        print(f"[PASS] Credits updated! New balance: {merchant['credits_balance']}")
    else:
        print("[FAIL] Credit update failed.")

if __name__ == "__main__":
    asyncio.run(test_registry())
