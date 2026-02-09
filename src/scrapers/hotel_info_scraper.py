"""
Scraper 1: Récupération des informations d'un hôtel Booking.com
Usage: Appelé quand on clique sur "Extraire" (ajout concurrent).
- Lance le navigateur normalement, accepte les cookies, charge la page en entier.
- Récupère: nom, adresse, étoiles, image (URL type cf.bstatic.com dans une balise <img>).
- scrape_hotel_info = sync (ThreadPool). scrape_hotel_info_async = async (pour FastAPI /extract).
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
import re
import sys
import os
from typing import Optional, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.stealth_config import (
    create_stealth_browser,
    close_browser,
    random_delay,
    create_stealth_browser_async,
    close_browser_async,
    random_delay_async,
)


# Un peu plus de temps pour que nom/adresse/image soient stables (éviter "Offre à l'établissement", fallback adresse, mauvaise image)
PAGE_LOAD_TIMEOUT_MS = 15_000   # 15 s chargement
CONTENT_READY_TIMEOUT_MS = 12_000  # 12 s pour que le titre soit là
DOM_STABILIZE_DELAY = (2, 3)   # 2–3 s après le titre
ADDRESS_WAIT_DELAY = (2, 3)    # 2–3 s en plus avant adresse (elle charge parfois après)
ADDRESS_VISIBLE_TIMEOUT_MS = 6_000  # attendre que le bloc adresse soit visible
COOKIE_CLICK_TIMEOUT_MS = 2_000
EXTRACT_TIMEOUT_MS = 8_000  # timeout par étape d’extraction (adresse, étoiles, image)

# Sélecteurs bandeau cookies (on clique dès qu’un est visible)
COOKIE_ACCEPT_SELECTORS = [
    "button:has-text('Accepter')",
    "button:has-text('Accept')",
    "button:has-text('OK')",
    "[data-testid='accept-cookies']",
    "button[id*='accept']",
    "a:has-text('Accepter')",
    "a:has-text('Accept')",
]

# Dès qu’UN de ces éléments est présent, on considère le contenu prêt (évite d’attendre un seul sélecteur)
TITLE_SELECTORS_OR = (
    'h2[data-testid="title"], '
    'h1.pp-header__title, '
    '[data-testid="property-name"], '
    '.hp__hotel-name, '
    'h1'
)

# On privilégie le vrai titre (h2 data-testid) pour éviter "Offre à l'établissement..."
NAME_SELECTORS = [
    'h2[data-testid="title"]',
    'h1.pp-header__title',
    '[data-testid="property-name"]',
    '.hp__hotel-name',
    'h1',
]

# Préfixes / suffixes à enlever du nom affiché par Booking
NAME_PREFIXES_TO_STRIP = ("Offre à l'établissement ", "Offre à l'établissement", "Offre à l’établissement ")
NAME_SUFFIXES_TO_STRIP = (
    ", (France)",
    " (France)",
    " (Hôtel)",
    " (Hotel)",
    " (hôtel)",
    " (Établissement)",
)


def _norm_addr(t: str) -> str:
    """Normalise le texte d'adresse (enlever "Voir sur la carte", etc.)."""
    t = (t or "").replace("Voir sur la carte", "").replace("Voir la carte", "").replace("Excellent emplacement -", "").strip().strip("-").strip()
    if "Une fois votre réservation" in t:
        t = t.split("Une fois votre réservation")[0].strip()
    return t if t and len(t) > 8 else ""


def _clean_hotel_name(raw: str) -> str:
    """Enlève 'Offre à l'établissement', ' (Hôtel)', ', (France)', etc."""
    if not raw:
        return raw
    s = raw.strip()
    for prefix in NAME_PREFIXES_TO_STRIP:
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    # Plusieurs suffixes possibles (ex: "...(Hôtel), (France)" → tout enlever)
    changed = True
    while changed:
        changed = False
        for suffix in NAME_SUFFIXES_TO_STRIP:
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
                changed = True
                break
    return s


def _accept_cookies_if_present(page: Page) -> None:
    """Clique sur Accepter / Accept si un bandeau cookies est affiché (rapide)."""
    for selector in COOKIE_ACCEPT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=COOKIE_CLICK_TIMEOUT_MS):
                btn.click(timeout=2000)
                print("  ✅ Cookies / consentement acceptés")
                return
        except Exception:
            continue


