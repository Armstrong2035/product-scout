import os
import asyncio
from fastapi import APIRouter, HTTPException, Query, Header, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.database_service import DatabaseService

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/dashboard")
async def get_analytics_dashboard(
    shop_url: str = Query(..., description="The Shopify store domain"),
    days: int = Query(30, description="Number of days to look back"),
    # In a real production app, we would verify a session token or JWT here
    # to ensure the requester actually owns `shop_url`.
):
    """
    Returns aggregated analytics for the merchant dashboard.
    Powered by a highly performant Supabase RPC that crunches all metrics in one pass.
    """
    try:
        db = DatabaseService()
        
        # Verify merchant exists
        merchant = await db.get_merchant(shop_url)
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found or unauthorized.")
            
        data = await db.get_dashboard_analytics(shop_url=shop_url, days=days)
        
        if not data:
            # Prevent nulls on fresh accounts
            data = {
                "overview": {
                    "total_searches": 0,
                    "cart_rate_percent": 0,
                    "checkout_rate_percent": 0
                },
                "trending": [],
                "missed_opportunities": [],
                "top_products": []
            }
            
        return data

    except Exception as e:
        print(f"[ANALYTICS ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics dashboard data")

@router.get("/recent-searches")
async def get_recent_searches_feed(
    shop_url: str = Query(..., description="The Shopify store domain"),
    limit: int = Query(50, description="Max number of searches to return")
):
    """
    Returns a live feed of the most recent searches for the given shop.
    Returns: list of dicts with id, query, result_count, created_at, latency_ms.
    """
    try:
        db = DatabaseService()
        
        # Verify merchant
        merchant = await db.get_merchant(shop_url)
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found or unauthorized.")
            
        recent = await db.get_recent_searches(shop_url=shop_url, limit=limit)
        return {"recent_searches": recent}
        
    except Exception as e:
        print(f"[ANALYTICS ERROR] {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent searches feed")
