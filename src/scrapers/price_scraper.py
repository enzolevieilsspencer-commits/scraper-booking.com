"""
Scraper 2 : récupération des prix pour J (aujourd'hui) + 30 jours (J → J+30).

DÉROULEMENT GÉNÉRAL
-------------------
1. On récupère l'URL de l'hôtel telle qu'en base (on n'enlève rien).
2. On charge la page hôtel dans un navigateur "stealth".
3. On accepte les cookies (comme le scraper 1) pour débloquer le site.
4. On clique sur le bouton "Date d'arrivée" pour ouvrir le calendrier.
5. On lit le DOM du calendrier (cellules avec data-date et prix).
6. On extrait les prix pour chaque date et on construit les snapshots.
7. On enregistre les snapshots en base (et le front les affiche).

Approche DOM (plus simple, recommandée) : pas d'interception GraphQL.
"""
from datetime import timedelta, date
from typing import List, Dict, Any, Optional
import random
import sys
import os
import re
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
from config import MIN_DELAY_SECONDS, MAX_DELAY_SECONDS, PAUSE_BETWEEN_HOTELS_MIN, PAUSE_BETWEEN_HOTELS_MAX

# ----- Constantes utilisées dans tout le scraper -----

# Format de date pour la BDD et les logs (ex. 2026-02-11). Pas d'ambiguïté jour/mois.
DATE_FMT = "%Y-%m-%d"

# Sélecteur du bouton "Date d'arrivée" qui ouvre le calendrier.
DATE_BUTTON_SELECTOR = "[data-testid='date-display-field-start']"
# Fallback au cas où le data-testid change après une mise à jour du site.
DATE_BUTTON_FALLBACK_SELECTOR = "button:has-text(\"Date d'arrivée\")"




def get_next_30_days(max_dates: Optional[int] = None) -> List[date]:
    """
    Liste des dates à scraper : J (jour du scraping) + 30 jours = J, J+1, ..., J+30.
    Inclut toujours le jour où le scraping a lieu.
    Si max_dates est fourni (ex. 3 pour test), on garde les N premières dates.
    Si max_dates=30, on retourne 31 jours (aujourd'hui + 30).
    """
    today = date.today()
    days = [today + timedelta(days=i) for i in range(0, 31)]  # J à J+30
    if max_dates is not None and max_dates > 0:
        # 30 = aujourd'hui + 30 jours (31 snapshots)
        n = 31 if max_dates == 30 else min(max_dates, 31)
        days = days[:n]
    return days


def get_dates_from_offsets(offsets: List[int]) -> List[date]:
    """
    Génère les dates à partir d'offsets en jours.
    Ex. : [30] → [J+30], [1, 7, 30] → [J+1, J+7, J+30]. Utile pour --j-plus 30.
    """
    today = date.today()
    return [today + timedelta(days=offset) for offset in sorted(offsets)]


def _parse_avg_price(formatted: str) -> Optional[float]:
    """
    Transforme le champ "avgPriceFormatted" du JSON (ex. "€ 152" ou "€ 0") en nombre.
    Retourne None si absent, "€ 0" ou valeur incohérente (pour filtrer les indispos).
    """
    if not formatted:
        return None
    text = (formatted or "").replace("\xa0", " ").strip()
    m = re.search(r"€\s*(\d[\d\s]*(?:[.,]\d{2})?)", text) or re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)", text)
    if not m:
        return None
    s = m.group(1).replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        p = float(s)
        return p if p >= 10 and p < 10000 else None
    except ValueError:
        return None


def _is_calendar_days_list(days) -> bool:
    """Vérifie si days est une liste de jours calendrier (checkin, avgPriceFormatted)."""
    return (
        isinstance(days, list)
        and len(days) > 0
        and isinstance(days[0], dict)
        and "checkin" in days[0]
    )


