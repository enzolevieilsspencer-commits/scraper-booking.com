# 📁 Structure du Projet Booking Scraper

## 🎯 Vue d'ensemble

Projet Python complet pour scraper Booking.com avec 2 scrapers distincts :
- **Scraper 1** : Infos hôtel (manuel, via API)
- **Scraper 2** : Prix 30 jours (automatique, 2x/jour)

## 📂 Structure des fichiers

```
booking-scraper-project/
│
├── 📄 README.md                    # Documentation principale
├── 📄 QUICKSTART.md                # Guide démarrage rapide
├── 📄 DEPLOYMENT.md                # Guide déploiement Railway
├── 📄 NEXTJS_INTEGRATION.md        # Intégration avec Next.js
│
├── ⚙️ Configuration
│   ├── .env                        # Variables d'environnement (avec vos clés)
│   ├── .env.example                # Template des variables
│   ├── .gitignore                  # Fichiers à ignorer
│   ├── requirements.txt            # Dépendances Python
│   ├── Procfile                    # Configuration Railway
│   └── railway.json                # Config Railway
│
├── 📦 src/                         # Code source
│   ├── __init__.py
│   │
│   ├── 🔧 config.py                # Configuration centrale
│   │
│   ├── 💾 database/                # Gestion base de données
│   │   ├── __init__.py
│   │   └── supabase_client.py     # Client Supabase
│   │
│   ├── 🕷️ scrapers/                # Scrapers
│   │   ├── __init__.py
│   │   ├── stealth_config.py      # Config Playwright anti-détection
│   │   ├── hotel_info_scraper.py  # Scraper 1: Infos hôtel
│   │   └── price_scraper.py       # Scraper 2: Prix 30 jours
│   │
│   ├── 🌐 api/                     # API FastAPI
│   │   └── server.py              # Serveur API pour Scraper 1
│   │
│   └── ⏰ scheduler/                # Automatisation
│       ├── run_price_scraper.py   # Exécution scraping prix
│       └── cron_jobs.py           # Scheduler avec horaires aléatoires
│
└── 🧪 test_setup.py                # Script de tests

```

## 📊 Fichiers créés (17 fichiers)

### Documentation (4 fichiers)
- ✅ README.md - Doc principale avec installation, usage, structure DB
- ✅ QUICKSTART.md - Guide démarrage rapide et tests locaux
- ✅ DEPLOYMENT.md - Guide déploiement Railway complet
- ✅ NEXTJS_INTEGRATION.md - Intégration avec frontend Next.js

### Configuration (6 fichiers)
- ✅ requirements.txt - Dépendances Python (Playwright, FastAPI, Supabase, etc.)
- ✅ .env - Variables d'environnement avec VOS clés Supabase
- ✅ .env.example - Template pour les variables
- ✅ .gitignore - Exclusions Git
- ✅ Procfile - Config Railway
- ✅ railway.json - Config build Railway

### Code Python (11 fichiers)
- ✅ src/__init__.py
- ✅ src/config.py - Configuration centrale, User-Agents, délais
- ✅ src/database/__init__.py
- ✅ src/database/supabase_client.py - Client Supabase (CRUD complet)
- ✅ src/scrapers/__init__.py
- ✅ src/scrapers/stealth_config.py - Playwright stealth mode
- ✅ src/scrapers/hotel_info_scraper.py - Scraper 1 (infos hôtel)
- ✅ src/scrapers/price_scraper.py - Scraper 2 (prix 30 jours)
- ✅ src/api/server.py - API FastAPI
- ✅ src/scheduler/run_price_scraper.py - Exécution scraping
- ✅ src/scheduler/cron_jobs.py - Scheduler automatique
- ✅ test_setup.py - Tests de validation

## 🎯 Fonctionnalités implémentées

### ✅ Scraper 1 - Infos Hôtel
- Extraction : nom, adresse, étoiles, photo
- Mode stealth (anti-détection)
- API FastAPI pour trigger manuel
- Enregistrement dans Supabase

### ✅ Scraper 2 - Prix 30 jours
- Scraping des 30 prochaines nuits
- 2 sessions/jour (3 hôtels chacune)
- Horaires aléatoires (anti-détection)
- Gestion disponibilité (complet/dispo)
- Batch insert dans Supabase
- Logs détaillés

### ✅ Infrastructure
- Client Supabase complet (CRUD)
- Configuration centralisée
- Playwright en mode stealth
- User-Agent rotation
- Délais aléatoires
- Logs d'exécution
- Tests de validation
- Prêt pour Railway

## 🗄️ Tables Supabase requises

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

## 🚀 Commandes principales

### Tests locaux
```bash
python test_setup.py                          # Tests de validation
python src/scrapers/hotel_info_scraper.py     # Test Scraper 1
python src/scrapers/price_scraper.py          # Test Scraper 2
python src/api/server.py                      # Lancer API
python src/scheduler/cron_jobs.py --run-now   # Test scheduler
```

### Production
```bash
python src/scheduler/cron_jobs.py             # Scheduler auto
python src/api/server.py                      # API uniquement
```

## 📦 Prochaines étapes

1. **Tester localement** → `python test_setup.py`
2. **Push sur GitHub** → Créer repo et push
3. **Déployer Railway** → Suivre DEPLOYMENT.md
4. **Intégrer Next.js** → Suivre NEXTJS_INTEGRATION.md

## 💡 Points clés

### Sécurité anti-détection ✅
- Playwright stealth mode
- User-Agent rotation (5 différents)
- Délais aléatoires 30-60s
- Horaires randomisés (8-11h et 14-17h)
- Sessions séparées (3+3 hôtels)

### Performance ✅
- Batch insert Supabase
- Gestion erreurs robuste
- Logs détaillés
- Retry automatique (Railway)

### Maintenabilité ✅
- Code bien structuré
- Configuration centralisée
- Documentation complète
- Tests inclus

## 🎉 C'est prêt !

Tout est configuré avec VOS clés Supabase. Il ne reste qu'à :
1. Tester localement
2. Push sur GitHub
3. Déployer sur Railway

Bon scraping ! 🚀
