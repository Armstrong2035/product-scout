import json
import os
import asyncio
from typing import List, Dict, Any
from app.services.shopify_service import ShopifyService
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService

class IndexerService:
    def __init__(self):
        self.kb_path = "data/product_kb.json"
        self.vector_path = "data/product_vectors.json"
        self.embedding_service = EmbeddingService()
        
    def clean_product_data(self, raw_products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transforms raw Shopify GraphQL product data into a clean text format for vectorization.
        Includes variants, metafields, and prepares for Storefront API hydration.
        """
        cleaned = []
        for p in raw_products:
            # Extract basic fields from GraphQL node
            title = p.get("title", "")
            description_html = p.get("descriptionHtml", "") or ""
            # Basic HTML stripping
            body_text = description_html.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ").replace("<li>", "- ").replace("</li>", " ")
            tags = p.get("tags", [])
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            product_type = p.get("product_type", "")
            
            # Variant enrichment (GraphQL nested structure)
            variant_edges = p.get("variants", {}).get("edges", [])
            variant_list = [v.get("node", {}) for v in variant_edges]
            variant_strings = []
            for v in variant_list:
                v_title = v.get("title", "")
                if v_title and v_title.lower() != "default title":
                    variant_strings.append(v_title)
            
            variant_info = f" Variants: {', '.join(variant_strings)}." if variant_strings else ""
            
            # Metafield enrichment (GraphQL nested structure)
            metafield_edges = p.get("metafields", {}).get("edges", [])
            metafield_list = [m.get("node", {}) for m in metafield_edges]
            meta_strings = []
            for m in metafield_list:
                meta_strings.append(f"{m.get('key')}: {m.get('value')}")
            
            meta_info = f" Metadata: {'; '.join(meta_strings)}." if meta_strings else ""
            
            # Create content string for embedding (The "Rich Data" Moat)
            content = f"Title: {title}. Type: {product_type}. Tags: {tag_str}.{variant_info}{meta_info} Description: {body_text}"
            
            # GID is already provided in GraphQL (e.g. gid://shopify/Product/123)
            storefront_gid = p.get("id")
            
            # Extract basic ID for legacy reasons if needed
            admin_id = storefront_gid.split("/")[-1] if storefront_gid else "0"
            
            item = {
                "id": admin_id,
                "storefront_id": storefront_gid,
                "title": title,
                "handle": p.get("handle"),
                "content": content,
                "price": variant_list[0].get("price", "0.00") if variant_list else "0.00",
                "image_url": p.get("featuredImage", {}).get("url") if p.get("featuredImage") else None,
                "product_type": product_type,
                "tags": tag_str,
                "metafields": meta_strings
            }
            cleaned.append(item)
        return cleaned

    async def run_indexing_pipeline(self):
        """
        Automated pipeline: Extract -> Clean -> Vectorize -> Save
        """
        shopify = ShopifyService()
        print("[INDEXER] Starting extraction from Shopify (GraphQL)...")
        raw_products = await shopify.fetch_all_products_graphql()
        
        print(f"[INDEXER] Extracted {len(raw_products)} products.")
        if not raw_products:
            print("[INDEXER WARNING] No products fetched. Check Shopify credentials or scopes.")
            return 0
            
        print("[INDEXER] Cleaning data...")
        clean_data = self.clean_product_data(raw_products)
        print(f"[INDEXER] Cleaned {len(clean_data)} products.")
        
        # Save raw clean data
        os.makedirs(os.path.dirname(self.kb_path), exist_ok=True)
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2)
            
        # 3. Vectorize and Push to Pinecone
        vector_service = VectorService()
        print(f"[INDEXER] Generating embeddings and syncing to Pinecone for {len(clean_data)} products...")
        pinecone_vectors = []
        
        for item in clean_data:
            try:
                vector = await self.embedding_service.get_embeddings(item["content"])
                
                # Pinecone expects { "id": "...", "values": [...], "metadata": {...} }
                pinecone_vectors.append({
                    "id": str(item["id"]),
                    "values": vector,
                    "metadata": {
                        "title": item["title"],
                        "handle": item["handle"],
                        "description": item["content"], # Storing the cleaned content as description
                        "storefront_id": item["storefront_id"],
                        "price": str(item["price"]),
                        "image_url": item["image_url"] or "",
                        "product_type": item["product_type"] or "",
                        "tags": item["tags"] or ""
                    }
                })
                await asyncio.sleep(0.1) # Basic throttling
            except Exception as e:
                print(f"[INDEXER ERROR] Failed to embed product {item['id']}: {e}")
            
        if pinecone_vectors:
            vector_service.upsert_vectors(pinecone_vectors)
            print(f"[INDEXER] Pipeline complete! Vectorized and pushed {len(pinecone_vectors)} products to Pinecone.")
        else:
            print("[INDEXER WARNING] No vectors were generated.")
            
        return len(pinecone_vectors)
