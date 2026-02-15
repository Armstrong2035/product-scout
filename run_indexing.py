import asyncio
import os
from dotenv import load_dotenv
from app.services.indexer_service import IndexerService

# Load .env file
load_dotenv()

async def main():
    print("--- Starting Manual Indexing Job ---")
    try:
        indexer = IndexerService()
        count = await indexer.run_indexing_pipeline()
        print(f"\n[SUCCESS] Indexed {count} products.")
        print(f"Vectors saved to: {indexer.vector_path}")
    except Exception as e:
        print(f"\n[ERROR] Indexing failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
