from app.utils.vector_math import cosine_similarity
import math

def demo_similarity():
    output_file = "math_results.txt"
    with open(output_file, "w") as f:
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

        f.write("--- Cosine Similarity Demonstration ---\n\n")
        print("--- Cosine Similarity Demonstration ---\n")
        
        f.write(f"1. Identical Vectors: {v1} and {v2}\n")
        f.write(f"   Score: {score_identical:.4f}\n")
        f.write(f"   Angle: {math.degrees(math.acos(max(-1, min(1, score_identical)))):.2f}°\n\n")
        print(f"1. Identical Score: {score_identical:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_identical)))):.2f}°)")
        
        f.write(f"2. Orthogonal Vectors: {v3} and {v4}\n")
        f.write(f"   Score: {score_orthogonal:.4f}\n")
        f.write(f"   Angle: {math.degrees(math.acos(max(-1, min(1, score_orthogonal)))):.2f}°\n\n")
        print(f"2. Orthogonal Score: {score_orthogonal:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_orthogonal)))):.2f}°)")
        
        f.write(f"3. Opposite Vectors: {v5} and {v6}\n")
        f.write(f"   Score: {score_opposite:.4f}\n")
        f.write(f"   Angle: {math.degrees(math.acos(max(-1, min(1, score_opposite)))):.2f}°\n\n")
        print(f"3. Opposite Score: {score_opposite:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_opposite)))):.2f}°)")
        
        f.write(f"4. Similar Vectors: {v7} and {v8}\n")
        f.write(f"   Score: {score_similar:.4f}\n")
        f.write(f"   Angle: {math.degrees(math.acos(max(-1, min(1, score_similar)))):.2f}°\n")
        print(f"4. Similar Score: {score_similar:.4f} (Angle: {math.degrees(math.acos(max(-1, min(1, score_similar)))):.2f}°)")
        
        print(f"\nResults also saved to {output_file}")

if __name__ == "__main__":
    demo_similarity()
