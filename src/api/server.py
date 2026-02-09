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


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║   🚀 Booking Scraper API                     ║
    ║   Serveur démarré sur http://{API_HOST}:{API_PORT}  ║
    ╚══════════════════════════════════════════════╝
    
    📌 Endpoints disponibles:
       GET  /               - Info API
       GET  /health         - Health check
       POST /extract        - Extraire infos (Next.js, sans enregistrer)
       POST /scrape-hotel   - Scraper et enregistrer un hôtel
       POST /test-scrape    - Tester le scraping sans enregistrer
    
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
