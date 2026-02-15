import asyncio
import os
import httpx
from app.services.database_service import DatabaseService
from app.services.indexer_service import IndexerService
from dotenv import load_dotenv

load_dotenv()

async def provision_store_manually(shop_url: str, admin_token: str):
    """
    Manually onboards a store into the Multi-Tenancy engine.
    Bypasses the OAuth web flow for rapid testing.
    """
    print(f"--- Provisioning Store: {shop_url} ---")
    db = DatabaseService()
    
    # 1. Generate Storefront Token (Optional but good)
    print("Generating Storefront Token...")
    storefront_token = None
    sf_url = f"https://{shop_url}/admin/api/2024-01/storefront_access_tokens.json"
    
    async with httpx.AsyncClient() as client:
        try:
            sf_response = await client.post(
                sf_url, 
                headers={"X-Shopify-Access-Token": admin_token}, 
                json={"storefront_access_token": {"title": "Product Scout Manual Sync"}}
            )
            if sf_response.status_code == 201:
                storefront_token = sf_response.json().get("storefront_access_token", {}).get("access_token")
                print(f"[SUCCESS] Storefront Token: {storefront_token}")
        except Exception as e:
            print(f"[SKIP] Storefront token generation failed: {e}")

    # 2. Register in Supabase
    print("Registering in Supabase Registry...")
    merchant_data = {
        "shop_url": shop_url,
        "access_token": admin_token,
        "storefront_token": storefront_token,
        "credits_balance": 500, # Large testing balance
        "plan_level": "pro"
    }
    
    success = await db.save_merchant(merchant_data)
    if success:
        print(f"[SUCCESS] {shop_url} is now in the Registry.")
    else:
        print(f"[FAIL] Could not save to Supabase.")
        return

    # 3. Trigger Indexing Pipeline (Isolated Namespace)
    print(f"Triggering indexing for namespace '{shop_url}'...")
    indexer = IndexerService()
    count = await indexer.run_indexing_pipeline(shop_url, admin_token)
    
    print(f"\n--- PROVISIONING COMPLETE ---")
    print(f"Store: {shop_url}")
    print(f"Products Secretly Partitioned: {count}")
    print(f"Ready for isolated search tests!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python provision_store.py <shop_url> <admin_token>")
        print("Example: python provision_store.py store1.myshopify.com shpat_123456")
    else:
        shop = sys.argv[1]
        token = sys.argv[2]
        asyncio.run(provision_store_manually(shop, token))
