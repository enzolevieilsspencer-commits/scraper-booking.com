"""
Scraper prix : J (aujourd'hui) + 30 jours.
Charge la page, scroll 800px (première action), cookies, ouvre le calendrier, extrait les prix du DOM.
"""
from datetime import timedelta, date
from typing import List, Dict, Any, Optional
import random
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.stealth_config import (
    create_stealth_browser,
    close_browser,
    create_stealth_browser_full,
    close_browser_full,
    random_delay,
)
from scrapers.hotel_info_scraper import _accept_cookies_if_present
from config import PAUSE_BETWEEN_HOTELS_MIN, PAUSE_BETWEEN_HOTELS_MAX

# ----- Constantes -----

DATE_FMT = "%Y-%m-%d"
SCROLL_PIXELS = 800

# Sélecteurs du bouton "Date d'arrivée"
DATE_BUTTON_SELECTOR = "[data-testid='date-display-field-start']"
DATE_BUTTON_FALLBACK_SELECTOR = "button:has-text(\"Date d'arrivée\")"

# Sélecteur pour attendre le calendrier visible
CALENDAR_VISIBLE_SELECTOR = "[data-date], [data-testid*='calendar'], .bui-calendar__day"


# ----- Dates -----

def get_next_30_days(max_dates: Optional[int] = None) -> List[date]:
    """J à J+30. max_dates=30 → 31 jours, max_dates=3 → 3 jours."""
    today = date.today()
    days = [today + timedelta(days=i) for i in range(0, 31)]
    if max_dates is not None and max_dates > 0:
        n = 31 if max_dates == 30 else min(max_dates, 31)
        days = days[:n]
    return days


def get_dates_from_offsets(offsets: List[int]) -> List[date]:
    """Ex: [30] → [J+30], [1, 7, 30] → [J+1, J+7, J+30]."""
    today = date.today()
    return [today + timedelta(days=offset) for offset in sorted(offsets)]


# ----- Extraction DOM -----

def _extract_calendar_from_dom(page) -> Dict[str, Dict]:
    """
    Extrait les prix du calendrier depuis le DOM.
    Retourne { "2026-02-13": { "price": 152.0, "available": True }, ... }
    """
    result = page.evaluate("""
        () => {
            const out = {};
            const priceRe = /[€$]\\s*(\\d[\\d\\s]*[.,]?\\d*)/;
            let cells = document.querySelectorAll('main table tbody tr td');
            if (cells.length < 5) {
                cells = document.querySelectorAll('[data-date]');
            }
            if (cells.length < 5) {
                cells = document.querySelectorAll('table tbody tr td');
            }
            for (const cell of cells) {
                const dateStr = cell.getAttribute('data-date') || 
                    cell.querySelector('[data-date]')?.getAttribute('data-date') ||
                    cell.closest('[data-date]')?.getAttribute('data-date') || '';
                if (!dateStr) continue;
                let checkin = '';
                const isoMatch = dateStr.match(/^(\\d{4})-(\\d{2})-(\\d{2})/);
                if (isoMatch) {
                    checkin = isoMatch[0];
                } else {
                    const digits = dateStr.replace(/\\D/g, '');
                    if (digits.length >= 8) {
                        checkin = digits.slice(0,4) + '-' + digits.slice(4,6) + '-' + digits.slice(6,8);
                    }
                }
                if (!checkin) continue;
                const priceSpan = cell.querySelector('span div span') || cell.querySelector('span span') || cell.querySelector('span');
                const priceText = (priceSpan?.textContent || cell.textContent || '').trim();
                const m = priceText.match(priceRe);
                const price = m ? parseFloat(m[1].replace(/\\s/g,'').replace(',','.')) : null;
                const disabled = cell.hasAttribute('disabled') || cell.getAttribute('aria-disabled') === 'true' ||
                    (cell.className && /disabled|unavailable|blocked|grayed/i.test(cell.className));
                const available = !disabled && price !== null && price >= 10;
                if (!(checkin in out) || available) {
                    out[checkin] = { price: available ? price : null, available };
                }
            }
            return out;
        }
    """)
    return result or {}


# ----- Scraping principal -----

