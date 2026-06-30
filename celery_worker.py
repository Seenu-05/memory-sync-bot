from celery import Celery
from celery.schedules import crontab
from celery.exceptions import MaxRetriesExceededError
import requests
import time
import os
from security import MemoryVault
from dotenv import load_dotenv
from database import engine, Base, SessionLocal
from models import Memory
from models import User
from models import DeadLetter

load_dotenv()

MASTER_KEY = os.getenv("AES_MASTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not MASTER_KEY or not BOT_TOKEN:
    raise ValueError("CRITICAL ERROR: Missing environment variables!")
vault = MemoryVault(MASTER_KEY)

Base.metadata.create_all(bind=engine)

celery_config = {
    'broker_url': os.getenv("REDIS_URL"),
    'broker_use_ssl': {'ssl_cert_reqs': None}, # This disables strict certificate checking for the cloud connection
}

app = Celery('memory_tasks')
app.conf.update(celery_config)

app.conf.broker_transport_options = {'protocol': 2}

app.conf.beat_schedule = {
    'execute-weekend-cleanup': {
        'task' : 'celery_worker.weekend_cleanup',
        'schedule' : crontab(hour=9, minute=0, day_of_week=0),
    },
}

@app.task(bind = True, max_retries = 3)
def send_telegram_message(self, chat_id, text):
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(telegram_url, json = {"chat_id":chat_id, "text":text, "parse_mode": "Markdown"}, timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as exc:
        print(f"[COURIER] Network Error: {exc}. Retrying...")
        try:
            countdown = 2**self.request.retries
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            print(f"[COURIER] Max retries hit! Routing to Dead Letter Queue...")
            db = SessionLocal()
            try:
                dlq_entry = DeadLetter(
                    chat_id=chat_id,
                    payload=text,
                    error_reason=str(exc)
                )
                db.add(dlq_entry)
                db.commit()
                print("[COURIER] Safely secured in the DLQ.")
            except Exception as db_err:
                db.rollback()
                print(f"[COURIER] CRITICAL: DB failed during DLQ save - {db_err}")
            finally:
                db.close()

@app.task
def weekend_cleanup():
    print("\n[BEAT] The Alarm Clock rang! Starting the Couples Exchange...")
    db = SessionLocal()

    try:
        paired_users = db.query(User).filter(User.partner_id.isnot(None)).all()
        processed_ids = set()

        for user in paired_users:
            if user.telegram_id in processed_ids:
                continue

            user_id = user.telegram_id
            partner_id = user.partner_id
            print(f"[BEAT] Swapping vaults for {user_id} and {partner_id}...")

            user_memories = db.query(Memory).filter(Memory.user_id==user_id).all()
            partner_memories = db.query(Memory).filter(Memory.user_id == partner_id).all()
            
            if user_memories:
                user_summary = "💌 *Your Partner's Week in Review*\n\n"
                for mem in user_memories:
                    clean = vault.unlock(mem.encrypted_text)
                    user_summary += f"• [{mem.memory_type}] {clean}\n"
                send_telegram_message.delay(partner_id, user_summary)
            if partner_memories:
                partner_summary = "💌 *Your Partner's Week in Review*\n\n"
                for mem in user_memories:
                    clean = vault.unlock(mem.encrypted_text)
                    partner_summary += f"• [{mem.memory_type}] {clean}\n"
                send_telegram_message.delay(partner_id, partner_summary)

            processed_ids.add(user_id)
            processed_ids.add(partner_id)
        
        print("[BEAT] Exchange complete. Incinerating the Bad memories...")
        deleted_count = db.query(Memory).filter(Memory.memory_type == 'Bad').delete()
        db.commit()
        print(f"[BEAT] Cleanup Complete! {deleted_count} bad memories erased across all users.")

    except Exception as e:
        db.rollback()
        print(f"[BEAT] DATABASE ERROR: {e}")
    finally:
        db.close()

    return True


@app.task
def process_memory(payload):

    try:
        raw_text = payload["message"]["text"]
        user_id = payload["message"]["chat"]["id"]
        memory_type = payload.get("memory_type", "Unknown")
    except KeyError:
        return False
    
    locked_data = vault.lock(raw_text)

    db = SessionLocal()

    try:
        new_memory = Memory(
            user_id = user_id,
            memory_type = memory_type,
            encrypted_text = locked_data
        )
        db.add(new_memory)
        db.commit()

        print(f"[WORKER] Calling Telegram Courier for User {user_id}...")
        telegram_url = f"https://api.telegram.org/{BOT_TOKEN}/sendMessage"

        success_msg = "✅ Your memory has been safely encrypted and locked in the vault!"
        send_telegram_message.delay(user_id, success_msg)
        print("[WORKER] Courier delivered the message successfully.")
        
    except Exception as e:
        db.rollback()
        print(f"[WORKER] DATABASE ERROR: {e}")
    
    finally:
        db.close()

    return True
