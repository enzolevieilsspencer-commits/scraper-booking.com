# 🏨 Booking.com Scraper - Veille Concurrentielle

Système de scraping automatisé pour surveiller les prix de 6 hôtels à Saint-Rémy-de-Provence.

## 📁 Architecture

- **Scraper 1** : Récupération des infos hôtel (manuel, via API)
- **Scraper 2** : Surveillance des prix sur 30 jours (automatique, 1x/jour)

## 🚀 Installation

### Prérequis
- Python 3.10+
- pip

### Setup

```bash
# Cloner le projet
cd booking-scraper-project

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou : venv\Scripts\activate  # Windows

# Installer dépendances
pip install -r requirements.txt

# Installer Playwright browsers
playwright install chromium

# Configurer variables d'environnement
cp .env.example .env
# Éditer .env avec vos vraies valeurs
```

## ⚙️ Configuration

Éditer le fichier `.env` :

```env
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
ENVIRONMENT=development
```

## 🎯 Utilisation

### Scraper 1 : Infos Hôtel (API)

Démarrer le serveur API :

```bash
python src/api/server.py
```

Endpoint : `POST http://localhost:8000/scrape-hotel`

Body :
```json
{
  "url": "https://www.booking.com/hotel/fr/..."
}
```

### Scraper 2 : Prix Automatique

Exécution manuelle (test) :
```bash
python src/scheduler/run_price_scraper.py
```

Exécution automatique (production) :
```bash
python src/scheduler/cron_jobs.py
```

## 📊 Tables Supabase

### Table `hotels`
```sql
CREATE TABLE hotels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  address TEXT,
  url TEXT NOT NULL,
  stars INTEGER,
  "photoUrl" TEXT,
  "isClient" BOOLEAN DEFAULT FALSE,
  "isMonitored" BOOLEAN DEFAULT TRUE,
  "createdAt" TIMESTAMP DEFAULT NOW(),
  "updatedAt" TIMESTAMP DEFAULT NOW()
);
```

### Table `rate_snapshots`
```sql
CREATE TABLE rate_snapshots (
  id TEXT PRIMARY KEY,
  "hotelId" TEXT NOT NULL REFERENCES hotels(id),
  "dateCheckin" DATE NOT NULL,
  price FLOAT8,
  currency TEXT DEFAULT 'EUR',
  available BOOLEAN DEFAULT TRUE,
  "scrapedAt" TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rate_snapshots_hotel_date 
ON rate_snapshots("hotelId", "dateCheckin", "scrapedAt");
```

### Table `scraper_logs` (optionnel)
```sql
CREATE TABLE scraper_logs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  "hotelId" TEXT,
  "snapshotsCreated" INTEGER,
  error TEXT,
  "startedAt" TIMESTAMP DEFAULT NOW(),
  "completedAt" TIMESTAMP
);
```

## 🚢 Déploiement sur Railway

Le projet utilise un **Dockerfile** avec Playwright + Chromium préinstallé (évite les timeouts de téléchargement).

### Étapes

1. **Créer un projet** sur [Railway](https://railway.app)
2. **New Project** → **Deploy from GitHub repo** → sélectionner ce dépôt
3. **Variables d'environnement** (Settings → Variables) :
   | Variable | Description |
   |----------|-------------|
   | `SUPABASE_URL` | URL du projet Supabase |
   | `SUPABASE_SERVICE_KEY` | Clé service (secret) |
   | `ENVIRONMENT` | `production` |
4. **Déploiement** : Railway détecte le Dockerfile et build automatiquement
5. **Domaine** : Settings → Networking → Generate Domain (pour exposer l'API)

### Endpoints déployés

- `GET /` — Info API
- `GET /health` — Health check
- `POST /extract` — Extraire infos hôtel (Next.js)
- `POST /scrape-hotel` — Scraper et enregistrer un hôtel
- `POST /scrape-prices` — Lancer le scraping des prix

## 🔒 Sécurité

- ✅ User-Agent rotation
- ✅ Délais aléatoires entre requêtes
- ✅ Horaires d'exécution randomisés
- ✅ Playwright en mode stealth
- ✅ Sessions séparées (3 hôtels matin, 3 hôtels après-midi)

## 📝 Logs

Les logs sont écrits dans :
- Console (stdout)
- Table `scraper_logs` (Supabase)

## 🐛 Debug

```bash
# Test scraper infos
python -c "from src.scrapers.hotel_info_scraper import scrape_hotel_info; print(scrape_hotel_info('URL_BOOKING'))"

# Test scraper prix
python src/scheduler/run_price_scraper.py --test
```

## 📧 Support

En cas de problème, vérifier :
1. Les logs dans Railway/Console
2. La table `scraper_logs` dans Supabase
3. Que Playwright est bien installé
4. Les variables d'environnement

---

**Développé pour la veille concurrentielle hôtelière à Saint-Rémy-de-Provence** 🏨
# scraper-booking
