from fastapi import FastAPI, Depends, Request
import os
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from celery_worker import process_memory
from database import get_db
from models import Memory
from models import User
from security import MemoryVault
import redis
import requests
from database import engine, Base
import models

load_dotenv()
MASTER_KEY = os.getenv("AES_MASTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
vault = MemoryVault(MASTER_KEY)

Base.metadata.create_all(bind=engine)
app = FastAPI()

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses = True)

def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json = {"chat_id" : chat_id, "text" : text})

@app.post("/webhook")
async def receive_webhook(request : Request, db: Session = Depends(get_db)):
    payload = await request.json()
    try:
        chat_id = payload["message"]["chat"]["id"]
        user_text = payload["message"]["text"].strip()
    except KeyError:
        return {"status" : "ignored"}
    
    user_account = db.query(User).filter(User.telegram_id == chat_id).first()
    if not user_account:
        new_user = User(telegram_id = chat_id)
        db.add(new_user)
        db.commit()
        if user_text == "/start":
            send_reply(chat_id, f"Welcome! Your ID is {chat_id}. Send this ID to your partner so they can connect with you using /connect {chat_id}")
            return {"status" : "ok"}
        
    if user_text.startswith("/connect "):
        try:
            partner_id = int(user_text.split(" ")[1])
            user_account.partner_id = partner_id
            partner_account = db.query(User).filter(User.telegram_id == partner_id).first()
            if not partner_account:
                partner_account = User(telegram_id=partner_id, partner_id=chat_id)
                db.add(partner_account)
            else:
                partner_account.partner_id = chat_id
            db.commit()
            send_reply(chat_id, f"Success! You are now securely paired with {partner_id}.")
            send_reply(partner_id, f"Your partner (ID: {chat_id}) just connected to your vault!")
        except Exception:
            send_reply(chat_id, "Invalid command. Use format: /connect 12345")
        return {"status" : "ok"}

    state_key = f"state:{chat_id}"
    temp_type_key = f"temp_type:{chat_id}"

    current_state = redis_client.get(state_key)

    if not current_state:
        redis_client.set(state_key, "AWAITING_TYPE")
        send_reply(chat_id, "Was this a Good or Bad memory?")
        return {"status": "ok"}
    
    elif current_state == "AWAITING_TYPE":
        if user_text.lower() not in ["good", "bad"]:
            send_reply(chat_id, "Please just reply with exactly 'Good' or 'Bad'.")
            return {"status": "ok"}
        redis_client.set(state_key, "AWAITING_TEXT")
        redis_client.set(temp_type_key, user_text.capitalize())
        send_reply(chat_id, f"Got it. It was a {user_text} memory. Tell me what happened!")
        return {"status": "ok"}
    
    elif current_state == "AWAITING_TEXT":
        memory_type = redis_client.get(temp_type_key)
        payload["memory_type"] = memory_type
        process_memory.delay(payload)
        redis_client.delete(state_key)
        redis_client.delete(temp_type_key)
        return {"status": "ok"}

    return {"status" : "ok"}

@app.get("/memories/{user_id}")
def get_user_memories(user_id : int, db : Session = Depends(get_db)):
    memories = db.query(Memory).filter(Memory.user_id==user_id).all()
    if not memories:
        return {"message": "No memories found for this user."}
    
    decrypted_history = []
    for mem in memories:
        clean_text = vault.unlock(mem.encrypted_text)
        decrypted_history.append({
            "memory_id": mem.id,
            "saved_at": mem.created_at,
            "text": clean_text
        })
    
    return {
        "user_id": user_id,
        "total_memories": len(decrypted_history),
        "history": decrypted_history
    }