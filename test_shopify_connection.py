import asyncio
import os
from dotenv import load_dotenv
from app.services.shopify_service import ShopifyService

# Load .env file
load_dotenv()

async def test_connection():
    print("--- Testing Shopify Connection ---")
    service = ShopifyService()
    
    print(f"Shop URL: {service.shop_url}")
    print(f"Admin Token Configured: {'Yes' if service.admin_access_token else 'No'}")
    
    try:
        products = await service.fetch_all_products()
        print(f"\n[SUCCESS] Total products found: {len(products)}")
        
        if products:
            print("\nSample Product Data (First Item):")
            first = products[0]
            print(f"ID: {first.get('id')}")
            print(f"Title: {first.get('title')}")
            print(f"Handle: {first.get('handle')}")
            print(f"Variants Count: {len(first.get('variants', []))}")
        else:
            print("\n[WARNING] No products returned. Check if the store has products or if the token has 'read_products' scope.")
            
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
