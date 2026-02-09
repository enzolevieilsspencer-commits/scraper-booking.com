#!/bin/bash
# À lancer depuis booking-scraper-project (Mac)
# Usage: ./setup-and-run.sh   ou   bash setup-and-run.sh

cd "$(dirname "$0")"

echo "📁 Dossier: $(pwd)"
echo ""

# 1. Venv déjà créé normalement ; si besoin :
if [ ! -d "venv" ]; then
  echo "Création du venv avec python3..."
  python3 -m venv venv
fi

echo "Activation du venv..."
source venv/bin/activate

# 2. Dépendances Python (au cas où le venv serait vide)
if ! python -c "import fastapi" 2>/dev/null; then
  echo "Installation des dépendances (pip install -r requirements.txt)..."
  pip install -r requirements.txt
fi

# 3. Playwright Chromium (à faire une fois ; téléchargement ~150 Mo)
if ! python -c "from playwright.sync_api import sync_playwright; sync_playwright().start()" 2>/dev/null; then
  echo "Installation de Chromium pour Playwright (peut prendre 1–2 min)..."
  playwright install chromium
fi

# 4. Fichier .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Fichier .env créé depuis .env.example — pense à y mettre SUPABASE_URL et SUPABASE_SERVICE_KEY"
fi

echo ""
echo "Démarrage du serveur scraper sur http://localhost:8000"
echo "Arrêt: Ctrl+C"
echo ""
python src/api/server.py
