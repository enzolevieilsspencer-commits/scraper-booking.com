# Connexion Back (Railway) ↔ Front (Next.js / Vercel)

Ce document décrit comment le **scraper Railway** (back) et l’**app Next.js** (front) sont connectés via **Supabase**.

---

## Architecture globale

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONT (Next.js – Vercel)                                        │
│  • Pages : /, /app, /app/competitors, /app/history, /app/logs…  │
│  • API routes : /api/dashboard/*, /api/competitors, /api/…       │
│  • Lit Supabase (Prisma + client Supabase Auth)                  │
│  • Peut écrire : hotels (ajout/suppression concurrents)          │
└──────────────────────────────┬──────────────────────────────────┘
                                │
                                │  même projet Supabase
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  SUPABASE (PostgreSQL + Auth)                                    │
│  • Tables : hotels, rate_snapshots, scraper_logs                 │
│  • Auth : auth.users (login/signup du front)                     │
└──────────────────────────────┬──────────────────────────────────┘
                                │
                                │  écriture (scraping)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  BACK (Scraper – Railway)                                        │
│  • Scheduler : cron_jobs.py (2 sessions/jour)                   │
│  • API optionnelle : server.py (POST /extract, POST /scan…)      │
│  • Écrit dans : hotels, rate_snapshots, scraper_logs             │
└─────────────────────────────────────────────────────────────────┘
```

- **Une seule base** : même projet Supabase pour le front et le back.
- **Back** : écrit dans les 3 tables (scraping, logs).
- **Front** : lit les 3 tables (dashboard, historique, logs) et écrit dans `hotels` pour ajouter/supprimer des concurrents.

---

## Les 3 tables partagées

| Table              | Rôle back (Railway)                               | Rôle front (Next.js)                                           |
| ------------------ | ------------------------------------------------- | -------------------------------------------------------------- |
| **hotels**         | Crée/met à jour les lignes (scraper infos + prix) | Lit la liste, **écrit** pour ajouter/supprimer des concurrents |
| **rate_snapshots** | Insère les prix scrapés                           | Lit pour dashboard, historique, carte par date                 |
| **scraper_logs**   | Insère les logs d’exécution                       | Lit pour la page « Logs scraper »                              |

Schéma SQL : voir `supabase/supabase_tables.sql` (et côté scraper : QUICKSTART.md / README copy.md).

---

## Variables d’environnement

### Côté Vercel (Next.js)

À définir dans **Settings → Environment Variables** :

| Variable                        | Usage                                                                                                                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_SUPABASE_URL`      | Auth + client Supabase (ex. `https://xxx.supabase.co`)                                                                                                                                |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé anon Supabase                                                                                                                                                                     |
| `DATABASE_URL`                  | Connexion Postgres pour Prisma (URL **pooler** Supabase, sans guillemets). Ex. `postgresql://postgres.REF:MDP@...pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=1` |
| `SCRAPER_API_URL`               | (Optionnel) URL du service Railway pour l’extraction d’infos. Ex. `https://service-principal-production.up.railway.app` (sans `/extract`)                                             |

Important : sur Vercel, coller `DATABASE_URL` **sans guillemets**.

### Côté Railway (scraper)

D’après **DEPLOYMENT.md** et **README copy.md** :

| Variable                                                     | Usage                                                                   |
| ------------------------------------------------------------ | ----------------------------------------------------------------------- |
| `SUPABASE_URL`                                               | Même URL que `NEXT_PUBLIC_SUPABASE_URL` (ex. `https://xxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY`                                       | Clé **service_role** Supabase (écriture en base)                        |
| `ENVIRONMENT`                                                | Ex. `production`                                                        |
| `MIN_DELAY_SECONDS` / `MAX_DELAY_SECONDS`                    | Délais entre requêtes scraping                                          |
| `HEADLESS_MODE`                                              | Ex. `true`                                                              |
| `SESSION_1_START_HOUR` / `SESSION_1_END_HOUR` (et session 2) | Créneaux du scheduler                                                   |

Le scraper doit pointer vers **le même projet Supabase** que le front.

---

## Contrat API entre Front et Back (optionnel)

Pour que le front « parle » au back au-delà de la base :

### 1. Extraction d’infos (ajout de concurrent)

- **Front** : `POST /api/competitors/extract-info` avec `{ "url": "https://www.booking.com/..." }`.
- **Next.js** appelle le back si `SCRAPER_API_URL` est défini :
  - **Back** : exposer **`POST {SCRAPER_API_URL}/extract`** avec body `{ "url": "..." }`, réponse `{ "name", "location", "stars", "photoUrl" }`.
- Détails : `app/api/README.md` (section « Extraction d’infos »).

### 2. Déclencher un run manuel (optionnel)

- **Back** : exposer par ex. **`POST /scan`** (ou `/run`) protégé par un secret.
- **Front** : bouton « Lancer un scan » peut appeler cette URL (avec le secret en header) au lieu d’une route Next.js qui fait le scraping.

---

## Fichiers utiles dans ce repo (tarifscope)

| Fichier                          | Contenu                                                             |
| -------------------------------- | ------------------------------------------------------------------- |
| **INTEGRATION.md** (ce fichier)  | Vue d’ensemble connexion Back ↔ Front                               |
| **app/api/README.md**            | Routes API Next.js, contrat `/extract`, variables `SCRAPER_API_URL` |
| **supabase/supabase_tables.sql** | Création des tables `hotels`, `rate_snapshots`, `scraper_logs`      |
| **DEPLOYMENT.md**                | Déploiement du **scraper** sur Railway (back)                       |
| **QUICKSTART.md**                | Tests locaux du **scraper** (back)                                  |
| **README copy.md**               | Description du projet scraper (back), tables, env                   |

---

## Checklist « tout est bien connecté »

- [ ] Supabase : les 3 tables existent (`hotels`, `rate_snapshots`, `scraper_logs`).
- [ ] Vercel : `DATABASE_URL` (sans guillemets), `NEXT_PUBLIC_SUPABASE_*`, et si besoin `SCRAPER_API_URL`.
- [ ] Railway : `SUPABASE_URL` et `SUPABASE_SERVICE_KEY` du **même** projet Supabase.
- [ ] Back : scheduler ou cron qui écrit bien dans les 3 tables (voir logs Railway + `scraper_logs`).
- [ ] Front : dashboard / historique / logs scraper s’affichent (données lues depuis Supabase).
- [ ] (Optionnel) Back expose `POST /extract` → front peut pré-remplir les infos à l’ajout d’un concurrent.
