import asyncio
import csv
import os
from dotenv import load_dotenv
from app.services.shopify_service import ShopifyService
from app.services.indexer_service import IndexerService

# Load .env file
load_dotenv()

async def export_to_csv():
    print("--- Exporting Shopify Products to CSV ---")
    shopify = ShopifyService()
    indexer = IndexerService()
    
    try:
        # 1. Fetch raw products via GraphQL
        print("[1/3] Fetching products from Shopify (GraphQL)...")
        raw_products = await shopify.fetch_all_products_graphql()
        print(f"[1/3] Found {len(raw_products)} products.")
        
        if not raw_products:
            print("[ABORT] No products found to export.")
            return

        # 2. Clean data
        print("[2/3] Cleaning data...")
        clean_data = indexer.clean_product_data(raw_products)
        
        # 3. Save to CSV
        output_file = "shopify_products.csv"
        print(f"[3/3] Saving to {output_file}...")
        
        if clean_data:
            keys = clean_data[0].keys()
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(clean_data)
            
            print(f"\n[SUCCESS] Export complete! Created {output_file}")
        else:
            print("[ERROR] Cleaned data is empty.")
            
    except Exception as e:
        print(f"\n[ERROR] Export failed: {e}")

if __name__ == "__main__":
    asyncio.run(export_to_csv())
