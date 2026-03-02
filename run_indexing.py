import asyncio
import os
from dotenv import load_dotenv
from app.services.indexer_service import IndexerService

# Load .env file
load_dotenv()

async def main():
    print("--- Starting Manual Indexing Job ---")
    site_id = os.getenv("SHOPIFY_SHOP_URL") # Try to get from .env
    
    if not site_id:
        print("[ERROR] SHOPIFY_SHOP_URL not found in .env. Please set it to your store domain (e.g. store.myshopify.com)")
        return

    try:
        indexer = IndexerService()
        count = await indexer.run_indexing_pipeline(site_id=site_id)
        print(f"\n[SUCCESS] Indexed {count} products for '{site_id}'.")
    except Exception as e:
        print(f"\n[ERROR] Indexing failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
