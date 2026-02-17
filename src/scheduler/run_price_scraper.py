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


def run_price_scraping(
    session_number: int = None,
    hotel_limit: int = None,
    max_dates_per_hotel: int = None,
    j_plus: int = None,
    strategy: int = 1,
) -> Dict[str, Any]:
    """
    Exécute le scraping des prix pour les hôtels actifs.
    
    Args:
        session_number: 1 ou 2 (pour diviser en 2 sessions) - None = tous
        hotel_limit: Limite le nombre d'hôtels (pour tests)
        max_dates_per_hotel: Limite le nombre de dates par hôtel. None = 30.
        j_plus: Si fourni, ne scrape que le prix à J+N (ex: 30 = J+30, ~1 min/hôtel).
        
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
        if max_dates_per_hotel:
            print(f"🧪 Mode test: {max_dates_per_hotel} date(s) par hôtel (au lieu de 30)")
        if j_plus is not None:
            print(f"⚡ Mode J+{j_plus} : uniquement le prix à J+{j_plus} (~1 min/hôtel)")
        
        # Afficher les hôtels à scraper
        print("\n🏨 Hôtels à scraper:")
        for i, hotel in enumerate(hotels_to_scrape, 1):
            print(f"  {i}. {hotel['name']}")
        
        # Lancer le scraping
        date_offsets = [j_plus] if j_plus is not None else None
        stats, snapshots = scrape_multiple_hotels(
            hotels_to_scrape,
            max_dates_per_hotel=max_dates_per_hotel,
            date_offsets=date_offsets,
            strategy=strategy,
        )
        
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
        help="Mode test (1 seul hôtel, 3 dates)"
    )
    parser.add_argument(
        "--dates",
        type=int,
        metavar="N",
        help="Nombre de dates à scraper par hôtel (défaut: 30). Ex: 3 pour test rapide.",
    )
    parser.add_argument(
        "--j-plus",
        type=int,
        metavar="N",
        dest="j_plus",
        help="Scraper uniquement le prix à J+N (ex: 30 = J+30, ~1 min par hôtel).",
    )
    parser.add_argument(
        "--strategy",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Stratégie multi-hôtels: 1=1 nav/hôtel (défaut), 2=nav partagé, 3=parallèle.",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Tester avec une URL Booking précise (ex: https://www.booking.com/hotel/fr/xxx.html)",
    )
    
    args = parser.parse_args()
    
    # Mode test avec URL fournie
    if args.url:
        max_dates = args.dates if args.dates else 30
        print(f"🧪 MODE TEST avec URL: {args.url[:60]}... ({max_dates} dates)")
        from scrapers.price_scraper import scrape_hotel_prices
        test_hotel = {"id": "test-url", "name": "Hôtel (URL)", "url": args.url}
        snapshots = scrape_hotel_prices(test_hotel, max_dates=max_dates)
        print(f"\n📊 Résultat: {len(snapshots)} snapshots")
        for s in snapshots[:10]:
            print(f"  {s['dateCheckin']}: {s['price']}€ (dispo: {s['available']})")
        sys.exit(0 if snapshots else 1)
    
    # Mode test rapide (1 hôtel, 3 dates)
    if args.test:
        print("🧪 MODE TEST (1 hôtel, 3 dates)")
        result = run_price_scraping(
            session_number=None,
            hotel_limit=1,
            max_dates_per_hotel=3,
        )
    else:
        result = run_price_scraping(
            session_number=args.session,
            hotel_limit=args.limit,
            max_dates_per_hotel=args.dates,
            j_plus=args.j_plus,
            strategy=args.strategy,
        )
    
    # Exit code selon le résultat
    sys.exit(0 if result["success"] else 1)
