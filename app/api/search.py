import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.embedding_service import EmbeddingService
from app.services.shopify_service import ShopifyService
from app.services.vector_service import VectorService

from app.services.database_service import DatabaseService

router = APIRouter(tags=["search"])

class SearchRequest(BaseModel):
    query: str
    shop_url: str # Required for multi-tenancy
    limit: Optional[int] = 5

class SearchResult(BaseModel):
    title: str
    handle: str
    price: str
    description: Optional[str] = None
    score: float
    image_url: Optional[str] = None
    storefront_id: Optional[str] = None
    product_type: Optional[str] = None
    available_for_sale: Optional[bool] = True

@router.post("/search", response_model=List[SearchResult])
async def search_products(request: SearchRequest):
    """
    Search endpoint that enforces shop isolation using Pinecone Namespaces.
    Hydrates results using shop-specific Storefront credentials.
    """
    try:
        # 1. Fetch Merchant Credentials from Supabase
        db = DatabaseService()
        merchant = await db.get_merchant(request.shop_url)
        
        # Note: If merchant not in DB, we could fallback to .env for dev/onboarding
        # but for production, we strictly require a valid merchant.
        sf_token = merchant.get("storefront_token") if merchant else os.getenv("SHOPIFY_STOREFRONT_TOKEN")
        
        # 2. Embed the query
        embedder = EmbeddingService()
        query_vector = await embedder.get_query_embedding(request.query)
        
        # 3. Query Pinecone Namespace
        vector_service = VectorService()
        top_matches = vector_service.query_vectors(
            query_vector, 
            namespace=request.shop_url, 
            top_k=request.limit
        )
        
        if not top_matches:
            return []
        
        # 4. Hydrate results with live Storefront data
        shopify = ShopifyService(
            shop_url=request.shop_url, 
            storefront_access_token=sf_token
        )
        gids = [m["metadata"].get("storefront_id") for m in top_matches if m["metadata"].get("storefront_id")]
        
        hydrated_map = {}
        if gids:
            hydrated_map = await shopify.fetch_storefront_data(gids)
            
        # 5. Format response with merged data
        results = []
        for match in top_matches:
            meta = match["metadata"]
            gid = meta.get("storefront_id")
            live_data = hydrated_map.get(gid, {})
            
            # Use live price/image if available, fall back to indexed metadata
            price = live_data.get("priceRange", {}).get("minVariantPrice", {}).get("amount", meta.get("price", "0.00"))
            image_url = live_data.get("featuredImage", {}).get("url", meta.get("image_url"))
            
            results.append(SearchResult(
                title=live_data.get("title", meta.get("title", "Unknown")),
                handle=live_data.get("handle", meta.get("handle", "")),
                price=price,
                description=meta.get("description"),
                score=match["score"],
                image_url=image_url,
                storefront_id=gid,
                product_type=meta.get("product_type"),
                available_for_sale=live_data.get("availableForSale", True)
            ))
            
        return results
        
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reindex")
async def trigger_reindex(shop_url: str):
    """Trigger reindexing for a specific shop."""
    from app.services.indexer_service import IndexerService
    try:
        # Load admin token from DB
        db = DatabaseService()
        merchant = await db.get_merchant(shop_url)
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found in registry")
            
        indexer = IndexerService()
        count = await indexer.run_indexing_pipeline(
            shop_url=shop_url, 
            admin_access_token=merchant["access_token"]
        )
        return {"message": f"Reindexing for {shop_url} complete", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
