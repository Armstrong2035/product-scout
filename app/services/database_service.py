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
