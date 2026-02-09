#!/bin/sh
set -e
echo "[start] Démarrage..."
echo "[start] PORT=${PORT:-non défini}"
echo "[start] SUPABASE_URL: $(test -n "$SUPABASE_URL" && echo 'défini' || echo 'MANQUANT')"
echo "[start] SUPABASE_SERVICE_KEY: $(test -n "$SUPABASE_SERVICE_KEY" && echo 'défini' || echo 'MANQUANT')"
# Lancer l'API en premier plan pour voir ses logs / crash ; scheduler en arrière-plan
echo "[start] Lancement Scheduler (background)..."
python src/scheduler/cron_jobs.py &
echo "[start] Lancement API (foreground)..."
exec python -u src/api/server.py 2>&1
