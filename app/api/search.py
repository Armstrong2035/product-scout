import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.embedding_service import EmbeddingService
from app.services.shopify_service import ShopifyService
from app.services.vector_service import VectorService

router = APIRouter(tags=["search"])

class SearchRequest(BaseModel):
    query: str
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
    Natural language search endpoint for Shopify products.
    """
    try:
        # 1. Embed the query
        embedder = EmbeddingService()
        query_vector = await embedder.get_query_embedding(request.query)
        
        # 2. Query Pinecone
        vector_service = VectorService()
        top_matches = vector_service.query_vectors(query_vector, top_k=request.limit)
        
        if not top_matches:
            return []
        
        # 3. Hydrate results with live Storefront data
        shopify = ShopifyService()
        gids = [m["metadata"].get("storefront_id") for m in top_matches if m["metadata"].get("storefront_id")]
        
        hydrated_map = {}
        if gids:
            hydrated_map = await shopify.fetch_storefront_data(gids)
            
        # 4. Format response with merged data
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
async def trigger_reindex():
    """Trigger the full indexing pipeline."""
    from app.services.indexer_service import IndexerService
    try:
        indexer = IndexerService()
        count = await indexer.run_indexing_pipeline()
        return {"message": "Reindexing complete", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
