import asyncio
import os
from dotenv import load_dotenv
from app.services.shopify_service import ShopifyService

# Load .env file
load_dotenv()

async def test_metafields():
    print("--- Testing Metafield Access ---")
    service = ShopifyService()
    
    # Use the first product ID we found earlier (Gift Card)
    sample_product_id = "9441885585625"
    
    print(f"Testing Product ID: {sample_product_id}")
    
    try:
        metafields = await service.fetch_product_metafields(sample_product_id)
        print(f"\n[SUCCESS] Found {len(metafields)} metafields.")
        
        if metafields:
            for m in metafields:
                print(f"- Namespace: {m.get('namespace')}, Key: {m.get('key')}, Value: {m.get('value')}")
        else:
            print("\n[INFO] No metafields found for this product. This is normal if you haven't added any custom fields yet.")
            
    except Exception as e:
        print(f"\n[ERROR] Metafield fetch failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_metafields())