async def _accept_cookies_if_present_async(page) -> None:
    """Version async pour scrape_hotel_info_async."""
    for selector in COOKIE_ACCEPT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=COOKIE_CLICK_TIMEOUT_MS):
                await btn.click(timeout=2000)
                print("  ✅ Cookies / consentement acceptés")
                return
        except Exception:
            continue


def scrape_hotel_info(booking_url: str) -> Optional[Dict[str, Any]]:
    """
    Ouvre la page, accepte les cookies, attend le premier bloc "titre" disponible,
    extrait nom, adresse, étoiles, image. Objectif: 15–20 s.
    """
    print(f"🔍 Scraping infos pour: {booking_url}")

    browser, context, page = create_stealth_browser()
    page.set_default_timeout(CONTENT_READY_TIMEOUT_MS)

    try:
        # 1) Chargement
        page.goto(booking_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        random_delay(1, 1)

        # 2) Cookies
        _accept_cookies_if_present(page)
        random_delay(1, 1)

        # 3) Attendre le titre
        page.wait_for_selector(TITLE_SELECTORS_OR, timeout=CONTENT_READY_TIMEOUT_MS, state="attached")
        # Laisser le DOM se stabiliser (adresse, galerie photo)
        random_delay(DOM_STABILIZE_DELAY[0], DOM_STABILIZE_DELAY[1])

        page.set_default_timeout(EXTRACT_TIMEOUT_MS)

        hotel_info = {
            "url": booking_url,
            "name": None,
            "location": None,
            "address": None,
            "stars": None,
            "photoUrl": None,
        }

        # Nom: premier sélecteur qui donne du texte, puis nettoyage "Offre à l'établissement" / " (Hôtel)"
        for sel in NAME_SELECTORS:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    text = el.inner_text().strip()
                    if text and len(text) < 200:
                        hotel_info["name"] = _clean_hotel_name(text)
                        if hotel_info["name"]:
                            print(f"  ✅ Nom: {hotel_info['name']}")
                        break
            except Exception:
                continue
        if not hotel_info["name"]:
            print("  ⚠️ Nom non trouvé")

        # Adresse : laisser un peu plus de temps au bloc (pin + adresse) pour s'afficher
        random_delay(ADDRESS_WAIT_DELAY[0], ADDRESS_WAIT_DELAY[1])
        try:
            page.wait_for_selector(
                'a[href*="maps"], a[href*="map"], span[data-node_tt_id="location_score_tooltip"], [data-testid="property-address"], :has-text("Voir sur la carte")',
                timeout=ADDRESS_VISIBLE_TIMEOUT_MS,
                state="visible",
            )
        except Exception:
            pass  # on essaie quand même d'extraire

        # 1) Bloc adresse Booking : div avec l'adresse en premier noeud texte + sous-div aria-hidden (structure fournie)
        try:
            for selector in [
                'div.b99b6ef58f',
                'div.b06461926f',
                'div.cb4b7a25d9',
                'div:has(> div[aria-hidden="true"]):has-text("France")',
            ]:
                el = page.locator(selector).first
                if el.count() > 0 and el.is_visible(timeout=4000):
                    # Récupérer uniquement le premier noeud texte (l'adresse), pas le div aria-hidden
                    raw = el.evaluate("""el => {
                        const first = el.childNodes[0];
                        return (first && first.nodeType === Node.TEXT_NODE) ? first.textContent.trim() : el.childNodes[0]?.textContent?.trim() || el.innerText;
                    }""")
                    if isinstance(raw, str):
                        raw = _norm_addr(raw)
                    else:
                        raw = _norm_addr(el.inner_text())
                    if raw and re.search(r"\d{5}", raw) and "," in raw:
                        hotel_info["address"] = raw
                        print(f"  ✅ Adresse (bloc Booking): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                        break
            if hotel_info["address"]:
                pass
        except Exception:
            pass

        # 2) Lien "carte" dont le texte est l'adresse complète
        if not hotel_info["address"]:
            try:
                for a in page.locator('a[href*="maps"], a[href*="map"]').all():
                    try:
                        raw = a.inner_text().strip()
                        if raw and len(raw) > 25 and "," in raw and re.search(r"\d{5}", raw):
                            hotel_info["address"] = _norm_addr(raw)
                            if hotel_info["address"]:
                                print(f"  ✅ Adresse (lien carte): {hotel_info['address'][:70]}{'...' if len(hotel_info['address']) > 70 else ''}")
                                break
                    except Exception:
                        continue
            except Exception:
                pass

        # 2) Sibling / bloc juste sous le titre (pin + adresse)
        if not hotel_info["address"]:
            try:
                title_loc = page.locator('h2[data-testid="title"]').first
                if title_loc.count() > 0:
                    for sibling_sel in ["+ span", "+ div", "+ p", "+ a", "+ *"]:
                        try:
                            next_el = title_loc.locator(sibling_sel).first
                            if next_el.count() > 0 and next_el.is_visible(timeout=4000):
                                raw = next_el.inner_text().strip()
                                raw = _norm_addr(raw)
                                if raw and raw.lower() not in ("carte", "voir", "accepter"):
                                    hotel_info["address"] = raw
                                    print(f"  ✅ Adresse (sous le nom): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                                    break
                        except Exception:
                            continue
            except Exception:
                pass

        # 3) Autres sélecteurs Booking
        if not hotel_info["address"]:
            for selector, label in [
                ('span[data-node_tt_id="location_score_tooltip"]', "tooltip"),
                ('[data-testid="property-address"]', "property-address"),
                ('[data-testid="address"]', "address"),
                ('span:has-text("Voir sur la carte")', "Voir sur la carte"),
            ]:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=4500):
                        raw = _norm_addr(el.inner_text().strip())
                        if raw:
                            hotel_info["address"] = raw
                            print(f"  ✅ Adresse ({label}): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                            break
                except Exception:
                    continue
        if not hotel_info["address"]:
            print("  ⚠️ Adresse non trouvée")

        # Ville (dérivée de l'adresse)
        if hotel_info["address"]:
            parts = hotel_info["address"].split(",")
            hotel_info["location"] = parts[-2].strip() if len(parts) >= 2 else hotel_info["address"]
        else:
            hotel_info["location"] = ""

        # Étoiles
        try:
            stars_el = page.locator('[data-testid="rating-stars"]').first
            aria = stars_el.get_attribute("aria-label")
            if aria:
                m = re.search(r"(\d+)", aria)
                if m:
                    hotel_info["stars"] = int(m.group(1))
                    print(f"  ✅ Étoiles: {hotel_info['stars']}")
        except Exception as e:
            print(f"  ⚠️ Étoiles non trouvées: {e}")

        # Image: la PLUS GRANDE (hero extérieur), pas les chambres ni miniatures
        try:
            photo_url = None
            # 1) Image déclarée "main" par Booking
            main_img = page.locator('img[data-testid="main-image"]').first
            if main_img.count() > 0:
                candidate = main_img.get_attribute("src")
                if candidate and "bstatic.com" in candidate:
                    photo_url = candidate.strip()
            # 2) Première image de la galerie principale (hero), pas la grille de miniatures
            if not photo_url:
                try:
                    hero_container = page.locator("[data-testid='property-gallery']").first
                    if hero_container.count() > 0:
                        first_img = hero_container.locator("img[src*='bstatic.com']").first
                        if first_img.count() > 0:
                            photo_url = (first_img.get_attribute("src") or "").strip()
                except Exception:
                    pass
            # 3) Prendre la première image max1280 (la plus grande = souvent l’extérieur)
            if not photo_url:
                for sel in [
                    'img[src*="bstatic.com"][src*="max1280"]',
                    'img[src*="bstatic.com"][src*="max1024"]',
                ]:
                    imgs = page.locator(sel).all()
                    for img_el in imgs[:3]:  # max 3 premières
                        try:
                            src = img_el.get_attribute("src")
                            if src and "bstatic.com" in src:
                                # Éviter les petites (thumbnails souvent en max500 ou sans max)
                                if "max1280" in src or "max1024" in src:
                                    photo_url = src.strip()
                                    break
                        except Exception:
                            continue
                    if photo_url:
                        break
            # 4) Fallback: première bstatic (hors petites vignettes)
            if not photo_url:
                for img_el in page.locator('img[src*="bstatic.com"]').all()[:5]:
                    try:
                        src = (img_el.get_attribute("src") or "").strip()
                        if "max" in src and ("1024" in src or "1280" in src):
                            photo_url = src
                            break
                    except Exception:
                        continue
            if photo_url:
                hotel_info["photoUrl"] = photo_url
                print(f"  ✅ Photo récupérée (bstatic)")
            else:
                print(f"  ⚠️ Aucune image bstatic trouvée")
        except Exception as e:
            print(f"  ⚠️ Photo non trouvée: {e}")

        print(f"✅ Scraping terminé pour {hotel_info['name']}")
        return hotel_info

    except PlaywrightTimeout:
        print("❌ Timeout lors du chargement de la page")
        return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None
    finally:
        close_browser(browser)


async def scrape_hotel_info_async(booking_url: str) -> Optional[Dict[str, Any]]:
    """
    Même logique que scrape_hotel_info mais en async (API Playwright async).
    À utiliser depuis FastAPI /extract pour éviter "Sync API inside asyncio loop".
    """
    playwright = None
    browser = None
    try:
        playwright, browser, context, page = await create_stealth_browser_async()
        page.set_default_timeout(CONTENT_READY_TIMEOUT_MS)

        print("Scraping infos pour: %s" % booking_url[:80])
        await page.goto(booking_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        await random_delay_async(1, 1)
        await _accept_cookies_if_present_async(page)
        await random_delay_async(1, 1)
        # Même sélecteur large que la version sync (évite timeout si le DOM varie)
        await page.wait_for_selector(TITLE_SELECTORS_OR, timeout=CONTENT_READY_TIMEOUT_MS, state="attached")
        await random_delay_async(DOM_STABILIZE_DELAY[0], DOM_STABILIZE_DELAY[1])
        page.set_default_timeout(EXTRACT_TIMEOUT_MS)

        hotel_info: Dict[str, Any] = {"name": "", "location": "", "address": "", "stars": 0, "photoUrl": ""}

        # Nom: même logique que sync (NAME_SELECTORS + _clean_hotel_name)
        for sel in NAME_SELECTORS:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    text = (await loc.inner_text()).strip()
                    if text and len(text) < 200:
                        hotel_info["name"] = _clean_hotel_name(text)
                        if hotel_info["name"]:
                            print(f"  ✅ Nom: {hotel_info['name']}")
                        break
            except Exception:
                continue
        if not hotel_info["name"]:
            print("  ⚠️ Nom non trouvé")

        # Adresse: même logique que sync (plusieurs fallbacks)
        print("  🔍 Recherche de l'adresse...")
        await random_delay_async(ADDRESS_WAIT_DELAY[0], ADDRESS_WAIT_DELAY[1])
        try:
            await page.wait_for_selector(
                'a[href*="maps"], a[href*="map"], span[data-node_tt_id="location_score_tooltip"], [data-testid="property-address"], :has-text("Voir sur la carte")',
                timeout=ADDRESS_VISIBLE_TIMEOUT_MS,
                state="visible",
            )
        except Exception:
            pass

        # 1) Bloc adresse Booking (div avec classe Booking)
        try:
            for selector in [
                'div.b99b6ef58f',
                'div.b06461926f',
                'div.cb4b7a25d9',
                'div:has(> div[aria-hidden="true"]):has-text("France")',
            ]:
                el = page.locator(selector).first
                if await el.count() > 0 and await el.is_visible(timeout=4000):
                    raw = await el.evaluate("""el => {
                        const first = el.childNodes[0];
                        return (first && first.nodeType === Node.TEXT_NODE) ? first.textContent.trim() : el.childNodes[0]?.textContent?.trim() || el.innerText;
                    }""")
                    if isinstance(raw, str):
                        raw = _norm_addr(raw)
                    else:
                        raw = _norm_addr(await el.inner_text())
                    if raw and re.search(r"\d{5}", raw) and "," in raw:
                        hotel_info["address"] = raw
                        print(f"  ✅ Adresse (bloc Booking): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                        break
        except Exception:
            pass

        # 2) Lien "carte" dont le texte est l'adresse complète
        if not hotel_info["address"]:
            try:
                for a in await page.locator('a[href*="maps"], a[href*="map"]').all():
                    try:
                        raw = (await a.inner_text()).strip()
                        if raw and len(raw) > 25 and "," in raw and re.search(r"\d{5}", raw):
                            hotel_info["address"] = _norm_addr(raw)
                            if hotel_info["address"]:
                                print(f"  ✅ Adresse (lien carte): {hotel_info['address'][:70]}{'...' if len(hotel_info['address']) > 70 else ''}")
                                break
                    except Exception:
                        continue
            except Exception:
                pass

        # 3) Sibling sous le titre (pin + adresse)
        if not hotel_info["address"]:
            try:
                title_loc = page.locator('h2[data-testid="title"]').first
                if await title_loc.count() > 0:
                    for sibling_sel in ["+ span", "+ div", "+ p", "+ a", "+ *"]:
                        try:
                            next_el = title_loc.locator(sibling_sel).first
                            if await next_el.count() > 0 and await next_el.is_visible(timeout=4000):
                                raw = (await next_el.inner_text()).strip()
                                raw = _norm_addr(raw)
                                if raw and raw.lower() not in ("carte", "voir", "accepter"):
                                    hotel_info["address"] = raw
                                    print(f"  ✅ Adresse (sous le nom): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                                    break
                        except Exception:
                            continue
            except Exception:
                pass

        # 4) Autres sélecteurs Booking
        if not hotel_info["address"]:
            for selector, label in [
                ('span[data-node_tt_id="location_score_tooltip"]', "tooltip"),
                ('[data-testid="property-address"]', "property-address"),
                ('[data-testid="address"]', "address"),
                ('span:has-text("Voir sur la carte")', "Voir sur la carte"),
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible(timeout=4500):
                        raw = _norm_addr((await el.inner_text()).strip())
                        if raw:
                            hotel_info["address"] = raw
                            print(f"  ✅ Adresse ({label}): {raw[:70]}{'...' if len(raw) > 70 else ''}")
                            break
                except Exception:
                    continue
        if not hotel_info["address"]:
            print("  ⚠️ Adresse non trouvée")

        # Ville (dérivée de l'adresse) → location pour l'API
        if hotel_info["address"]:
            parts = hotel_info["address"].split(",")
            hotel_info["location"] = parts[-2].strip() if len(parts) >= 2 else hotel_info["address"]
        else:
            hotel_info["location"] = ""

        # Étoiles
        try:
            stars_el = page.locator('[data-testid="rating-stars"]').first
            if await stars_el.count() > 0:
                aria = await stars_el.get_attribute("aria-label")
                if aria:
                    m = re.search(r"(\d+)", aria)
                    if m:
                        hotel_info["stars"] = int(m.group(1))
                        print(f"  ✅ Étoiles: {hotel_info['stars']}")
        except Exception as e:
            print(f"  ⚠️ Étoiles non trouvées: {e}")

        # Image (même logique qu'en sync, en await)
        try:
            photo_url = None
            main_img = page.locator('img[data-testid="main-image"]').first
            if await main_img.count() > 0:
                candidate = await main_img.get_attribute("src")
                if candidate and "bstatic.com" in candidate:
                    photo_url = candidate.strip()
            if not photo_url:
                try:
                    hero_container = page.locator("[data-testid='property-gallery']").first
                    if await hero_container.count() > 0:
                        first_img = hero_container.locator("img[src*='bstatic.com']").first
                        if await first_img.count() > 0:
                            photo_url = (await first_img.get_attribute("src") or "").strip()
                except Exception:
                    pass
            if not photo_url:
                for sel in [
                    'img[src*="bstatic.com"][src*="max1280"]',
                    'img[src*="bstatic.com"][src*="max1024"]',
                ]:
                    imgs = await page.locator(sel).all()
                    for img_el in imgs[:3]:
                        try:
                            src = await img_el.get_attribute("src")
                            if src and "bstatic.com" in src and ("max1280" in src or "max1024" in src):
                                photo_url = src.strip()
                                break
                        except Exception:
                            continue
                    if photo_url:
                        break
            if not photo_url:
                all_imgs = await page.locator('img[src*="bstatic.com"]').all()
                for img_el in all_imgs[:5]:
                    try:
                        src = (await img_el.get_attribute("src") or "").strip()
                        if "max" in src and ("1024" in src or "1280" in src):
                            photo_url = src
                            break
                    except Exception:
                        continue
            if photo_url:
                hotel_info["photoUrl"] = photo_url
                print(f"  ✅ Photo récupérée (bstatic)")
            else:
                print(f"  ⚠️ Aucune image bstatic trouvée")
        except Exception as e:
            print(f"  ⚠️ Photo non trouvée: {e}")

        print(f"✅ Scraping terminé pour {hotel_info['name']}")
        return hotel_info

    except Exception as e:
        if "Timeout" in str(type(e).__name__) or "timeout" in str(e).lower():
            print("❌ Timeout lors du chargement de la page")
        else:
            print(f"❌ Erreur: {e}")
        return None
    finally:
        if playwright is not None and browser is not None:
            await close_browser_async(playwright, browser)


def test_scraper():
    """Test manuel."""
    test_url = "https://www.booking.com/hotel/fr/chateau-de-roussan.fr.html"
    result = scrape_hotel_info(test_url)
    if result:
        print("\n📊 Résultat:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print("\n❌ Échec du scraping")


if __name__ == "__main__":
    test_scraper()
