"""
Scraper 2: Récupération des prix pour les 30 prochains jours
Usage: Exécuté automatiquement 2x/jour (2 sessions de 3 hôtels)
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.stealth_config import create_stealth_browser, close_browser, random_delay
from config import MIN_DELAY_SECONDS, MAX_DELAY_SECONDS


def get_next_30_days() -> List[date]:
    """Génère une liste des 30 prochains jours"""
    today = date.today()
    return [today + timedelta(days=i) for i in range(1, 31)]


def scrape_price_for_date(
    page: Page, 
    hotel_url: str, 
    checkin_date: date
) -> Optional[Dict[str, Any]]:
    """
    Scrape le prix pour une date spécifique
    
    Args:
        page: Page Playwright déjà ouverte
        hotel_url: URL de l'hôtel
        checkin_date: Date de check-in
        
    Returns:
        Dict avec: price, currency, available, dateCheckin
    """
    try:
        # Formater les dates pour l'URL Booking
        checkout_date = checkin_date + timedelta(days=1)  # 1 nuit
        
        checkin_str = checkin_date.strftime("%Y-%m-%d")
        checkout_str = checkout_date.strftime("%Y-%m-%d")
        
        # Construire URL avec dates
        if "?" in hotel_url:
            url_with_dates = f"{hotel_url}&checkin={checkin_str}&checkout={checkout_str}"
        else:
            url_with_dates = f"{hotel_url}?checkin={checkin_str}&checkout={checkout_str}"
        
        # Aller sur la page avec les dates
        page.goto(url_with_dates, wait_until="domcontentloaded", timeout=30000)
        random_delay(2, 4)
        
        # Attendre le chargement des prix
        try:
            page.wait_for_selector('[data-testid="price-and-discounted-price"]', timeout=10000)
        except:
            # Si pas de prix trouvé, l'hôtel est peut-être complet
            pass
        
        snapshot = {
            "dateCheckin": checkin_str,
            "price": None,
            "currency": "EUR",
            "available": False,
        }
        
        # Chercher le prix
        try:
            # Méthode 1: Prix dans le premier résultat de chambre
            price_element = page.locator('[data-testid="price-and-discounted-price"]').first
            price_text = price_element.inner_text()
            
            # Extraire le nombre (ex: "€ 150" -> 150.0)
            price_match = re.search(r'[\d\s]+(?:[.,]\d+)?', price_text.replace('\xa0', ''))
            if price_match:
                price_str = price_match.group().replace(' ', '').replace(',', '.')
                snapshot["price"] = float(price_str)
                snapshot["available"] = True
                print(f"    ✅ {checkin_str}: {snapshot['price']}€")
        except:
            # Méthode 2: Chercher dans les offres
            try:
                price_element = page.locator('.prco-valign-middle-helper').first
                price_text = price_element.inner_text()
                
                price_match = re.search(r'[\d\s]+(?:[.,]\d+)?', price_text.replace('\xa0', ''))
                if price_match:
                    price_str = price_match.group().replace(' ', '').replace(',', '.')
                    snapshot["price"] = float(price_str)
                    snapshot["available"] = True
                    print(f"    ✅ {checkin_str}: {snapshot['price']}€")
            except Exception as e:
                # Pas de prix = indisponible
                print(f"    ⚠️ {checkin_str}: Indisponible")
                snapshot["available"] = False
        
        return snapshot
        
    except PlaywrightTimeout:
        print(f"    ❌ {checkin_date}: Timeout")
        return {
            "dateCheckin": checkin_date.isoformat(),
            "price": None,
            "currency": "EUR",
            "available": False,
        }
    except Exception as e:
        print(f"    ❌ {checkin_date}: Erreur - {e}")
        return None


def scrape_hotel_prices(hotel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scrape tous les prix pour un hôtel sur 30 jours
    
    Args:
        hotel: Dict avec id, url, name
        
    Returns:
        Liste de snapshots de prix
    """
    print(f"\n🏨 Scraping {hotel['name']}...")
    
    browser, context, page = create_stealth_browser()
    snapshots = []
    
    try:
        dates = get_next_30_days()
        
        for i, checkin_date in enumerate(dates, 1):
            print(f"  📅 Date {i}/30: {checkin_date}")
            
            snapshot = scrape_price_for_date(page, hotel['url'], checkin_date)
            
            if snapshot:
                snapshot["hotelId"] = hotel['id']
                snapshots.append(snapshot)
            
            # Délai aléatoire entre chaque requête (sauf dernière)
            if i < len(dates):
                random_delay(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        
        print(f"✅ {hotel['name']}: {len(snapshots)} snapshots récupérés")
        
    except Exception as e:
        print(f"❌ Erreur scraping {hotel['name']}: {e}")
    finally:
        close_browser(browser)
    
    return snapshots


def scrape_multiple_hotels(hotels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scrape plusieurs hôtels et retourne les statistiques
    
    Args:
        hotels: Liste d'hôtels à scraper
        
    Returns:
        Stats: total_hotels, total_snapshots, errors
    """
    stats = {
        "total_hotels": len(hotels),
        "total_snapshots": 0,
        "successful_hotels": 0,
        "failed_hotels": 0,
        "errors": []
    }
    
    all_snapshots = []
    
    for i, hotel in enumerate(hotels, 1):
        print(f"\n{'='*60}")
        print(f"Hôtel {i}/{len(hotels)}")
        print(f"{'='*60}")
        
        try:
            snapshots = scrape_hotel_prices(hotel)
            all_snapshots.extend(snapshots)
            stats["total_snapshots"] += len(snapshots)
            stats["successful_hotels"] += 1
            
        except Exception as e:
            error_msg = f"Erreur {hotel['name']}: {str(e)}"
            print(f"❌ {error_msg}")
            stats["failed_hotels"] += 1
            stats["errors"].append(error_msg)
        
        # Pause entre hôtels
        if i < len(hotels):
            print(f"\n⏸️ Pause avant hôtel suivant...")
            random_delay(MIN_DELAY_SECONDS * 2, MAX_DELAY_SECONDS * 2)
    
    return stats, all_snapshots


def test_single_hotel():
    """Test avec un seul hôtel"""
    test_hotel = {
        "id": "test-123",
        "name": "Hôtel Test",
        "url": "https://www.booking.com/hotel/fr/chateau-de-roussan.fr.html"
    }
    
    snapshots = scrape_hotel_prices(test_hotel)
    
    print(f"\n📊 Résultat: {len(snapshots)} snapshots")
    for snap in snapshots[:5]:  # Afficher les 5 premiers
        print(f"  {snap['dateCheckin']}: {snap['price']}€ (dispo: {snap['available']})")


if __name__ == "__main__":
    test_single_hotel()
