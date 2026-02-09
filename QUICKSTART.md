# ⚡ Quick Start Guide

Guide de démarrage rapide pour tester le scraper localement avant de déployer.

## 📦 Installation (5 minutes)

### 1. Cloner et installer

```bash
cd booking-scraper-project

# Créer environnement virtuel
python -m venv venv

# Activer l'environnement
source venv/bin/activate  # Mac/Linux
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Installer Playwright
playwright install chromium
```

### 2. Configuration

Le fichier `.env` est déjà configuré avec vos clés Supabase.

Vérifier que tout est bon:
```bash
python test_setup.py
```

## 🧪 Tests locaux

### Test 1: Scraper d'infos hôtel

```bash
python src/scrapers/hotel_info_scraper.py
```

Vous verrez le navigateur s'ouvrir et scraper un hôtel de test.

### Test 2: Scraper de prix

```bash
python src/scrapers/price_scraper.py
```

Cela va scraper les 30 prochains jours pour un hôtel test.

### Test 3: API (Scraper 1)

Terminal 1:
```bash
python src/api/server.py
```

Terminal 2:
```bash
curl -X POST http://localhost:8000/scrape-hotel \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.booking.com/hotel/fr/chateau-de-roussan.fr.html"}'
```

### Test 4: Scheduler automatique

```bash
# Exécuter immédiatement (sans attendre les horaires)
python src/scheduler/cron_jobs.py --run-now

# Ou juste la session 1
python src/scheduler/cron_jobs.py --session 1
```

### Test 5: Run complet du scraper de prix

```bash
# Mode test (1 seul hôtel)
python src/scheduler/run_price_scraper.py --test

# Session 1 (3 premiers hôtels)
python src/scheduler/run_price_scraper.py --session 1

# Tous les hôtels
python src/scheduler/run_price_scraper.py
```

## 🎯 Utilisation Production

### Option A: Scheduler automatique (recommandé)

Lance le scheduler qui va scraper automatiquement 2x/jour:

```bash
python src/scheduler/cron_jobs.py
```

Laisser tourner en arrière-plan. Le scheduler va:
- Session 1: Entre 8h-11h (3 hôtels)
- Session 2: Entre 14h-17h (3 autres hôtels)
- Horaires randomisés chaque jour

### Option B: API pour ajouter des concurrents

Lance le serveur API:

```bash
python src/api/server.py
```

Endpoints disponibles:
- `GET /` - Info API
- `GET /health` - Health check
- `POST /scrape-hotel` - Ajouter un hôtel
- `POST /test-scrape` - Tester sans enregistrer

## 📊 Vérifier les résultats

### Dans Supabase

1. Aller sur https://supabase.com
2. Votre projet → Table Editor
3. Regarder les tables:
   - `hotels` - Les hôtels ajoutés
   - `rate_snapshots` - Les prix scrapés
   - `scraper_logs` - Les logs d'exécution

### Requêtes SQL utiles

```sql
-- Voir tous les hôtels actifs
SELECT * FROM hotels WHERE "isMonitored" = true;

-- Voir les derniers prix scrapés
SELECT h.name, rs."dateCheckin", rs.price, rs.available
FROM rate_snapshots rs
JOIN hotels h ON h.id = rs."hotelId"
ORDER BY rs."scrapedAt" DESC
LIMIT 100;

-- Voir les logs des dernières exécutions
SELECT * FROM scraper_logs
ORDER BY "startedAt" DESC
LIMIT 10;
```

## 🚀 Prêt pour le déploiement ?

1. ✅ Tests locaux OK
2. ✅ Données bien enregistrées dans Supabase
3. ✅ Aucune erreur dans les logs

→ Suivre [DEPLOYMENT.md](./DEPLOYMENT.md) pour déployer sur Railway

## 🆘 Problèmes courants

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "playwright executable doesn't exist"
```bash
playwright install chromium
```

### "Connection refused" (Supabase)
Vérifier les clés dans `.env`

### Le scraper ne trouve pas les prix
- Booking.com change parfois sa structure HTML
- Vérifier les sélecteurs dans `price_scraper.py`
- Augmenter les timeouts

### Trop de requêtes bloquées
Augmenter les délais dans `.env`:
```
MIN_DELAY_SECONDS=60
MAX_DELAY_SECONDS=120
```

## 📚 Prochaines étapes

1. **Local OK ?** → Déployer sur Railway ([DEPLOYMENT.md](./DEPLOYMENT.md))
2. **Besoin d'intégrer avec Next.js ?** → Voir [NEXTJS_INTEGRATION.md](./NEXTJS_INTEGRATION.md)
3. **Personnaliser ?** → Modifier les fichiers dans `src/`

## 💡 Conseils

- **Headless mode**: Mettre `HEADLESS_MODE=true` en production
- **Logs**: Toujours vérifier `scraper_logs` après exécution
- **Monitoring**: Configurer des alertes Railway pour les échecs
- **Backup**: Exporter régulièrement la base Supabase

Bon scraping ! 🎉