def scrape_hotel_with_page(page, hotel: Dict[str, Any], dates: List[date]) -> List[Dict[str, Any]]:
    """
    Scrape un hôtel avec une page Playwright déjà ouverte.
    Première action : scroll 800px vers le bas.
    """
    first_str = dates[0].strftime(DATE_FMT)
    last_str = (dates[-1] + timedelta(days=1)).strftime(DATE_FMT)
    sep = "&" if "?" in hotel["url"] else "?"
    url = f"{hotel['url']}{sep}checkin={first_str}&checkout={last_str}"

    snapshots: List[Dict[str, Any]] = []
    calendar_days: Dict[str, Dict] = {}
    total = len(dates)

    try:
        # 1. Chargement
        print(f"  [1] Chargement de la page...")
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        random_delay(2, 4)
        print(f"  ✅ Page chargée")

        # 2. Première action : scroll 800px vers le bas
        print(f"  [2] Scroll {SCROLL_PIXELS}px vers le bas (première action)...")
        page.evaluate(f"window.scrollBy(0, {SCROLL_PIXELS})")
        random_delay(0, 1)
        print(f"  ✅ Scroll effectué")

        # 3. Cookies
        print(f"  [3] Gestion des cookies...")
        _accept_cookies_if_present(page)
        random_delay(1, 2)
        print(f"  ✅ Cookies traités")

        # 4. Bouton Date d'arrivée
        print(f"  [4] Recherche du bouton « Date d'arrivée »...")
        date_btn = page.locator(DATE_BUTTON_SELECTOR).or_(page.locator(DATE_BUTTON_FALLBACK_SELECTOR)).last
        date_btn.wait_for(state="visible", timeout=10000)
        date_btn.scroll_into_view_if_needed()
        random_delay(0, 1)
        print(f"  ✅ Bouton trouvé")

        # 5. Clic et extraction DOM
        print(f"  [5] Clic sur « Date d'arrivée » et lecture du calendrier...")
        date_btn.evaluate("""
            el => {
                const target = el.closest('button') || el;
                target.click();
            }
        """)
        try:
            page.locator(CALENDAR_VISIBLE_SELECTOR).first.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        for attempt in range(3):
            time.sleep(1.5 + attempt)
            dom_data = _extract_calendar_from_dom(page)
            if dom_data:
                for checkin, info in dom_data.items():
                    calendar_days[checkin] = info
                if len(calendar_days) >= min(3, total):
                    break
        print(f"  ✅ {len(calendar_days)} jour(s) extrait(s)")

    except Exception as e:
        print(f"  ❌ Erreur {hotel['name']}: {e}")

    # 6. Construction des snapshots
    print(f"  [6] Construction des {total} snapshots...")
    for i, checkin_date in enumerate(dates, 1):
        checkin_str = checkin_date.strftime(DATE_FMT)
        info = calendar_days.get(checkin_str, {})
        price = info.get("price")
        available = info.get("available", False) if not info else (price is not None)
        snapshots.append({
            "hotelId": hotel["id"],
            "dateCheckin": checkin_str,
            "price": price,
            "currency": "EUR",
            "available": available,
        })
        print(f"  📅 {i}/{total} {checkin_str} → {f'{price}€' if price else 'Indisponible'}")

    return sorted(snapshots, key=lambda s: s["dateCheckin"])


