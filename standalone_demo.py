import math
from typing import List

# Copy of the logic from app/utils/vector_math.py to ensure it works anywhere
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)

def demo_similarity():
    # 1. Identical vectors (Angle = 0°)
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0, 3.0]
    score_identical = cosine_similarity(v1, v2)
    
    # 2. Orthogonal vectors (Angle = 90° - Perpendicular)
    v3 = [1.0, 0.0]
    v4 = [0.0, 1.0]
    score_orthogonal = cosine_similarity(v3, v4)
    
    # 3. Opposite vectors (Angle = 180°)
    v5 = [1.0, 1.0]
    v6 = [-1.0, -1.0]
    score_opposite = cosine_similarity(v5, v6)
    
    # 4. Similar vectors (Small angle)
    v7 = [1.0, 2.0, 0.1]
    v8 = [1.1, 1.9, -0.1]
    score_similar = cosine_similarity(v7, v8)

    print("--- Cosine Similarity Demonstration (Standalone) ---")
    print("\n1. Identical Vectors:")
    print(f"   Score: {score_identical:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_identical)))):.2f}°)")
    
    print("\n2. Orthogonal Vectors:")
    print(f"   Score: {score_orthogonal:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_orthogonal)))):.2f}°)")
    
    print("\n3. Opposite Vectors:")
    print(f"   Score: {score_opposite:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_opposite)))):.2f}°)")
    
    print("\n4. Similar Vectors:")
    print(f"   Score: {score_similar:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_similar)))):.2f}°)")

if __name__ == "__main__":
    demo_similarity()
