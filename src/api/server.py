"""
API FastAPI pour déclencher manuellement le scraping d'infos hôtel
Endpoint: POST /scrape-hotel avec {"url": "..."}
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.supabase_client import supabase_client
from config import API_HOST, API_PORT

app = FastAPI(
    title="Booking Scraper API",
    description="API pour scraper les infos des hôtels Booking.com",
    version="1.0.0"
)

# CORS pour permettre les appels depuis Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeHotelRequest(BaseModel):
    """Request body pour scraper un hôtel"""
    url: str
    isClient: Optional[bool] = False
    isMonitored: Optional[bool] = True


class ScrapeHotelResponse(BaseModel):
    """Response après scraping"""
    success: bool
    message: str
    hotel: Optional[dict] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "running",
        "service": "Booking Scraper API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/scrape-hotel", response_model=ScrapeHotelResponse)
async def scrape_hotel(request: ScrapeHotelRequest):
    """
    Scrape les informations d'un hôtel Booking.com
    
    Body:
    {
        "url": "https://www.booking.com/hotel/fr/...",
        "isClient": false,
        "isMonitored": true
    }
    """
    try:
        print(f"\n🔍 Requête de scraping: {request.url}")
        
        # Vérifier si l'hôtel existe déjà
        existing_hotel = supabase_client.get_hotel_by_url(request.url)
        if existing_hotel:
            return ScrapeHotelResponse(
                success=False,
                message="Cet hôtel existe déjà dans la base",
                hotel=existing_hotel,
                error="Hotel already exists"
            )
        
        # Import paresseux pour ne pas charger Playwright au démarrage du serveur
        from scrapers.hotel_info_scraper import scrape_hotel_info
        hotel_data = scrape_hotel_info(request.url)
        
        if not hotel_data:
            raise HTTPException(
                status_code=500,
                detail="Échec du scraping - Impossible de récupérer les données"
            )
        
        # Ajouter les flags
        hotel_data["isClient"] = request.isClient
        hotel_data["isMonitored"] = request.isMonitored
        
        # Enregistrer dans Supabase
        created_hotel = supabase_client.create_hotel(hotel_data)
        
        if not created_hotel:
            raise HTTPException(
                status_code=500,
                detail="Échec de l'enregistrement dans la base de données"
            )
        
        return ScrapeHotelResponse(
            success=True,
            message=f"Hôtel '{hotel_data['name']}' ajouté avec succès",
            hotel=created_hotel
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/test-scrape")
async def test_scrape(request: ScrapeHotelRequest):
    """
    Teste le scraping sans enregistrer dans la base
    Utile pour vérifier qu'une URL fonctionne
    """
    try:
        from scrapers.hotel_info_scraper import scrape_hotel_info
        print(f"\n🧪 Test de scraping: {request.url}")
        hotel_data = scrape_hotel_info(request.url)
        
        if not hotel_data:
            return {
                "success": False,
                "message": "Échec du scraping",
                "data": None
            }
        
        return {
            "success": True,
            "message": "Scraping réussi (non enregistré)",
            "data": hotel_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Erreur: {str(e)}",
            "data": None
        }


# Timeout pour /extract (scraping peut prendre 30–60 s, cold start Railway encore plus)
EXTRACT_TIMEOUT_SECONDS = 90

class ExtractRequest(BaseModel):
    """Body pour POST /extract (appelé par Next.js)"""
    url: str


@app.post("/extract")
async def extract(request: ExtractRequest):
    """
    Endpoint pour Next.js « Ajouter un concurrent ».
    Body: { "url": "https://www.booking.com/hotel/..." }
    Réponse: { name, location, stars, photoUrl } (pas d'écriture en base).
    Timeout 90 s pour éviter 502 côté client (Railway/Vercel).
    """
    try:
        from scrapers.hotel_info_scraper import scrape_hotel_info_async
        print(f"\n🔍 Extract (Next.js): {request.url}")
        data = await asyncio.wait_for(
            scrape_hotel_info_async(request.url),
            timeout=EXTRACT_TIMEOUT_SECONDS,
        )
        if not data:
            raise HTTPException(
                status_code=500,
                detail="Échec du scraping - Impossible de récupérer les données"
            )
        # Toujours renvoyer des types attendus par Next (pas de null pour les string)
        return {
            "name": data.get("name") or "",
            "location": data.get("location") or "",
            "address": data.get("address") or "",
            "stars": data.get("stars") if data.get("stars") is not None else 0,
            "photoUrl": data.get("photoUrl") or "",
        }
    except asyncio.TimeoutError:
        print("❌ /extract timeout")
        raise HTTPException(
            status_code=504,
            detail="Scraping trop long (timeout). Réessayez ou vérifiez l'URL."
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur /extract: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


# ============ ROUTES PRIX (Scraper 2) ============
# Back → DB : run_price_scraping écrit dans rate_snapshots via supabase_client

class ScrapePricesRequest(BaseModel):
    """Body pour POST /scrape-prices"""
    limit: Optional[int] = None  # Limiter le nombre d'hôtels (ex: 6)
    dates: Optional[int] = None  # Nombre de dates par hôtel (ex: 30)
    strategy: Optional[int] = 1  # 1=isolé, 2=partagé, 3=parallèle


class ScrapePricesTestRequest(BaseModel):
    """Body pour POST /scrape-prices/test"""
    url: str
    dates: Optional[int] = 3  # Pour test rapide


@app.post("/scrape-prices")
async def scrape_prices(request: ScrapePricesRequest):
    """
    Lance le scraping des prix pour tous les hôtels surveillés.
    Écrit dans Supabase (rate_snapshots, scraper_logs).
    Body: { "limit": 6, "dates": 30 } (optionnel)
    Exécuté dans un thread pour éviter "Playwright Sync API inside asyncio loop".
    """
    try:
        from scheduler.run_price_scraper import run_price_scraping
        print(f"\n💰 Requête /scrape-prices: limit={request.limit}, dates={request.dates}")
        result = await asyncio.to_thread(
            run_price_scraping,
            hotel_limit=request.limit,
            max_dates_per_hotel=request.dates,
            strategy=request.strategy,
        )
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "stats": result.get("stats", {}),
            "snapshots_count": result.get("snapshots_count", 0),
        }
    except Exception as e:
        print(f"❌ Erreur /scrape-prices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/scrape-prices/test")
async def scrape_prices_test(request: ScrapePricesTestRequest):
    """
    Teste le scraping des prix pour une URL sans enregistrer en base.
    Body: { "url": "https://www.booking.com/hotel/fr/...", "dates": 3 }
    Exécuté dans un thread pour éviter "Playwright Sync API inside asyncio loop".
    """
    try:
        from scrapers.price_scraper import scrape_hotel_prices
        print(f"\n🧪 Test /scrape-prices: {request.url[:60]}...")
        test_hotel = {"id": "test", "name": "Test", "url": request.url}
        snapshots = await asyncio.to_thread(
            scrape_hotel_prices,
            test_hotel,
            max_dates=request.dates or 3,
        )
        return {
            "success": True,
            "message": f"{len(snapshots)} snapshots extraits (non enregistrés)",
            "snapshots": [
                {"dateCheckin": s["dateCheckin"], "price": s["price"], "available": s["available"]}
                for s in snapshots[:20]
            ],
        }
    except Exception as e:
        print(f"❌ Erreur /scrape-prices/test: {e}")
        return {
            "success": False,
            "message": str(e),
            "snapshots": [],
        }


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║   🚀 Booking Scraper API                     ║
    ║   Serveur démarré sur http://{API_HOST}:{API_PORT}  ║
    ╚══════════════════════════════════════════════╝
    
    📌 Endpoints disponibles:
       GET  /                 - Info API
       GET  /health           - Health check
       POST /extract          - Extraire infos hôtel (Next.js, sans enregistrer)
       POST /scrape-hotel     - Scraper et enregistrer un hôtel
       POST /test-scrape      - Tester scraping hôtel sans enregistrer
       POST /scrape-prices    - Scraper les prix → DB (rate_snapshots)
       POST /scrape-prices/test - Tester scraping prix sans enregistrer
    
    💡 Exemple curl:
       curl -X POST http://localhost:8000/scrape-hotel \\
         -H "Content-Type: application/json" \\
         -d '{{"url": "https://www.booking.com/hotel/fr/..."}}'
    """)
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info"
    )
