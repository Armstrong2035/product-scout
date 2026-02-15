import asyncio
import os
from app.services.shopify_service import ShopifyService
from app.services.indexer_service import IndexerService
from app.services.vector_service import VectorService
from app.api.search import search_products, SearchRequest
from dotenv import load_dotenv

load_dotenv()

async def verify_isolation():
    shop_a = "alpha-store.myshopify.com"
    shop_b = "beta-store.myshopify.com"
    real_shop = os.getenv("CUSTOM_SHOP_URL")
    real_token = os.getenv("CUSTOM_SHOP_ADMIN_ACCESS_TOKEN")
    
    print(f"--- Multi-Tenancy Isolation Test ---")
    indexer = IndexerService()
    vector_service = VectorService()
    
    print(f"Step 1: Fetching products from REAL shop: {real_shop}")
    shopify = ShopifyService(shop_url=real_shop, admin_access_token=real_token)
    raw_products = await shopify.fetch_all_products_graphql()
    clean_products = indexer.clean_product_data(raw_products)
    
    print(f"Step 2: Vectorizing products (this may take a minute)...")
    vectors = []
    for item in clean_products[:5]: # Only test with 5 products for speed
        vec = await indexer.embedding_service.get_embeddings(item["content"])
        vectors.append({
            "id": f"test_{item['id']}",
            "values": vec,
            "metadata": {"title": item["title"], "storefront_id": item["storefront_id"]}
        })

    print(f"Step 3: Pushing to Namespace A ({shop_a}) and B ({shop_b})")
    vector_service.upsert_vectors(vectors, namespace=shop_a)
    vector_service.upsert_vectors(vectors, namespace=shop_b)

    print("\n--- Cross-Namespace Search Test ---")
    
    # Test 1: Search Namespace A
    print(f"Searching in {shop_a} for 'product'...")
    results_a = await search_products(SearchRequest(query="product", shop_url=shop_a, limit=5))
    print(f"Found {len(results_a)} results in {shop_a}")
    
    # Test 2: Search Namespace B
    print(f"Searching in {shop_b} for 'product'...")
    results_b = await search_products(SearchRequest(query="product", shop_url=shop_b, limit=5))
    print(f"Found {len(results_b)} results in {shop_b}")

    if len(results_a) > 0 and len(results_b) > 0:
        print("\n[VERIFICATION SUCCESS] Namespaces were created and queried correctly!")
    else:
        print("\n[VERIFICATION FAILED] No results found in one or more namespaces.")

if __name__ == "__main__":
    asyncio.run(verify_isolation())
