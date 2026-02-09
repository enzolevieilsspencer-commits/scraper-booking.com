"""
Configuration centrale du projet
"""
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# API Configuration (Railway injecte PORT, sinon API_PORT ou 8000)
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT") or os.getenv("API_PORT", "8000"))

# Scraping Configuration
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "30"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "60"))
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "true").lower() == "true"

# Session Times (random ranges in hours)
SESSION_1_START_HOUR = int(os.getenv("SESSION_1_START_HOUR", "8"))
SESSION_1_END_HOUR = int(os.getenv("SESSION_1_END_HOUR", "11"))
SESSION_2_START_HOUR = int(os.getenv("SESSION_2_START_HOUR", "14"))
SESSION_2_END_HOUR = int(os.getenv("SESSION_2_END_HOUR", "17"))

# User Agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Validation
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY doivent être définis dans .env")

print(f"✅ Configuration chargée - Environment: {ENVIRONMENT}")
