import json
import os
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.embedding_service import EmbeddingService
from app.services.shopify_service import ShopifyService
from app.services.qdrant_service import QdrantService
from app.services.database_service import DatabaseService
import google.generativeai as genai

router = APIRouter(tags=["search"])

class SearchRequest(BaseModel):
    query: str
    site_id: str 
    limit: Optional[int] = 5

async def generate_search_stream(request: SearchRequest):
    """
    SSE Generator for multi-stage search refinement.
    Decoupled: Returns IDs and Scores, letting client handle hydration.
    """
    try:
        # 1. Setup Services
        embedder = EmbeddingService()
        vector_service = QdrantService()

        # 2. Stage 1: Vector Search (Instant)
        query_vector = await embedder.get_query_embedding(request.query)
        top_matches = vector_service.query_vectors(
            query_vector, 
            site_id=request.site_id, 
            limit=15 # Get more for reranking
        )

        if not top_matches:
            yield f"data: {json.dumps({'event': 'empty'})}\n\n"
            return

        # Return minimal data for instant rendering/hydration start
        initial_results = []
        for match in top_matches[:5]:
            meta = match["metadata"]
            initial_results.append({
                "id": meta.get("storefront_id") or str(match["id"]),
                "handle": meta.get("handle"),
                "score": match["score"]
            })

        yield f"data: {json.dumps({'event': 'products', 'data': initial_results})}\n\n"

        # 3. Stage 2: Re-ranking (Refinement)
        reranked_matches = embedder.rerank(request.query, [
            {"id": m["id"], "description": m["metadata"].get("description", ""), "metadata": m["metadata"], "score": m["score"]} 
            for m in top_matches
        ])
        
        # Always return refined top 5 to ensure best accuracy
        refined_results = []
        for match in reranked_matches[:5]:
            meta = match["metadata"]
            refined_results.append({
                "id": meta.get("storefront_id") or str(match["id"]),
                "handle": meta.get("handle"),
                "score": match["rerank_score"]
            })
        yield f"data: {json.dumps({'event': 'refined', 'data': refined_results})}\n\n"

        # 4. Stage 3: AI Reasoning (The "Why")
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            top_3_titles = [m["metadata"].get("title") for m in reranked_matches[:3]]
            prompt = f"User: {request.query}\nProducts: {', '.join(top_3_titles)}\nExplain in 2 short sentences why these match."
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            yield f"data: {json.dumps({'event': 'reasoning', 'text': response.text.strip()})}\n\n"
        except Exception:
            pass # Reasoning is optional/fail-safe

    except Exception as e:
        print(f"[STREAM ERROR] {e}")
        yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    except Exception as e:
        print(f"[STREAM ERROR] {e}")
        yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

@router.post("/search")
async def search_products(request: SearchRequest):
    return StreamingResponse(generate_search_stream(request), media_type="text/event-stream")

@router.post("/reindex")
async def trigger_reindex(shop_url: str):
    """Trigger reindexing for a specific shop."""
    from app.services.indexer_service import IndexerService
    try:
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
