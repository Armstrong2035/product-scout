import json
import os
import time
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.database_service import DatabaseService
import google.generativeai as genai

router = APIRouter(tags=["search"])

# ── Models ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    shop_url: str  # Required for multi-tenancy
    session_id: str
    limit: Optional[int] = 5

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_llm_explanation_prompt(query: str, product: Dict[str, Any]) -> str:
    """
    Build a tightly scoped prompt for a SINGLE product.
    """
    meta = product["metadata"]
    product_context = (
        f"Product: \"{meta.get('title', 'Unknown')}\"\n"
        f"Type: {meta.get('product_type', 'N/A')}\n"
        f"Description: {(meta.get('description') or '')[:500]}\n"
        f"Score: {product['score']:.2f}"
    )

    return (
        f"A customer searched for: \"{query}\"\n\n"
        f"Context for the product found:\n{product_context}\n\n"
        f"You are an expert personal shopping concierge. Create a structured 'Why It Fits' breakdown for this product:\n"
        f"1. **The Hook**: One punchy sentence validating the search intent (e.g., 'This is the ultimate choice for high-intensity marathon training.').\n"
        f"2. **Technical Bullets**: Exactly THREE bullets mapping a `[Specific Material/Feature]` to a `[Real-world Outcome]`.\n"
        f"3. **Conclusion**: One short, confident closing recommendation.\n\n"
        f"FORMAT EXAMPLE:\n"
        f"This is the ultimate choice for high-intensity marathon training.\n"
        f"• Carbon-Fiber Plate: Provides explosive energy return to shave seconds off your pace.\n"
        f"• Engineered Mesh Upper: Ensures 360-degree breathability to prevent overheating on long runs.\n"
        f"• Reinforced Heel Counter: Delivers maximum stability for confident cornering at speed.\n"
        f"You will love how this pair empowers your peak performance.\n\n"
        f"CRITICAL RULES:\n"
        f"- Use exactly three bullets.\n"
        f"- Be technically precise based ONLY on the provided description.\n"
        f"- No generic marketing fluff.\n"
        f"- Respond ONLY with the text."
    )


async def _get_single_explanation(query: str, product: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Fires a single Gemini call for ONE product.
    Returns a dict with index and explanation.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"index": index, "explanation": ""}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = _build_llm_explanation_prompt(query, product)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt)
        )
        
        return {"index": index, "explanation": response.text.strip() if response.candidates else ""}
    except Exception as e:
        print(f"[LLM ERROR] Result {index}: {e}")
        return {"index": index, "explanation": ""}

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/search")
async def search_products(request: SearchRequest):
    """
    Streaming Search Pipeline (SSE):
      1. Immediate Stream: Deliver raw search results (IDs/scores) in <200ms.
      2. Background Phase: Execute concurrent individual LLM calls for justifications.
      3. Incremental Stream: Yield each justification as soon as it's ready.
    """
    start_time = time.monotonic()
    search_id = str(os.urandom(8).hex()) # Unique trace ID

    async def generate_search_stream():
        try:
            db = DatabaseService()
            # ── 1. Retrieval ──────────────────────────────────────────────────
            from app.services.vector_service import VectorService
            vector_service = VectorService()
            
            # Use raw Pinecone query for speed
            all_candidates = vector_service.query_vectors(
                request.query,
                namespace=request.shop_url,
                limit=request.limit or 5
            )

            if not all_candidates:
                yield f"data: {json.dumps({'type': 'empty'})}\n\n"
                return

            # ── 2. Immediate Delivery ─────────────────────────────────────────
            results = [
                {
                    "storefront_id": c["metadata"].get("storefront_id"),
                    "score": c["score"]
                }
                for c in all_candidates
            ]
            
            yield f"data: {json.dumps({'type': 'results', 'search_id': search_id, 'results': results})}\n\n"

            # ── 3. STAGE 2: Concurrent Justifications ─────────────────────────
            # Fire all LLM calls in parallel
            explanation_tasks = [
                _get_single_explanation(request.query, product, i)
                for i, product in enumerate(all_candidates)
            ]

            # Yield each explanation as soon as it finishes
            for task in asyncio.as_completed(explanation_tasks):
                result = await task
                yield f"data: {json.dumps({'type': 'explanation', 'index': result['index'], 'explanation': result['explanation']})}\n\n"

            # ── 4. Final Telemetry ─────────────────────────────────────────────
            latency_ms = int((time.monotonic() - start_time) * 1000)
            top_result_id = results[0]["storefront_id"] if results else None
            
            await db.log_search({
                "id": search_id,
                "shop_url": request.shop_url,
                "session_id": request.session_id,
                "query": request.query,
                "result_count": len(results),
                "top_result_id": top_result_id,
                "latency_ms": latency_ms
            })
            await db.increment_query_count(request.shop_url)

        except Exception as e:
            print(f"[STREAM ERROR] {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate_search_stream(), media_type="text/event-stream")


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