def _find_calendar_days(obj) -> Optional[List[Dict]]:
    """Recherche récursive : tout objet avec .days = liste de {checkin, avgPriceFormatted}."""
    if isinstance(obj, dict):
        days = obj.get("days")
        if _is_calendar_days_list(days):
            return days
        for v in obj.values():
            found = _find_calendar_days(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_calendar_days(item)
            if found:
                return found
    return None


def _extract_calendar_from_body(body: Dict) -> Optional[List[Dict]]:
    """
    Extrait la liste des jours du calendrier. Cherche availabilityCalendar.days
    à tous les niveaux (data, property.availabilityCalendar, etc.).
    """
    if not body:
        return None
    return _find_calendar_days(body)


def _find_any_days_in_body(body: Dict) -> str:
    """Debug : cherche toute liste 'days' avec checkin pour localiser le calendrier."""
    found = []

    def search(obj, path=""):
        if isinstance(obj, dict):
            if "days" in obj:
                v = obj["days"]
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    has_checkin = "checkin" in v[0]
                    found.append(f"{path}.days({len(v)}items,checkin={has_checkin})")
            for k, v in obj.items():
                search(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list) and obj:
            for i, item in enumerate(obj[:3]):
                search(item, f"{path}[{i}]")

    try:
        search(body)
        return " | ".join(found[:3]) if found else "aucun days"
    except Exception:
        return "?"


def _get_data_keys_from_body(body: Dict) -> str:
    """Debug : retourne les clés de data pour comprendre la structure."""
    try:
        data = body.get("data")
        if isinstance(data, dict):
            keys = list(data.keys())[:10]
            cal = data.get("availabilityCalendar")
            cal_info = "cal=dict" if isinstance(cal, dict) else "cal=absent" if cal is None else f"cal={type(cal).__name__}"
            return f"{keys} | {cal_info}"
        if isinstance(data, list):
            first = data[0] if data else {}
            k = list(first.keys())[:6] if isinstance(first, dict) else []
            return f"list[{len(data)}] {k}"
    except Exception as e:
        return f"err:{type(e).__name__}"
    return "?"


def _merge_days_into(calendar_days: Dict[str, Dict], days: List[Dict]) -> None:
    """
    Fusionne une liste de "days" (venue de l'API) dans le dictionnaire calendar_days.
    Chaque jour a : checkin (ex. "2026-02-11"), avgPriceFormatted ("€ 152"), available (true/false).
    On en fait un dict checkin → { price (float ou None), available } pour construire les snapshots ensuite.
    """
    for d in days:
        checkin = d.get("checkin")
        if not checkin:
            continue
        available = d.get("available") is True
        formatted = (d.get("avgPriceFormatted") or "").strip()
        price = _parse_avg_price(formatted) if available else None
        if price is None and available and "0" in formatted:
            available = False
        calendar_days[checkin] = {"price": price, "available": available}


def _extract_calendar_from_dom(page) -> Dict[str, Dict]:
    """
    Extrait les prix du calendrier depuis le DOM.
    Structure Booking.com : main > table > tbody > tr > td > span > div > span (prix).
    Cherche aussi [data-date] sur les cellules pour la date.
    Retourne { "2026-02-13": { "price": 152.0, "available": True }, ... }
    """
    result = page.evaluate("""
        () => {
            const out = {};
            const priceRe = /[€$]\\s*(\\d[\\d\\s]*[.,]?\\d*)/;
            // 1) Cellules du calendrier : table dans main (structure XPath fournie)
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
                // Prix dans span > div > span (XPath fourni) ou dans la cellule
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


def scrape_hotel_with_page(page, hotel: Dict[str, Any], dates: List[date]) -> List[Dict[str, Any]]:
    """
    Scrape un hôtel avec une page Playwright déjà ouverte.
    Utilisé par les 3 stratégies (1 nav/hôtel, navigateur partagé, parallèle).
    Charge la page, cookies, clic calendrier, lit le DOM pour extraire les prix.
    Ne crée ni ne ferme le navigateur.
    """
    total = len(dates)
    today = date.today()

    first_str = dates[0].strftime(DATE_FMT)
    last_str = (dates[-1] + timedelta(days=1)).strftime(DATE_FMT)
    sep = "&" if "?" in hotel["url"] else "?"
    url = f"{hotel['url']}{sep}checkin={first_str}&checkout={last_str}"

    snapshots: List[Dict[str, Any]] = []
    calendar_days: Dict[str, Dict] = {}

    try:
        print(f"  [étape 1] Chargement de la page...")
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        random_delay(2, 4)
        print(f"  ✅ [étape 1] Page chargée")

        print(f"  [étape 2] Gestion des cookies...")
        _accept_cookies_if_present(page)
        random_delay(1, 2)
        print(f"  ✅ [étape 2] Cookies traités")

        print(f"  [étape 3] Scroll vers le bas (section Disponibilité)...")
        page.evaluate("window.scrollBy(0, 800)")
        random_delay(0, 1)
        print(f"  ✅ [étape 3] Scroll effectué")

        print(f"  [étape 4] Recherche du bouton « Date d'arrivée »...")
        date_btn = page.locator(DATE_BUTTON_SELECTOR).or_(page.locator(DATE_BUTTON_FALLBACK_SELECTOR)).last
        date_btn.wait_for(state="visible", timeout=10000)
        date_btn.scroll_into_view_if_needed()
        random_delay(0, 1)
        print(f"  ✅ [étape 4] Bouton trouvé et visible")

        print(f"  [étape 5] Clic sur « Date d'arrivée » et lecture du DOM...")
        date_btn.evaluate("""
            el => {
                const target = el.closest('button') || el;
                target.click();
            }
        """)
        # Attendre que le calendrier soit visible
        try:
            page.locator("[data-date], [data-testid*='calendar'], .bui-calendar__day").first.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        # Les prix peuvent charger en async — on attend un peu et on réessaie
        for attempt in range(3):
            time.sleep(1.5 + attempt)
            dom_data = _extract_calendar_from_dom(page)
            if dom_data:
                for checkin, info in dom_data.items():
                    calendar_days[checkin] = info
                if len(calendar_days) >= min(3, total):
                    break
        print(f"  ✅ [étape 5] {len(calendar_days)} jour(s) extrait(s) du DOM")
    except Exception as e:
        print(f"  ❌ Erreur {hotel['name']}: {e}")

    print(f"  [étape 6] Construction des {total} snapshots...")
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
    """
    Pour un seul hôtel : crée un navigateur, appelle scrape_hotel_with_page, ferme.
    Chaque snapshot contient : hotelId, dateCheckin, price (ou None), currency, available.
    """
    if date_offsets is not None:
        dates = get_dates_from_offsets(date_offsets)
    else:
        dates = get_next_30_days(max_dates)
    dates = sorted(dates)
    total = len(dates)
    today = date.today()

    print(f"\n🏨 {hotel['name']} — aujourd'hui = {today.isoformat()} → {total} nuit(s) (DOM calendrier)")

    browser, context, page = create_stealth_browser()
    try:
        snapshots = scrape_hotel_with_page(page, hotel, dates)
    finally:
        close_browser(browser)

    print(f"✅ {hotel['name']}: {len(snapshots)} snapshot(s) (ordre {dates[0].isoformat()} → {dates[-1].isoformat()})")
    return snapshots


# ----- Stratégies multi-hôtels (1=isolé, 2=partagé, 3=parallèle) -----

def _strategy_1_isolated(
    hotels: List[Dict[str, Any]],
    dates: List[date],
    fast_mode: bool,
) -> tuple:
    """Un navigateur par hôtel. Sécurité max, ~2-3 min pour 5 hôtels."""
    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    for i, hotel in enumerate(hotels, 1):
        print(f"\n{'='*60}\nHôtel {i}/{len(hotels)}\n{'='*60}")
        print(f"🏨 {hotel['name']} — {len(dates)} nuit(s)")
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


def _strategy_2_shared_browser(
    hotels: List[Dict[str, Any]],
    dates: List[date],
    fast_mode: bool,
) -> tuple:
    """Un navigateur, un nouvel onglet par hôtel. Plus rapide, ~1-2 min pour 5 hôtels."""
    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    playwright, browser, context, page = create_stealth_browser_full()
    try:
        for i, hotel in enumerate(hotels, 1):
            print(f"\n{'='*60}\nHôtel {i}/{len(hotels)}\n{'='*60}")
            print(f"🏨 {hotel['name']} — {len(dates)} nuit(s)")
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


def _strategy_3_parallel(
    hotels: List[Dict[str, Any]],
    dates: List[date],
    max_workers: int = 2,
) -> tuple:
    """Parallélisation limitée (2 workers par défaut). ~1 min pour 5 hôtels."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_snapshots = []
    stats = {"total_hotels": len(hotels), "total_snapshots": 0, "successful_hotels": 0, "failed_hotels": 0, "errors": []}

    def scrape_one(hotel, idx):
        print(f"\n[Worker {idx}] 🏨 {hotel['name']} — {len(dates)} nuit(s)")
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
    """
    Scrape plusieurs hôtels et retourne (stats, all_snapshots).

    strategy: 1 = un navigateur par hôtel (défaut, le plus sûr),
              2 = un navigateur partagé avec onglets,
              3 = parallèle (2 workers).
    """
    if date_offsets is not None:
        dates = get_dates_from_offsets(date_offsets)
    else:
        dates = get_next_30_days(max_dates_per_hotel)
    dates = sorted(dates)
    fast_mode = date_offsets is not None and len(date_offsets) == 1

    if strategy == 1:
        print("ℹ️ Stratégie 1 : un navigateur par hôtel")
        return _strategy_1_isolated(hotels, dates, fast_mode)
    elif strategy == 2:
        print("ℹ️ Stratégie 2 : navigateur partagé (onglets)")
        return _strategy_2_shared_browser(hotels, dates, fast_mode)
    elif strategy == 3:
        print("ℹ️ Stratégie 3 : parallèle (2 workers)")
        return _strategy_3_parallel(hotels, dates, max_workers=2)
    else:
        return _strategy_1_isolated(hotels, dates, fast_mode)


def test_single_hotel():
    """
    Point d'entrée pour tester le scraper à la main (python src/scrapers/price_scraper.py).
    Utilise un hôtel en dur et affiche les 5 premiers snapshots.
    """
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
