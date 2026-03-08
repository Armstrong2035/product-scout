import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from app.services.shopify_service import ShopifyService
from app.services.vector_service import VectorService
import google.generativeai as genai

class IndexerService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        
    def clean_product_data(self, raw_products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transforms raw Shopify GraphQL product data into a clean text format for vectorization.
        """
        cleaned = []
        for p in raw_products:
            title = p.get("title", "")
            description_html = p.get("descriptionHtml", "") or ""
            body_text = description_html.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ").replace("<li>", "- ").replace("</li>", " ")
            tags = p.get("tags", [])
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            product_type = p.get("product_type", "")
            
            variant_edges = p.get("variants", {}).get("edges", [])
            variant_list = [v.get("node", {}) for v in variant_edges]
            variant_strings = [v.get("title", "") for v in variant_list if v.get("title", "").lower() != "default title"]
            variant_info = f" Variants: {', '.join(variant_strings)}." if variant_strings else ""
            
            metafield_edges = p.get("metafields", {}).get("edges", [])
            meta_strings = [f"{m.get('node', {}).get('key')}: {m.get('node', {}).get('value')}" for m in metafield_edges]
            meta_info = f" Metadata: {'; '.join(meta_strings)}." if meta_strings else ""
            
            content = f"Title: {title}. Type: {product_type}. Tags: {tag_str}.{variant_info}{meta_info} Description: {body_text}"
            
            item = {
                "id": p.get("id").split("/")[-1],
                "storefront_id": p.get("id"),
                "title": title,
                "handle": p.get("handle"),
                "content": content,
                "price": variant_list[0].get("price", "0.00") if variant_list else "0.00",
                "image_url": p.get("featuredImage", {}).get("url") if p.get("featuredImage") else None,
                "product_type": product_type,
                "tags": tag_str
            }
            cleaned.append(item)
        return cleaned

    async def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding via Gemini API."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document"
            )
        )
        return result["embedding"]

    async def run_indexing_pipeline(self, site_id: Optional[str] = None, admin_access_token: Optional[str] = None):
        """
        Automated pipeline: Extract -> Clean -> Vectorize (Gemini) -> Push to Pinecone
        """
        # Fallback to env if site_id not provided
        target_site = site_id or os.getenv("SHOPIFY_SHOP_URL")
        
        shopify = ShopifyService(shop_url=target_site, admin_access_token=admin_access_token)
        current_site = shopify.shop_url
        
        if not current_site:
            print("[INDEXER] Error: No site_id provided or found in environment.")
            return 0
            
        print(f"[INDEXER] Starting extraction for site '{current_site}'...")
        raw_products = await shopify.fetch_all_products_graphql()
        
        if not raw_products:
            return 0
            
        clean_data = self.clean_product_data(raw_products)
        
        # 3. Vectorize and Push to Pinecone
        vector_service = VectorService()
        print(f"[INDEXER] Generating Gemini embeddings for {len(clean_data)} products...")
        pinecone_vectors = []
        
        for item in clean_data:
            try:
                # Cloud Embeddings
                vector = await self._get_embedding(item["content"])
                
                pinecone_vectors.append({
                    "id": item["id"],
                    "values": vector,
                    "metadata": {
                        "title": item["title"],
                        "handle": item["handle"],
                        "description": item["content"],
                        "storefront_id": item["storefront_id"],
                        "price": str(item["price"]),
                        "image_url": item["image_url"] or "",
                        "product_type": item["product_type"] or "",
                        "tags": item["tags"] or ""
                    }
                })
            except Exception as e:
                print(f"[INDEXER ERROR] Failed to embed product {item['id']}: {e}")
            
        if pinecone_vectors:
            vector_service.upsert_vectors(pinecone_vectors, namespace=current_site)
            print(f"[INDEXER] Pipeline complete! Pushed {len(pinecone_vectors)} products to Pinecone for '{current_site}'.")
        
        return len(pinecone_vectors)
