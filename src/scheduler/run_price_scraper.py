"""
Script pour exécuter le scraping des prix
Peut être appelé manuellement ou par le cron job
"""
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.price_scraper import scrape_multiple_hotels
from database.supabase_client import supabase_client


def run_price_scraping(session_number: int = None, hotel_limit: int = None) -> Dict[str, Any]:
    """
    Exécute le scraping des prix pour les hôtels actifs
    
    Args:
        session_number: 1 ou 2 (pour diviser en 2 sessions) - None = tous
        hotel_limit: Limite le nombre d'hôtels (pour tests)
        
    Returns:
        Statistiques d'exécution
    """
    print(f"\n{'='*70}")
    print(f"🚀 DÉMARRAGE DU SCRAPING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if session_number:
        print(f"📍 Session {session_number}/2")
    print(f"{'='*70}\n")
    
    # Créer un log dans Supabase
    log_id = supabase_client.create_scraper_log({
        "status": "running",
        "hotelId": None,
        "snapshotsCreated": 0,
    })
    
    try:
        # Récupérer les hôtels actifs
        all_hotels = supabase_client.get_monitored_hotels()
        
        if not all_hotels:
            print("⚠️ Aucun hôtel actif trouvé dans la base")
            # status doit être 'running' | 'success' | 'error' (contrainte Supabase)
            supabase_client.update_scraper_log(log_id, {
                "status": "success",
                "snapshotsCreated": 0,
                "error": "No active hotels found"
            })
            return {
                "success": False,
                "message": "Aucun hôtel actif",
                "stats": {}
            }
        
        print(f"✅ {len(all_hotels)} hôtel(s) actif(s) trouvé(s)")
        
        # Filtrer selon la session
        if session_number == 1:
            hotels_to_scrape = all_hotels[:3]  # 3 premiers
            print(f"📋 Session 1: Scraping des 3 premiers hôtels")
        elif session_number == 2:
            hotels_to_scrape = all_hotels[3:6]  # 3 suivants
            print(f"📋 Session 2: Scraping des 3 hôtels suivants")
        else:
            hotels_to_scrape = all_hotels  # Tous
            print(f"📋 Scraping de tous les hôtels")
        
        # Limiter pour tests
        if hotel_limit:
            hotels_to_scrape = hotels_to_scrape[:hotel_limit]
            print(f"🧪 Mode test: Limité à {hotel_limit} hôtel(s)")
        
        # Afficher les hôtels à scraper
        print("\n🏨 Hôtels à scraper:")
        for i, hotel in enumerate(hotels_to_scrape, 1):
            print(f"  {i}. {hotel['name']}")
        
        # Lancer le scraping
        stats, snapshots = scrape_multiple_hotels(hotels_to_scrape)
        
        # Enregistrer les snapshots dans Supabase
        if snapshots:
            print(f"\n💾 Enregistrement de {len(snapshots)} snapshots dans Supabase...")
            saved_count = supabase_client.create_rate_snapshots_batch(snapshots)
            print(f"✅ {saved_count} snapshots enregistrés")
        
        # Mettre à jour le log
        supabase_client.update_scraper_log(log_id, {
            "status": "success",
            "snapshotsCreated": len(snapshots),
        })
        
        # Résumé
        print(f"\n{'='*70}")
        print(f"✅ SCRAPING TERMINÉ")
        print(f"{'='*70}")
        print(f"📊 Statistiques:")
        print(f"   • Hôtels traités: {stats['successful_hotels']}/{stats['total_hotels']}")
        print(f"   • Snapshots créés: {stats['total_snapshots']}")
        print(f"   • Échecs: {stats['failed_hotels']}")
        if stats['errors']:
            print(f"\n⚠️ Erreurs:")
            for error in stats['errors']:
                print(f"   • {error}")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "message": "Scraping terminé avec succès",
            "stats": stats,
            "snapshots_count": len(snapshots)
        }
        
    except Exception as e:
        error_msg = f"Erreur fatale: {str(e)}"
        print(f"\n❌ {error_msg}")
        
        # Logger l'erreur
        supabase_client.update_scraper_log(log_id, {
            "status": "error",
            "error": error_msg
        })
        
        return {
            "success": False,
            "message": error_msg,
            "stats": {}
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Exécuter le scraping des prix")
    parser.add_argument(
        "--session",
        type=int,
        choices=[1, 2],
        help="Numéro de session (1 ou 2)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limiter le nombre d'hôtels (pour tests)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Mode test (1 seul hôtel)"
    )
    
    args = parser.parse_args()
    
    # Mode test
    if args.test:
        print("🧪 MODE TEST")
        result = run_price_scraping(session_number=None, hotel_limit=1)
    else:
        result = run_price_scraping(
            session_number=args.session,
            hotel_limit=args.limit
        )
    
    # Exit code selon le résultat
    sys.exit(0 if result["success"] else 1)
