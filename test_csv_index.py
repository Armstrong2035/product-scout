"""
Test script: reads shopify_products.csv, embeds each product,
and saves them to your Qdrant instance under a mock site_id.
Run on the VPS: docker compose exec api python test_csv_index.py
"""
import asyncio
import csv
import os
from dotenv import load_dotenv
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService

load_dotenv()

MOCK_SITE_ID = "test-store.myshopify.com"
CSV_FILE = "shopify_products.csv"

async def main():
    print(f"--- CSV Indexing Test ---")
    print(f"Site ID: {MOCK_SITE_ID}")
    print(f"Reading: {CSV_FILE}\n")

    embedding_svc = EmbeddingService()
    qdrant_svc = QdrantService()

    # Drop existing collection — required when changing embedding model/vector size
    print("Dropping existing collection to recreate with new vector dimensions...")
    qdrant_svc.delete_collection()

    # Read products from CSV
    products = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)

    print(f"Found {len(products)} products in CSV.\n")

    points = []
    for i, product in enumerate(products):
        product_id = product.get("id", "").strip()
        title = product.get("title", "").strip()
        content = product.get("content", "").strip()
        handle = product.get("handle", "").strip()
        storefront_id = product.get("storefront_id", "").strip()

        if not product_id or not content:
            print(f"  [SKIP] Row {i+1}: missing id or content")
            continue

        print(f"  [{i+1}/{len(products)}] Embedding: {title}...")
        vector = await embedding_svc.get_embeddings(content)

        points.append({
            "id": int(product_id) if product_id.isdigit() else abs(hash(product_id)) % (2**31),
            "vector": vector,
            "metadata": {
                "title": title,
                "handle": handle,
                "storefront_id": storefront_id,
                "description": content[:500],
                "price": product.get("price", ""),
                "image_url": product.get("image_url", ""),
                "product_type": product.get("product_type", ""),
                "tags": product.get("tags", ""),
            }
        })

    if not points:
        print("\n[ERROR] No products to index.")
        return

    print(f"\nPushing {len(points)} products to Qdrant...")
    qdrant_svc.upsert_vectors(points, site_id=MOCK_SITE_ID)
    print(f"\n[SUCCESS] Indexed {len(points)} products under site_id='{MOCK_SITE_ID}'")
    print(f"\nVerify at: http://YOUR_DROPLET_IP:6333/dashboard")
    print(f"Or search with:")
    print(f'  curl -X POST http://localhost:8000/search -H "Content-Type: application/json" -d \'{{"query": "snowboard", "site_id": "{MOCK_SITE_ID}"}}\'')


if __name__ == "__main__":
    asyncio.run(main())
