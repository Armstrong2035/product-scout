# Product Scout — Headless Integration Guide

This guide explains how to integrate your custom frontend (Shopify Extension, WooCommerce Plugin, or Mobile App) with the **Product Scout AI Engine**.

---

## 1. Core Architecture
The Engine is a **Headless Search Service**. It performs the complex vector math and AI reasoning, but it does **not** handle product display data (images, prices). 

**The Flow:**
1.  **Client** sends a query to the Engine.
2.  **Engine** returns a stream of Product IDs and Scores.
3.  **Client** uses those IDs to fetch live display data (Hydration) from its own platform (e.g., Shopify Storefront API).
4.  **Engine** follows up with AI-generated reasoning ("Why we picked this").

---

## 2. API Contract (Streaming SSE)

### `POST /search`
The search endpoint uses **Server-Sent Events (SSE)** to provide a multi-stage, high-speed experience.

**Request Body** (`application/json`):
```json
{
  "query": "comfortable waterproof sneakers",
  "site_id": "your-unique-site-identifier",
  "limit": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Natural language search query |
| `site_id` | string | ✅ | A unique ID for the store/tenant (e.g., `store.myshopify.com`) |
| `limit` | integer | ❌ | Max results (default: 5) |

---

## 3. SSE Implementation (The Client Side)

Since the response is a stream, use the **Fetch API** with a readable stream.

### SSE Events
The engine yields three types of data chunks:

1.  **`event: products`**: Instant results from the vector database.
    ```json
    {"event": "products", "data": [{"id": "123", "handle": "sneaker-xyz", "score": 0.85}]}
    ```
2.  **`event: refined`**: (Optional) High-accuracy results after the **BGE-Reranker** finishes. Use this to update the UI for maximum precision.
    ```json
    {"event": "refined", "data": [{"id": "456", "handle": "better-sneaker", "score": 0.98}]}
    ```
3.  **`event: reasoning`**: The AI's explanation for the selection.
    ```json
    {"event": "reasoning", "text": "These sneakers use GORE-TEX technology..."}
    ```

### Example Consumer (JavaScript)
```javascript
async function startSearch(query, siteId) {
  const response = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, site_id: siteId })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n\n");

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = JSON.parse(line.replace("data: ", ""));
      
      handleEvent(payload);
    }
  }
}
```

---

## 4. Hydration Strategy
The Engine returns **IDs and Handles**. Your client is responsible for fetching the "Look & Feel":

| Platform | Recommended Hydration Method |
|-----------|-----------------------------|
| **Shopify** | Use the `nodes()` query in the **Storefront API** using retrieved IDs. |
| **WooCommerce**| Use the WC REST API `products/batch` endpoint. |
| **Custom** | Pull from your own product cache/database. |

---

## 5. Deployment / Self-Hosting
- **Qdrant**: The engine expects a Qdrant instance on port `6333`.
- **FastEmbed**: Models are cached locally on the engine's VPS.
- **Environment**: Ensure `QDRANT_URL` and `GEMINI_API_KEY` are set on the server.

---

## Summary for Developers
- **`site_id`** is your namespace. Use the store's domain or a UUID.
- **Expect a Stream**, not a single JSON array.
- **Hydrate on the Client** to keep the search engine platform-agnostic.
- **Reranking** happens in the background to ensure Top-1 accuracy.
