"""
Système de scheduling automatique avec horaires aléatoires
Exécute le scraping 2x/jour à des heures variables
"""
import schedule
import time
import random
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scheduler.run_price_scraper import run_price_scraping
from config import (
    SESSION_1_START_HOUR,
    SESSION_1_END_HOUR,
    SESSION_2_START_HOUR,
    SESSION_2_END_HOUR
)


def get_random_time_in_range(start_hour: int, end_hour: int) -> str:
    """
    Génère une heure aléatoire dans une plage
    
    Args:
        start_hour: Heure de début (ex: 8)
        end_hour: Heure de fin (ex: 11)
        
    Returns:
        String au format "HH:MM" (ex: "09:23")
    """
    hour = random.randint(start_hour, end_hour - 1)
    minute = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}"


def schedule_session_1():
    """Exécute la session 1 (3 premiers hôtels)"""
    print(f"\n⏰ DÉCLENCHEMENT SESSION 1 - {datetime.now().strftime('%H:%M:%S')}")
    run_price_scraping(session_number=1)
    
    # Programmer la prochaine session 1 pour demain
    next_time = get_random_time_in_range(SESSION_1_START_HOUR, SESSION_1_END_HOUR)
    schedule.clear('session1')
    schedule.every().day.at(next_time).do(schedule_session_1).tag('session1')
    print(f"✅ Session 1 terminée. Prochaine exécution: demain à {next_time}")


def schedule_session_2():
    """Exécute la session 2 (3 hôtels suivants)"""
    print(f"\n⏰ DÉCLENCHEMENT SESSION 2 - {datetime.now().strftime('%H:%M:%S')}")
    run_price_scraping(session_number=2)
    
    # Programmer la prochaine session 2 pour demain
    next_time = get_random_time_in_range(SESSION_2_START_HOUR, SESSION_2_END_HOUR)
    schedule.clear('session2')
    schedule.every().day.at(next_time).do(schedule_session_2).tag('session2')
    print(f"✅ Session 2 terminée. Prochaine exécution: demain à {next_time}")


def initialize_scheduler():
    """Initialise le scheduler avec des horaires aléatoires"""
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   🤖 SCHEDULER AUTOMATIQUE DE SCRAPING                    ║
║   Horaires aléatoires pour éviter la détection            ║
╚═══════════════════════════════════════════════════════════╝

📅 Configuration:
   • Session 1: Entre {SESSION_1_START_HOUR}h et {SESSION_1_END_HOUR}h (3 premiers hôtels)
   • Session 2: Entre {SESSION_2_START_HOUR}h et {SESSION_2_END_HOUR}h (3 hôtels suivants)
   • Horaires randomisés chaque jour
    """)
    
    # Générer horaires pour aujourd'hui
    session1_time = get_random_time_in_range(SESSION_1_START_HOUR, SESSION_1_END_HOUR)
    session2_time = get_random_time_in_range(SESSION_2_START_HOUR, SESSION_2_END_HOUR)
    
    # Vérifier si l'heure est déjà passée aujourd'hui
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    if current_time > session1_time:
        print(f"⚠️ Session 1 ({session1_time}) déjà passée aujourd'hui")
        print(f"   → Programmée pour demain")
    else:
        print(f"✅ Session 1 programmée aujourd'hui à {session1_time}")
    
    if current_time > session2_time:
        print(f"⚠️ Session 2 ({session2_time}) déjà passée aujourd'hui")
        print(f"   → Programmée pour demain")
    else:
        print(f"✅ Session 2 programmée aujourd'hui à {session2_time}")
    
    # Programmer les tâches
    schedule.every().day.at(session1_time).do(schedule_session_1).tag('session1')
    schedule.every().day.at(session2_time).do(schedule_session_2).tag('session2')
    
    print(f"\n🚀 Scheduler démarré - En attente des prochaines exécutions...")
    print(f"{'='*60}\n")


def run_scheduler():
    """Boucle principale du scheduler"""
    initialize_scheduler()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les minutes
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Scheduler arrêté par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur fatale du scheduler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scheduler automatique de scraping")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Exécuter immédiatement au lieu d'attendre"
    )
    parser.add_argument(
        "--session",
        type=int,
        choices=[1, 2],
        help="Exécuter une session spécifique immédiatement puis arrêter"
    )
    
    args = parser.parse_args()
    
    if args.session:
        # Mode one-shot: exécuter une session et arrêter
        print(f"🚀 Exécution immédiate de la session {args.session}")
        run_price_scraping(session_number=args.session)
        sys.exit(0)
    
    elif args.run_now:
        # Exécuter immédiatement les 2 sessions puis démarrer le scheduler
        print("🚀 Exécution immédiate des 2 sessions...")
        print("\n" + "="*60)
        print("SESSION 1")
        print("="*60)
        run_price_scraping(session_number=1)
        
        print("\n" + "="*60)
        print("SESSION 2")
        print("="*60)
        run_price_scraping(session_number=2)
        
        print("\n✅ Exécution immédiate terminée")
        print("🔄 Démarrage du scheduler pour les prochaines exécutions...")
        run_scheduler()
    
    else:
        # Mode normal: démarrer le scheduler
        run_scheduler()
