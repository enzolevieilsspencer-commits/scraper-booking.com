"""
Script de test pour vérifier que tout fonctionne
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test que tous les modules s'importent correctement"""
    print("🧪 Test 1: Imports des modules...")
    
    try:
        from src.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
        print("  ✅ Config importée")
        
        from src.database.supabase_client import supabase_client
        print("  ✅ Client Supabase importé")
        
        from src.scrapers.hotel_info_scraper import scrape_hotel_info
        print("  ✅ Scraper infos importé")
        
        from src.scrapers.price_scraper import scrape_hotel_prices
        print("  ✅ Scraper prix importé")
        
        print("✅ Tous les imports OK\n")
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'import: {e}\n")
        return False


def test_supabase_connection():
    """Test la connexion à Supabase"""
    print("🧪 Test 2: Connexion Supabase...")
    
    try:
        from src.database.supabase_client import supabase_client
        
        # Tenter de récupérer les hôtels
        hotels = supabase_client.get_monitored_hotels()
        print(f"  ✅ Connexion OK - {len(hotels)} hôtel(s) trouvé(s)")
        
        for hotel in hotels:
            print(f"     • {hotel['name']}")
        
        print("✅ Supabase OK\n")
        return True
        
    except Exception as e:
        print(f"❌ Erreur Supabase: {e}\n")
        return False


def test_scraper_info():
    """Test le scraper d'infos (si URL fournie)"""
    print("🧪 Test 3: Scraper infos hôtel...")
    
    # URL de test (remplacer par une vraie si disponible)
    test_url = input("  Entrez une URL Booking.com (ou Enter pour skip): ").strip()
    
    if not test_url:
        print("  ⏭️ Test skippé\n")
        return True
    
    try:
        from src.scrapers.hotel_info_scraper import scrape_hotel_info
        
        print(f"  📡 Scraping {test_url}...")
        result = scrape_hotel_info(test_url)
        
        if result:
            print("  ✅ Scraping réussi:")
            print(f"     • Nom: {result['name']}")
            print(f"     • Adresse: {result['address']}")
            print(f"     • Étoiles: {result['stars']}")
            print("✅ Scraper infos OK\n")
            return True
        else:
            print("  ❌ Scraping échoué\n")
            return False
            
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_config():
    """Test la configuration"""
    print("🧪 Test 4: Configuration...")
    
    try:
        from src.config import (
            SUPABASE_URL,
            SUPABASE_SERVICE_KEY,
            ENVIRONMENT,
            MIN_DELAY_SECONDS,
            MAX_DELAY_SECONDS
        )
        
        print(f"  • Environment: {ENVIRONMENT}")
        print(f"  • Supabase URL: {SUPABASE_URL}")
        print(f"  • Délais: {MIN_DELAY_SECONDS}-{MAX_DELAY_SECONDS}s")
        print("✅ Configuration OK\n")
        return True
        
    except Exception as e:
        print(f"❌ Erreur config: {e}\n")
        return False


def main():
    """Lance tous les tests"""
    print("""
╔═══════════════════════════════════════════╗
║   🧪 TESTS DU SCRAPER BOOKING.COM         ║
╚═══════════════════════════════════════════╝
""")
    
    results = []
    
    # Tests
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Supabase", test_supabase_connection()))
    results.append(("Scraper", test_scraper_info()))
    
    # Résumé
    print("═" * 50)
    print("📊 RÉSUMÉ DES TESTS")
    print("═" * 50)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print("═" * 50)
    print(f"\nRésultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests sont passés ! Le scraper est prêt.\n")
        return 0
    else:
        print("\n⚠️ Certains tests ont échoué. Vérifiez la configuration.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
