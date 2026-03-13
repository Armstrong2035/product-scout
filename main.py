import os
import hmac
import hashlib
import httpx
from fastapi import FastAPI, Request, HTTPException, Query, Depends
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.search import router as search_router
from app.api.tracking import router as tracking_router
from app.api.analytics import router as analytics_router
from app.services.database_service import DatabaseService
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Product Scout API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
APP_URL = os.getenv("APP_URL", "http://localhost:8000") 
SCOPES = "read_products,read_metafields"

# --- Credits Middleware ---
class CreditsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # We only protect search and reindex routes
        if request.url.path in ["/search", "/reindex"]:
            # Simple header-based shop identification for now
            # In production, this would be a session token or JWT from Shopify App Bridge
            shop = request.query_params.get("shop_url") or request.headers.get("X-Shop-URL")
            
            if not shop:
                return await call_next(request) # Let it pass if no shop, search route will handle it
                
            db = DatabaseService()
            merchant = await db.get_merchant(shop)
            
            if not merchant:
                raise HTTPException(status_code=404, detail="Merchant not registered")
            
            if merchant.get("credits_balance", 0) <= 0:
                raise HTTPException(status_code=402, detail="Payment Required: Out of credits")
                
            # Deduct 1 credit for search (Atomic deduct would be better)
            if request.url.path == "/search":
                await db.update_credits(shop, -1)
                
        response = await call_next(request)
        return response

app.add_middleware(CreditsMiddleware)

# --- Shopify OAuth Flow ---

@app.get("/auth")
async def auth(shop: str = Query(...)):
    """Starts the Shopify OAuth flow."""
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop parameter")
        
    redirect_uri = f"{APP_URL}/auth/callback"
    install_url = (
        f"https://{shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_CLIENT_ID}&"
        f"scope={SCOPES}&"
        f"redirect_uri={redirect_uri}"
    )
    return RedirectResponse(install_url)

def verify_shopify_hmac(params: dict, secret: str) -> bool:
    """Verifies the HMAC signature from Shopify."""
    received_hmac = params.get("hmac")
    if not received_hmac:
        return False
        
    # Sort parameters and join into a query string
    # Remove 'hmac' from the parameters to check
    check_params = sorted([(k, v) for k, v in params.items() if k != "hmac"])
    message = "&".join([f"{k}={v}" for k, v in check_params])
    
    calculated_hmac = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(calculated_hmac, received_hmac)

@app.get("/auth/callback")
async def auth_callback(request: Request, shop: str, code: str):
    """Handles the redirect back from Shopify after merchant approval."""
    # 1. Verify HMAC (Crucial Security Step)
    params = dict(request.query_params)
    if not verify_shopify_hmac(params, SHOPIFY_CLIENT_SECRET):
        print(f"[AUTH ERROR] HMAC verification failed for {shop}")
        raise HTTPException(status_code=401, detail="HMAC verification failed")
    
    # 2. Exchange code for permanent token
    url = f"https://{shop}/admin/oauth/access_token"
    data = {
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "code": code
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve access token")
            
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        # 3. Generate Storefront Access Token Automatically
        # This removes the need for the user to find it manually.
        storefront_token = None
        sf_url = f"https://{shop}/admin/api/2024-01/storefront_access_tokens.json"
        sf_payload = {"storefront_access_token": {"title": "Product Scout Live Sync"}}
        
        try:
            sf_response = await client.post(
                sf_url, 
                headers={"X-Shopify-Access-Token": access_token}, 
                json=sf_payload
            )
            if sf_response.status_code == 201:
                storefront_token = sf_response.json().get("storefront_access_token", {}).get("access_token")
                print(f"[AUTH] Generated Storefront Token for {shop}")
        except Exception as e:
            print(f"[AUTH WARNING] Failed to generate Storefront token: {e}")

        # 4. Save to Supabase (Account Provisioning)
        db = DatabaseService()
        merchant_data = {
            "shop_url": shop,
            "access_token": access_token,
            "storefront_token": storefront_token,
            "credits_balance": 100, # Welcome bonus!
            "plan_level": "free"
        }
        await db.save_merchant(merchant_data)
        
        # 5. Trigger initial indexing in the background
        from app.services.indexer_service import IndexerService
        indexer = IndexerService()
        import asyncio
        asyncio.create_task(indexer.run_indexing_pipeline(shop, access_token))
        
        print(f"[AUTH] Successfully onboarded {shop}")
        
    # Redirect to successful install page or app dashboard
    return RedirectResponse(url=f"https://{shop}/admin/apps/product-scout")


# --- Provision Endpoint (called by React app after its own OAuth) ---

class ProvisionRequest(BaseModel):
    shop_url: str
    access_token: str

@app.post("/provision")
async def provision(payload: ProvisionRequest):
    """
    Idempotent merchant provisioning.
    Called by the React app after authenticate.admin() succeeds.
    - If merchant already exists in Supabase → return immediately (no re-indexing).
    - If new merchant → generate storefront token, upsert row, trigger indexing.
    """
    shop = payload.shop_url
    access_token = payload.access_token

    if not shop or not access_token:
        raise HTTPException(status_code=400, detail="shop_url and access_token are required")

    db = DatabaseService()

    # --- Idempotency check ---
    existing = await db.get_merchant(shop)
    if existing:
        print(f"[PROVISION] Merchant {shop} already provisioned — skipping.")
        return {"status": "already_provisioned", "shop": shop}

    # --- New merchant: generate storefront token ---
    storefront_token = None
    sf_url = f"https://{shop}/admin/api/2024-01/storefront_access_tokens.json"
    sf_payload = {"storefront_access_token": {"title": "Product Scout Live Sync"}}

    async with httpx.AsyncClient() as client:
        try:
            sf_response = await client.post(
                sf_url,
                headers={"X-Shopify-Access-Token": access_token},
                json=sf_payload
            )
            if sf_response.status_code == 201:
                storefront_token = sf_response.json().get("storefront_access_token", {}).get("access_token")
                print(f"[PROVISION] Generated Storefront Token for {shop}")
        except Exception as e:
            print(f"[PROVISION WARNING] Failed to generate Storefront token: {e}")

    # --- Upsert merchant row in Supabase ---
    merchant_data = {
        "shop_url": shop,
        "access_token": access_token,
        "storefront_token": storefront_token,
        "credits_balance": 100,
        "plan_level": "free"
    }
    await db.save_merchant(merchant_data)

    # --- Trigger initial indexing in the background ---
    from app.services.indexer_service import IndexerService
    import asyncio
    indexer = IndexerService()
    asyncio.create_task(indexer.run_indexing_pipeline(shop, access_token))

    print(f"[PROVISION] Successfully onboarded {shop}")
    return {"status": "provisioned", "shop": shop}


@app.get("/")
async def root():
    return {"message": "Product Scout API is online", "mode": "multi-tenant"}

@app.get("/test")
async def test_page():
    return FileResponse("test_overlay.html")

app.include_router(search_router)
app.include_router(tracking_router)
app.include_router(analytics_router)

# Serve static files for the storefront overlay
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
