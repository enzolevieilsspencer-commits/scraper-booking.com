# 🚀 Guide de Déploiement sur Railway

## Prérequis

1. Compte GitHub
2. Compte Railway (gratuit sur [railway.app](https://railway.app))
3. Votre code poussé sur GitHub

## Étape 1: Préparer le Repository GitHub

```bash
# Dans le dossier booking-scraper-project/
git init
git add .
git commit -m "Initial commit: Booking scraper project"

# Créer un repo sur GitHub puis:
git remote add origin https://github.com/VOTRE_USERNAME/booking-scraper.git
git push -u origin main
```

## Étape 2: Déployer sur Railway

### 2.1 Créer le projet

1. Aller sur [railway.app](https://railway.app)
2. Se connecter avec GitHub
3. Cliquer sur **"New Project"**
4. Choisir **"Deploy from GitHub repo"**
5. Sélectionner votre repository `booking-scraper`

### 2.2 Configurer les variables d'environnement

Dans Railway → Votre projet → **Variables** :

```
SUPABASE_URL=https://drkfyyyeebvjdzdaiyxf.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
ENVIRONMENT=production
MIN_DELAY_SECONDS=30
MAX_DELAY_SECONDS=60
HEADLESS_MODE=true
SESSION_1_START_HOUR=8
SESSION_1_END_HOUR=11
SESSION_2_START_HOUR=14
SESSION_2_END_HOUR=17
```

⚠️ **Important**: Ne PAS mettre la clé Supabase dans le code, uniquement dans les variables Railway

### 2.3 Configuration du build

Railway devrait détecter automatiquement Python et utiliser `railway.json`.

Si besoin, vérifier dans **Settings** → **Build Command**:
```bash
pip install -r requirements.txt && playwright install chromium
```

**Start Command**:
```bash
python src/scheduler/cron_jobs.py
```

### 2.4 Déployer

Railway déploie automatiquement à chaque push sur GitHub.

Pour déclencher manuellement:
- Aller dans **Deployments**
- Cliquer sur **"Deploy"**

## Étape 3: Vérifier le déploiement

### Dans Railway

1. **Logs**: Aller dans l'onglet **Deployments** → Cliquer sur le déploiement → **View Logs**

Vous devriez voir:
```
✅ Configuration chargée - Environment: production
✅ Client Supabase initialisé
🤖 SCHEDULER AUTOMATIQUE DE SCRAPING
✅ Session 1 programmée aujourd'hui à 09:23
✅ Session 2 programmée aujourd'hui à 15:47
🚀 Scheduler démarré
```

2. **Health Check**: Le service doit être **"Running"** (vert)

### Dans Supabase

1. Aller dans **Table Editor** → `scraper_logs`
2. Vérifier que des logs sont créés lors des exécutions

## Étape 4: Déployer l'API (optionnel)

Si vous voulez aussi déployer l'API FastAPI pour le Scraper 1:

### Option A: Service séparé sur Railway

1. Créer un **nouveau projet** Railway
2. Même repo GitHub
3. Modifier le **Start Command** en:
   ```bash
   python src/api/server.py
   ```
4. Railway vous donnera une URL publique (ex: `https://booking-api.up.railway.app`)

### Option B: Dans le même service

Modifier `Procfile` pour lancer les 2:
```
web: python src/api/server.py &
worker: python src/scheduler/cron_jobs.py
```

## Architecture finale

```
┌─────────────────┐
│   Next.js       │  ← Vercel
│   (Frontend)    │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
┌────────▼────────┐   ┌────▼──────────┐
│   Supabase      │   │   Railway     │
│  (Database)     │◄──┤   (Scrapers)  │
└─────────────────┘   └───────────────┘
```

## Coûts

**Railway**:
- Gratuit: $5 de crédit/mois (suffisant pour 1-2 services)
- Hobby: $5/mois pour usage illimité
- Pro: $20/mois si besoin plus de ressources

**Estimation pour votre cas**:
- Scraping 2x/jour, ~2h total/jour
- Consommation: ~3-4$/mois
- ✅ Devrait tenir dans le plan gratuit

## Monitoring

### Logs en temps réel

```bash
# Installer Railway CLI
npm install -g @railway/cli

# Se connecter
railway login

# Voir les logs
railway logs
```

### Alertes

Dans Railway → **Settings** → **Notifications**:
- Activer les alertes par email en cas d'échec

## Troubleshooting

### Le service crash au démarrage

1. Vérifier les logs Railway
2. Vérifier que Playwright est bien installé:
   ```bash
   playwright install chromium
   ```

### "Module not found"

Vérifier que `requirements.txt` est à jour et installé:
```bash
pip install -r requirements.txt
```

### Timeout Supabase

Vérifier la clé `SUPABASE_SERVICE_KEY` dans les variables Railway.

### Scraper bloqué par Booking

Augmenter les délais dans les variables:
```
MIN_DELAY_SECONDS=60
MAX_DELAY_SECONDS=120
```

## Mise à jour du code

```bash
# Faire vos modifications
git add .
git commit -m "Update scraper logic"
git push

# Railway redéploie automatiquement
```

## Support

- Railway Docs: https://docs.railway.app
- Supabase Docs: https://supabase.com/docs
- En cas de problème: vérifier les logs Railway + table `scraper_logs` dans Supabase