def scrape_hotel_prices(
    hotel: Dict[str, Any],
    max_dates: Optional[int] = None,
    date_offsets: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Un seul hôtel : crée le navigateur, scrape, ferme."""
    if date_offsets is not None:
        dates = get_dates_from_offsets(date_offsets)
    else:
        dates = get_next_30_days(max_dates)
    dates = sorted(dates)

    print(f"\n🏨 {hotel['name']} — {len(dates)} nuit(s)")

    browser, context, page = create_stealth_browser()
    try:
        snapshots = scrape_hotel_with_page(page, hotel, dates)
    finally:
        close_browser(browser)

    print(f"✅ {hotel['name']}: {len(snapshots)} snapshot(s)")
    return snapshots


# ----- Stratégies multi-hôtels -----

def _strategy_1_isolated(hotels: List[Dict], dates: List[date], fast_mode: bool) -> tuple:
    """Un navigateur par hôtel."""
    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    for i, hotel in enumerate(hotels, 1):
        print(f"\n{'='*60}\nHôtel {i}/{len(hotels)}\n{'='*60}")
        try:
            playwright, browser, context, page = create_stealth_browser_full()
            try:
                snapshots = scrape_hotel_with_page(page, hotel, dates)
                all_snapshots.extend(snapshots)
                stats["total_snapshots"] += len(snapshots)
                stats["successful_hotels"] += 1
            finally:
                close_browser_full(playwright, browser)
        except Exception as e:
            stats["failed_hotels"] += 1
            stats["errors"].append(f"{hotel['name']}: {e}")
            print(f"❌ {e}")
        if i < len(hotels):
            delay = random.uniform(PAUSE_BETWEEN_HOTELS_MIN, PAUSE_BETWEEN_HOTELS_MAX)
            print(f"\n⏸️ Pause {delay:.1f}s...")
            time.sleep(delay)

    return stats, all_snapshots


def _strategy_2_shared_browser(hotels: List[Dict], dates: List[date], fast_mode: bool) -> tuple:
    """Un navigateur, un onglet par hôtel."""
    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    playwright, browser, context, page = create_stealth_browser_full()
    try:
        for i, hotel in enumerate(hotels, 1):
            print(f"\n{'='*60}\nHôtel {i}/{len(hotels)}\n{'='*60}")
            try:
                if i > 1:
                    page = context.new_page()
                snapshots = scrape_hotel_with_page(page, hotel, dates)
                all_snapshots.extend(snapshots)
                stats["total_snapshots"] += len(snapshots)
                stats["successful_hotels"] += 1
            except Exception as e:
                stats["failed_hotels"] += 1
                stats["errors"].append(f"{hotel['name']}: {e}")
                print(f"❌ {e}")
            finally:
                if i > 1:
                    try:
                        page.close()
                    except Exception:
                        pass
            if i < len(hotels):
                delay = random.uniform(PAUSE_BETWEEN_HOTELS_MIN, PAUSE_BETWEEN_HOTELS_MAX)
                print(f"\n⏸️ Pause {delay:.1f}s...")
                time.sleep(delay)
    finally:
        close_browser_full(playwright, browser)

    return stats, all_snapshots


def _strategy_3_parallel(hotels: List[Dict], dates: List[date], max_workers: int = 2) -> tuple:
    """Parallèle (2 workers)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    def scrape_one(hotel, idx):
        try:
            playwright, browser, context, page = create_stealth_browser_full()
            try:
                snapshots = scrape_hotel_with_page(page, hotel, dates)
                return {"ok": True, "snapshots": snapshots}
            finally:
                close_browser_full(playwright, browser)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_one, h, i): h for i, h in enumerate(hotels, 1)}
        for future in as_completed(futures):
            hotel = futures[future]
            try:
                r = future.result()
                if r["ok"]:
                    all_snapshots.extend(r["snapshots"])
                    stats["total_snapshots"] += len(r["snapshots"])
                    stats["successful_hotels"] += 1
                else:
                    stats["failed_hotels"] += 1
                    stats["errors"].append(f"{hotel['name']}: {r['error']}")
            except Exception as e:
                stats["failed_hotels"] += 1
                stats["errors"].append(f"{hotel['name']}: {e}")

    return stats, all_snapshots


def scrape_multiple_hotels(
    hotels: List[Dict[str, Any]],
    max_dates_per_hotel: Optional[int] = None,
    date_offsets: Optional[List[int]] = None,
    strategy: int = 1,
) -> tuple:
    """Scrape plusieurs hôtels. strategy: 1=isolé, 2=partagé, 3=parallèle."""
    if date_offsets is not None:
        dates = get_dates_from_offsets(date_offsets)
    else:
        dates = get_next_30_days(max_dates_per_hotel)
    dates = sorted(dates)

    if strategy == 1:
        return _strategy_1_isolated(hotels, dates, False)
    elif strategy == 2:
        return _strategy_2_shared_browser(hotels, dates, False)
    elif strategy == 3:
        return _strategy_3_parallel(hotels, dates, max_workers=2)
    return _strategy_1_isolated(hotels, dates, False)


# ----- Test -----

def test_single_hotel():
    """Point d'entrée : python src/scrapers/price_scraper.py"""
    test_hotel = {
        "id": "test-123",
        "name": "Hôtel Test",
        "url": "https://www.booking.com/hotel/fr/chateau-de-roussan.fr.html"
    }
    snapshots = scrape_hotel_prices(test_hotel)
    print(f"\n📊 Résultat: {len(snapshots)} snapshots")
    for snap in snapshots[:5]:
        print(f"  {snap['dateCheckin']}: {snap['price']}€ (dispo: {snap['available']})")


if __name__ == "__main__":
    test_single_hotel()
