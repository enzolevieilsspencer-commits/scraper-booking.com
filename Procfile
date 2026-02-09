# Procfile pour Railway
# API au premier plan (écoute PORT, reçoit le trafic HTTP) + Scheduler en arrière-plan
web: python src/scheduler/cron_jobs.py & python src/api/server.py
