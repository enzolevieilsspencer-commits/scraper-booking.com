#!/bin/bash
# Lance les deux scrapers : API (infos hôtel) + Scheduler (prix)
# Usage: ./run-all.sh   ou   bash run-all.sh

cd "$(dirname "$0")"

echo "📁 Dossier: $(pwd)"
echo ""

# Activation du venv
if [ -d "venv" ]; then
  echo "Activation du venv..."
  source venv/bin/activate
else
  echo "⚠️  venv non trouvé. Lance d'abord: ./setup-and-run.sh (une fois)"
  exit 1
fi

# Charger .env dans le shell (pour affichage correct)
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "[run-all] PORT=${PORT:-8000}"
echo "[run-all] SUPABASE_URL: $(test -n "$SUPABASE_URL" && echo 'défini' || echo 'MANQUANT')"
echo "[run-all] SUPABASE_SERVICE_KEY: $(test -n "$SUPABASE_SERVICE_KEY" && echo 'défini' || echo 'MANQUANT')"
echo ""

# Scraper 1 : API (infos hôtel) + Scraper 2 : Scheduler (prix automatique)
echo "[run-all] Lancement Scheduler prix (arrière-plan)..."
python src/scheduler/cron_jobs.py &

echo "[run-all] Lancement API sur http://localhost:${PORT:-8000}"
echo "Arrêt: Ctrl+C"
echo ""
exec python -u src/api/server.py 2>&1
