"""
Configuration Playwright avec mode stealth pour éviter la détection
Sync et async pour compatibilité FastAPI (asyncio).
"""
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import random
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import USER_AGENTS, HEADLESS_MODE


def get_random_user_agent() -> str:
    """Retourne un User-Agent aléatoire"""
    return random.choice(USER_AGENTS)


def create_stealth_browser() -> tuple[Browser, BrowserContext, Page]:
    """
    Crée un navigateur Playwright en mode stealth
    Returns: (browser, context, page)
    """
    playwright = sync_playwright().start()
    
    # Lancer Chrome en mode stealth
    browser = playwright.chromium.launch(
        headless=HEADLESS_MODE,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )
    
    # Créer contexte avec User-Agent aléatoire
    context = browser.new_context(
        user_agent=get_random_user_agent(),
        viewport={'width': 1920, 'height': 1080},
        locale='fr-FR',
        timezone_id='Europe/Paris',
        # Simule un vrai navigateur
        extra_http_headers={
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    )
    
    # Masquer les propriétés Webdriver
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en']
        });
        
        window.chrome = {
            runtime: {}
        };
        
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' })
            })
        });
    """)
    
    page = context.new_page()
    
    print(f"✅ Navigateur stealth créé (headless={HEADLESS_MODE})")
    return browser, context, page


def close_browser(browser: Browser):
    """Ferme proprement le navigateur"""
    try:
        browser.close()
        print("✅ Navigateur fermé")
    except Exception as e:
        print(f"⚠️ Erreur fermeture navigateur: {e}")


def create_stealth_browser_full():
    """
    Crée un navigateur Playwright en mode stealth et retourne aussi playwright
    pour permettre close_browser_full() (utilisé par les stratégies multi-hôtels).
    Returns: (playwright, browser, context, page)
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=HEADLESS_MODE,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )
    context = browser.new_context(
        user_agent=get_random_user_agent(),
        viewport={'width': 1920, 'height': 1080},
        locale='fr-FR',
        timezone_id='Europe/Paris',
        extra_http_headers={'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'},
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'permissions', { get: () => ({ query: () => Promise.resolve({ state: 'granted' }) }) });
    """)
    page = context.new_page()
    print(f"✅ Navigateur stealth créé (headless={HEADLESS_MODE})")
    return playwright, browser, context, page


def close_browser_full(playwright, browser: Browser):
    """Ferme le navigateur et arrête Playwright (pour les stratégies multi-hôtels)."""
    try:
        browser.close()
        playwright.stop()
        print("✅ Navigateur fermé")
    except Exception as e:
        print(f"⚠️ Erreur fermeture navigateur: {e}")


def random_delay(min_seconds: int = 2, max_seconds: int = 5):
    """Attend un délai aléatoire (simulation comportement humain)"""
    import time
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


# --- API asynchrone (pour FastAPI / asyncio, évite "Sync API inside asyncio loop") ---

async def random_delay_async(min_seconds: float = 2, max_seconds: float = 5) -> None:
    """Délai aléatoire async (pour use dans scraper async)."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def create_stealth_browser_async():
    """
    Crée un navigateur Playwright en mode stealth (API async).
    Returns: (playwright, browser, context, page) — garder playwright pour le fermer à la fin.
    """
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=HEADLESS_MODE,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )
    context = await browser.new_context(
        user_agent=get_random_user_agent(),
        viewport={'width': 1920, 'height': 1080},
        locale='fr-FR',
        timezone_id='Europe/Paris',
        extra_http_headers={
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en']
        });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({ query: () => Promise.resolve({ state: 'granted' }) })
        });
    """)
    page = await context.new_page()
    print("✅ Navigateur stealth créé (headless=%s)" % HEADLESS_MODE)
    return p, browser, context, page


async def close_browser_async(playwright, browser):
    """Ferme le navigateur et arrête Playwright (async)."""
    try:
        await browser.close()
        await playwright.stop()
        print("✅ Navigateur fermé")
    except Exception as e:
        print("⚠️ Erreur fermeture navigateur: %s" % e)
