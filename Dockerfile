# Image Python sur Debian (bookworm = apt pour install-deps)
FROM python:3.9-bookworm

WORKDIR /app

# Dépendances Python + Playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + dépendances système en une commande (évite "missing dependencies")
RUN playwright install chromium --with-deps

COPY . .
RUN chmod +x start.sh

# Pour voir les logs immédiatement
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Scheduler en arrière-plan + API au premier plan (start.sh)
CMD ["./start.sh"]
