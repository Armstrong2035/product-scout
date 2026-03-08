import os
import time
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any

# Maximum number of candidates fetched from Pinecone before score-gap trimming
_CANDIDATE_CEILING = 50

class VectorService:
    def __init__(self):
        self.api_key = os.getenv("PINE_CONE_API_KEY")
        self.index_name = "product-scout-gemini"
        
        if not self.api_key:
            raise ValueError("PINE_CONE_API_KEY not found in environment")
            
        self.pc = Pinecone(api_key=self.api_key)
        
        # Ensure index exists
        self._ensure_index_exists()
        self.index = self.pc.Index(self.index_name)

    def _ensure_index_exists(self):
        """Creates the index if it doesn't already exist."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            print(f"[VECTOR] Creating new Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=3072, # Gemini Embedding dimension (e.g. text-embedding-004)
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)
        else:
            print(f"[VECTOR] Connected to existing Pinecone index: {self.index_name}")

    def upsert_vectors(self, vectors: List[Dict[str, Any]], namespace: str):
        """Pushes embeddings to Pinecone with metadata in a specific namespace."""
        print(f"[VECTOR] Upserting {len(vectors)} vectors to namespace '{namespace}'...")
        self.index.upsert(vectors=vectors, namespace=namespace)

    def query_vectors(self, query_embedding: List[float], namespace: str, top_k: int = 5) -> List[Dict[Dict[str, Any]]]:
        """Searches Pinecone for similar vectors within a specific namespace."""
        results = self.index.query(
            vector=query_embedding,
            top_k=_CANDIDATE_CEILING,
            include_metadata=True,
            namespace=namespace
        )

        matches = []
        for match in results.get("matches", []):
            matches.append({
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            })
        return matches

    @staticmethod
    def detect_score_gap(matches: List[Dict[str, Any]], min_results: int = 5) -> List[Dict[str, Any]]:
        """Scans consecutive score differences and cuts at the largest gap."""
        if len(matches) <= min_results:
            return matches

        scores = [m["score"] for m in matches]
        gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
        max_gap_idx = gaps.index(max(gaps))
        cut = max(max_gap_idx + 1, min_results)

        print(f"[VECTOR] Score gap cut: keeping {cut}/{len(matches)} candidates")
        return matches[:cut]

    def delete_all(self):
        """Purges the index."""
        print("[VECTOR] Purging index...")
        self.index.delete(delete_all=True)
