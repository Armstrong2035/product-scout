import json
import os
import time
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
    SSE Generator. Two events:
      1. 'products' — reranked product IDs/handles (fast)
      2. 'reasoning' — same products with per-product 'reason' field (after AI)
    
    Both events include '_ms' for latency profiling.
    """
    t_start = time.monotonic()

    try:
        embedder = EmbeddingService()
        vector_service = QdrantService()

        # Stage 1: Embed query + vector search + rerank
        query_vector = await embedder.get_query_embedding(request.query)
        top_matches = vector_service.query_vectors(
            query_vector,
            site_id=request.site_id,
            limit=15  # extra candidates for reranking
        )

        if not top_matches:
            yield f"data: {json.dumps({'event': 'empty'})}\n\n"
            return

        reranked = embedder.rerank(request.query, [
            {
                "id": m["id"],
                "description": m["metadata"].get("description", ""),
                "metadata": m["metadata"],
                "score": m["score"]
            }
            for m in top_matches
        ])

        top5 = reranked[:5]
        t_search_done = time.monotonic()

        # Emit products immediately (no reasons yet)
        products_payload = []
        for match in top5:
            meta = match["metadata"]
            products_payload.append({
                "id": meta.get("storefront_id") or str(match["id"]),
                "handle": meta.get("handle"),
                "score": match["rerank_score"]
            })

        yield f"data: {json.dumps({'event': 'products', 'data': products_payload, '_ms': round((t_search_done - t_start) * 1000)})}\n\n"

        # Stage 2: Per-product AI reasoning (single Gemini call)
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-2.5-flash")

            product_list = "\n".join([
                f"{i+1}. {m['metadata'].get('title', 'Unknown')}: {m['metadata'].get('description', '')[:200]}"
                for i, m in enumerate(top5)
            ])

            prompt = (
                f"You are a friendly, knowledgeable sales assistant helping a customer who searched for: \"{request.query}\".\n\n"
                f"Here are the top matching products:\n{product_list}\n\n"
                f"For each product, write a short, enthusiastic 1-sentence recommendation (max 20 words) "
                f"in a conversational sales tone — like you're talking directly to the customer, "
                f"highlighting why THIS product fits what they're looking for.\n\n"
                f"Examples of the right tone:\n"
                f"- \"If you want speed on groomed runs, this one's a no-brainer.\"\n"
                f"- \"Great pick for beginners — super forgiving and easy to control.\"\n"
                f"- \"This is the one serious riders keep coming back to.\"\n\n"
                f"Return ONLY valid JSON, no markdown:\n"
                f"{{\"1\": \"reason\", \"2\": \"reason\", \"3\": \"reason\", \"4\": \"reason\", \"5\": \"reason\"}}"
            )

            t_before_ai = time.monotonic()
            response = await asyncio.to_thread(model.generate_content, prompt)
            t_after_ai = time.monotonic()

            raw = response.text.strip()

            # Strip markdown code fences if present
            import re
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                explanations = json.loads(json_match.group())
            else:
                raise ValueError(f"No JSON found in response: {raw[:100]}")

            reasoned_payload = []
            for i, match in enumerate(top5):
                meta = match["metadata"]
                reasoned_payload.append({
                    "id": meta.get("storefront_id") or str(match["id"]),
                    "handle": meta.get("handle"),
                    "score": match["rerank_score"],
                    "reason": explanations.get(str(i + 1), "")
                })

            yield f"data: {json.dumps({'event': 'reasoning', 'data': reasoned_payload, '_ms': round((t_after_ai - t_start) * 1000)})}\n\n"

        except Exception as e:
            print(f"[REASONING ERROR] {e}")
            # Silently skip — products were already delivered

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
            site_id=shop_url, 
            admin_access_token=merchant["access_token"]
        )
        return {"message": f"Reindexing for {shop_url} complete", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
