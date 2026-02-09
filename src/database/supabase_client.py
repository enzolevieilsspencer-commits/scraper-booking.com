"""
Client Supabase pour interagir avec la base de données
"""
from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid
import sys
import os

# Ajouter le répertoire parent au path pour importer config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY


class SupabaseClient:
    """Client pour interagir avec Supabase"""
    
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("✅ Client Supabase initialisé")
    
    # ============ HOTELS ============
    
    def get_monitored_hotels(self) -> List[Dict[str, Any]]:
        """Récupère tous les hôtels actifs (isMonitored=true)"""
        try:
            response = self.client.table("hotels") \
                .select("*") \
                .eq("isMonitored", True) \
                .execute()
            return response.data
        except Exception as e:
            print(f"❌ Erreur get_monitored_hotels: {e}")
            return []
    
    def create_hotel(self, hotel_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée un nouvel hôtel"""
        try:
            hotel_data["id"] = str(uuid.uuid4())
            hotel_data["createdAt"] = datetime.now().isoformat()
            hotel_data["updatedAt"] = datetime.now().isoformat()
            
            response = self.client.table("hotels").insert(hotel_data).execute()
            print(f"✅ Hôtel créé: {hotel_data.get('name')}")
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"❌ Erreur create_hotel: {e}")
            return None
    
    def update_hotel(self, hotel_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un hôtel"""
        try:
            updates["updatedAt"] = datetime.now().isoformat()
            self.client.table("hotels") \
                .update(updates) \
                .eq("id", hotel_id) \
                .execute()
            print(f"✅ Hôtel mis à jour: {hotel_id}")
            return True
        except Exception as e:
            print(f"❌ Erreur update_hotel: {e}")
            return False
    
    def get_hotel_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Récupère un hôtel par son URL"""
        try:
            response = self.client.table("hotels") \
                .select("*") \
                .eq("url", url) \
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"❌ Erreur get_hotel_by_url: {e}")
            return None
    
    # ============ RATE SNAPSHOTS ============
    
    def create_rate_snapshot(self, snapshot_data: Dict[str, Any]) -> bool:
        """Crée un snapshot de prix"""
        try:
            snapshot_data["id"] = str(uuid.uuid4())
            snapshot_data["scrapedAt"] = datetime.now().isoformat()
            
            self.client.table("rate_snapshots").insert(snapshot_data).execute()
            return True
        except Exception as e:
            print(f"❌ Erreur create_rate_snapshot: {e}")
            return False
    
    def create_rate_snapshots_batch(self, snapshots: List[Dict[str, Any]]) -> int:
        """Crée plusieurs snapshots en batch"""
        try:
            for snapshot in snapshots:
                snapshot["id"] = str(uuid.uuid4())
                snapshot["scrapedAt"] = datetime.now().isoformat()
            
            response = self.client.table("rate_snapshots").insert(snapshots).execute()
            count = len(response.data) if response.data else 0
            print(f"✅ {count} snapshots créés")
            return count
        except Exception as e:
            print(f"❌ Erreur create_rate_snapshots_batch: {e}")
            return 0
    
    def get_latest_snapshot(self, hotel_id: str, checkin_date: date) -> Optional[Dict[str, Any]]:
        """Récupère le dernier snapshot pour un hôtel et une date"""
        try:
            response = self.client.table("rate_snapshots") \
                .select("*") \
                .eq("hotelId", hotel_id) \
                .eq("dateCheckin", checkin_date.isoformat()) \
                .order("scrapedAt", desc=True) \
                .limit(1) \
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"❌ Erreur get_latest_snapshot: {e}")
            return None
    
    # ============ SCRAPER LOGS ============
    
    def create_scraper_log(self, log_data: Dict[str, Any]) -> Optional[str]:
        """Crée un log de scraping"""
        try:
            log_id = str(uuid.uuid4())
            log_data["id"] = log_id
            log_data["startedAt"] = datetime.now().isoformat()
            
            self.client.table("scraper_logs").insert(log_data).execute()
            return log_id
        except Exception as e:
            print(f"❌ Erreur create_scraper_log: {e}")
            return None
    
    def update_scraper_log(self, log_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un log de scraping"""
        try:
            updates["completedAt"] = datetime.now().isoformat()
            self.client.table("scraper_logs") \
                .update(updates) \
                .eq("id", log_id) \
                .execute()
            return True
        except Exception as e:
            print(f"❌ Erreur update_scraper_log: {e}")
            return False


# Instance globale
supabase_client = SupabaseClient()
