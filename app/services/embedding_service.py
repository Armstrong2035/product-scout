try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False
    print("[EMBEDDING] Warning: FastEmbed not found. Falling back to Mock Mode.")

try:
    from fastembed import TextCrossEncoder
    RERANKER_AVAILABLE = True
except ImportError:
    try:
        from fastembed.reranker.cross_encoder import TextCrossEncoder
        RERANKER_AVAILABLE = True
    except ImportError:
        RERANKER_AVAILABLE = False
        print("[EMBEDDING] Warning: TextCrossEncoder not found. Reranking will use score-based fallback.")

import os
from typing import List, Dict, Any

class EmbeddingService:
    def __init__(self):
        if FASTEMBED_AVAILABLE:
            self.embedding_model = TextEmbedding("BAAI/bge-base-en-v1.5")
        else:
            self.embedding_model = None

        if RERANKER_AVAILABLE:
            self.rerank_model = TextCrossEncoder("BAAI/bge-reranker-base")
        else:
            self.rerank_model = None
            
    async def get_embeddings(self, text: str) -> List[float]:
        """Generates vector embeddings locally or returns mocks."""
        if not self.embedding_model:
            return [0.1] * 768 # Mock vector (bge-base = 768 dims)
            
        embeddings = list(self.embedding_model.embed([text]))
        return embeddings[0].tolist()

    async def get_query_embedding(self, text: str) -> List[float]:
        """Uses query_embed() for correct asymmetric retrieval with BGE models."""
        if not self.embedding_model:
            return [0.1] * 768

        embeddings = list(self.embedding_model.query_embed([text]))
        return embeddings[0].tolist()

    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Re-sorts products locally or returns hardcoded shuffle in mock mode."""
        if not self.rerank_model:
            # Simple mock: just reverse the order so people see the "Refinement" event
            for doc in documents:
                doc["rerank_score"] = doc.get("score", 0.5) + 0.1
            return documents[::-1]

        pairs = [(query, doc.get("description", "")) for doc in documents]
        scores = list(self.rerank_model.predict(pairs))
        
        for i, doc in enumerate(documents):
            doc["rerank_score"] = float(scores[i])
            
        return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
