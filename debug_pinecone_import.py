try:
    import pinecone
    print(f"[SUCCESS] 'import pinecone' worked. Version: {getattr(pinecone, '__version__', 'unknown')}")
    print(f"Pinecone file path: {getattr(pinecone, '__file__', 'unknown')}")
    from pinecone import Pinecone
    print("[SUCCESS] Import 'from pinecone import Pinecone' worked.")
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
except Exception as e:
    print(f"[FAIL] Unexpected error: {e}")
