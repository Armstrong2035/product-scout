import google.generativeai as genai
import os
from typing import List

class EmbeddingService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
    async def get_embeddings(self, text: str) -> List[float]:
        """
        Generates vector embeddings for a given string using Gemini models/gemini-embedding-001.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")
            
        # Using synchronous call in a way that's safe for this context
        # In a high-traffic app, we might use a dedicated async client if available
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document",
            title="Product Search"
        )
        return result['embedding']

    async def get_query_embedding(self, text: str) -> List[float]:
        """Specific task type for queries."""
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
