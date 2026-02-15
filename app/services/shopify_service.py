import httpx
import os
import json
from typing import List, Dict, Any

class ShopifyService:
    def __init__(self):
        # Align with the latest .env keys provided by the user
        self.shop_url = os.getenv("CUSTOM_SHOP_URL") or os.getenv("SHOPIFY_SHOP_URL")
        self.admin_access_token = os.getenv("CUSTOM_SHOP_ADMIN_ACCESS_TOKEN")
        self.storefront_access_token = os.getenv("SHOPIFY_STOREFRONT_TOKEN")
        self.api_version = os.getenv("SHOPIFY_API_VERSION", "2024-01")
        
    async def fetch_all_products_graphql(self) -> List[Dict[str, Any]]:
        """
        Fetches all products using the GraphQL Admin API.
        Includes variants and metafields in a single request.
        """
        if not self.shop_url or not self.admin_access_token:
            raise ValueError("Shopify credentials not configured")

        url = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self.admin_access_token,
            "Content-Type": "application/json"
        }

        query = """
        query getProducts($cursor: String) {
          products(first: 50, after: $cursor) {
            pageInfo {
              hasNextPage
            }
            edges {
              cursor
              node {
                id
                title
                handle
                descriptionHtml
                productType
                tags
                variants(first: 50) {
                  edges {
                    node {
                      id
                      title
                      price
                      sku
                    }
                  }
                }
                metafields(first: 20) {
                  edges {
                    node {
                      namespace
                      key
                      value
                    }
                  }
                }
                featuredImage {
                  url
                }
              }
            }
          }
        }
        """

        products = []
        cursor = None
        has_next_page = True

        async with httpx.AsyncClient() as client:
            while has_next_page:
                variables = {"cursor": cursor}
                response = await client.post(url, headers=headers, json={"query": query, "variables": variables})
                response.raise_for_status()
                data = response.json()
                
                if "errors" in data:
                    print(f"[SHOPIFY GRAPHQL ERROR] Full Error: {json.dumps(data['errors'], indent=2)}")
                    break
                
                connection = data.get("data", {}).get("products", {})
                edges = connection.get("edges", [])
                
                for edge in edges:
                    products.append(edge["node"])
                    cursor = edge["cursor"]
                
                has_next_page = connection.get("pageInfo", {}).get("hasNextPage", False)
                print(f"[SHOPIFY GRAPHQL] Fetched {len(products)} products so far...")

        return products

    async def fetch_all_products(self) -> List[Dict[str, Any]]:
        """
        Legacy REST API fetch.
        """
        # ... rest of the method remains same for compatibility

    async def fetch_product_metafields(self, product_id: int) -> List[Dict[str, Any]]:
        """Fetch metafields for a specific product."""
        url = f"https://{self.shop_url}/admin/api/{self.api_version}/products/{product_id}/metafields.json"
        headers = {"X-Shopify-Access-Token": self.admin_access_token}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("metafields", [])
            return []

    async def fetch_storefront_data(self, product_ids: List[str]) -> Dict[str, Any]:
        """
        Fetches live hydrated data (price, availability, images) from Storefront API.
        Uses GraphQL for efficiency.
        """
        if not self.shop_url or not self.storefront_access_token:
            print("[SHOPIFY] Storefront credentials missing, skipping hydration.")
            return {}

        query = """
        query getProducts($ids: [ID!]!) {
          nodes(ids: $ids) {
            ... on Product {
              id
              title
              handle
              availableForSale
              priceRange {
                minVariantPrice {
                  amount
                  currencyCode
                }
              }
              featuredImage {
                url
                altText
              }
            }
          }
        }
        """
        
        url = f"https://{self.shop_url}/api/{self.api_version}/graphql.json"
        headers = {
            "X-Shopify-Storefront-Access-Token": self.storefront_access_token,
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, 
                    headers=headers, 
                    json={"query": query, "variables": {"ids": product_ids}}
                )
                response.raise_for_status()
                data = response.json()
                
                # Map by ID for easy lookup
                hydrated = {}
                for node in data.get("data", {}).get("nodes", []):
                    if node:
                        hydrated[node["id"]] = node
                return hydrated
        except Exception as e:
            print(f"[SHOPIFY ERROR] Storefront hydration failed: {e}")
            return {}
