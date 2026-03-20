import os
import asyncio
from typing import List, Dict, Any
import cohere

class RerankService:
    """
    Wraps the Cohere Rerank v3.5 API.
    Takes a query and a list of candidate product documents, returns
    them reordered by semantic relevance with a score per document.
    """

    def __init__(self):
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in environment")
        self.client = cohere.Client(api_key=api_key)

    def _build_document_text(self, meta: Dict[str, Any]) -> str:
        """Serialize the product metadata fields we care about into a single string for the reranker."""
        parts = []
        if meta.get("title"):
            parts.append(f"Title: {meta['title']}")
        if meta.get("product_type"):
            parts.append(f"Type: {meta['product_type']}")
        if meta.get("description"):
            # Truncate long descriptions — Cohere has a token limit per doc
            desc = meta["description"][:500]
            parts.append(f"Description: {desc}")
        if meta.get("tags"):
            parts.append(f"Tags: {meta['tags']}")
        return " | ".join(parts)

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        """
        Rerank a list of Pinecone match dicts using Cohere.

        Args:
            query: The user's original search query.
            candidates: List of Pinecone matches [{'id', 'score', 'metadata'}].
            top_n: How many top results to return after reranking.

        Returns:
            Reranked subset of candidates, each enriched with:
              - 'rerank_score': Cohere relevance score (0–1)
              - 'rerank_highlights': list of matching snippet strings (may be empty on trial key)
        """
        if not candidates:
            return []

        documents = [self._build_document_text(c["metadata"]) for c in candidates]

        # Run the synchronous Cohere SDK call in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.rerank(
                model="rerank-english-v3.0",
                query=query,
                documents=documents,
                top_n=min(top_n, len(candidates)),
                return_documents=True,
            ),
        )

        reranked = []
        for result in response.results:
            original = candidates[result.index]
            highlights = []
            # Cohere returns highlighted snippets on paid tiers
            if result.document and hasattr(result.document, "snippets"):
                highlights = [s.text for s in (result.document.snippets or [])]

            reranked.append({
                **original,
                "rerank_score": result.relevance_score,
                "rerank_highlights": highlights,
            })

        return reranked
