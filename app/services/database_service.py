import os
from typing import Optional, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class DatabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_PRODUCT_URL")
        # Note: SERVICE_ROLE_KEY is required for backend operations (RLS bypass)
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.url or not self.key:
            # We don't raise here yet to allow the app to start, 
            # but methods will fail if keys are missing.
            print("[DATABASE] Warning: Supabase credentials missing.")
            self.client = None
        else:
            self.client: Client = create_client(self.url, self.key)

    async def get_merchant(self, site_id: str) -> Optional[Dict[str, Any]]:
        """Fetch merchant details using site_id (mapped to shop_url column)."""
        if not self.client:
            return None
            
        try:
            # We keep the column name as 'shop_url' in the DB for now
            response = self.client.table("merchants").select("*").eq("shop_url", site_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to fetch merchant: {e}")
            return None

    async def save_merchant(self, merchant_data: Dict[str, Any]) -> bool:
        """Upsert merchant record in the registry."""
        if not self.client:
            return False
            
        try:
            self.client.table("merchants").upsert(merchant_data).execute()
            return True
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to save merchant: {e}")
            return False

    async def update_credits(self, site_id: str, amount: int) -> bool:
        """Atomically update credit balance."""
        if not self.client:
            return False
        
        try:
            merchant = await self.get_merchant(site_id)
            if not merchant:
                return False
                
            new_balance = merchant.get("credits_balance", 0) + amount
            self.client.table("merchants").update({"credits_balance": new_balance}).eq("shop_url", site_id).execute()
            return True
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to update credits: {e}")
            return False

    async def increment_query_count(self, shop_url: str):
        """Update total query count for a merchant."""
        if not self.client: return
        try:
            # Fetch current
            res = self.client.table("merchants").select("total_queries").eq("shop_url", shop_url).execute()
            if res.data:
                curr = res.data[0].get("total_queries", 0)
                self.client.table("merchants").update({"total_queries": curr + 1}).eq("shop_url", shop_url).execute()
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to increment query count: {e}")

    async def log_search(self, analytics_data: Dict[str, Any]):
        """Log search telemetry to Supabase."""
        if not self.client: return
        try:
            self.client.table("search_logs").insert(analytics_data).execute()
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to log search: {e}")

    async def log_attribution_event(self, event_data: Dict[str, Any]):
        """Log click or cart event to Supabase."""
        if not self.client: return
        try:
            self.client.table("attribution_events").insert(event_data).execute()
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to log attribution event: {e}")

    async def get_dashboard_analytics(self, shop_url: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Calls the highly-performant Supabase RPC to aggregate all dashboard metrics
        (Searches, Carts, Checkouts, Trending Queries, Missed Opportunities, Top Products)
        in a single database transaction.
        """
        if not self.client: return None
        try:
            # We use the Supabase JS-equivalent rpc call
            res = self.client.rpc(
                "get_dashboard_analytics", 
                {"target_shop": shop_url, "days_back": days}
            ).execute()
            
            return res.data
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to fetch analytics: {e}")
            return None

    async def get_recent_searches(self, shop_url: str, limit: int = 50) -> list:
        """Fetch the most recent searches for the live feed."""
        if not self.client: return []
        try:
            res = self.client.table("search_logs")\
                .select("id, query, result_count, created_at, latency_ms")\
                .eq("shop_url", shop_url)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return res.data
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to fetch recent searches: {e}")
            return []
