try:
    from qdrant_client import QdrantClient, models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[QDRANT] Warning: qdrant-client not found. Falling back to Mock Mode.")

import os
from typing import List, Dict, Any

class QdrantService:
    def __init__(self):
        if QDRANT_AVAILABLE:
            self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
            self.api_key = os.getenv("QDRANT_API_KEY")
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
            self.collection_name = "products"
        else:
            self.client = None
            self.collection_name = "products"

    def _ensure_collection_exists(self, vector_size: int):
        """Creates the collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            print(f"[QDRANT] Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )

    def upsert_vectors(self, points: List[Dict[str, Any]], site_id: str):
        """
        Upserts vectors to Qdrant. 
        Uses 'site_id' as a metadata filter for multi-tenancy.
        """
        # Ensure collection exists (bge-small is 384 dimensions)
        if points:
            self._ensure_collection_exists(len(points[0]["vector"]))

        qdrant_points = []
        for p in points:
            # Inject site_id into metadata for filtering
            payload = p["metadata"]
            payload["site_id"] = site_id
            
            qdrant_points.append(models.PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=payload
            ))

        self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points
        )

    def query_vectors(self, query_vector: List[float], site_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search with metadata filtering or return mock results."""
        if not self.client:
            # Return some hardcoded products for terminal demo
            return [
                {"id": 1, "score": 0.9, "metadata": {"handle": "cool-boots", "storefront_id": "gid://1", "title": "Cool Boots"}},
                {"id": 2, "score": 0.8, "metadata": {"handle": "hiking-shoes", "storefront_id": "gid://2", "title": "Hiking Shoes"}},
                {"id": 3, "score": 0.7, "metadata": {"handle": "waterproof-sneakers", "storefront_id": "gid://3", "title": "Waterproof Sneakers"}}
            ]

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="site_id",
                        match=models.MatchValue(value=site_id),
                    )
                ]
            ),
            limit=limit,
        )

        matches = []
        for res in response.points:
            matches.append({
                "id": res.id,
                "score": res.score,
                "metadata": res.payload
            })
        return matches
