# 🧠 Memory Sync Vault

A highly secure, distributed Telegram bot architecture designed to act as an end-to-end encrypted vault for dual-user synchronization.

## 🏗 System Architecture (Hybrid Cloud)

This project implements a distributed microservice-inspired architecture, separating the web reception layer from the data processing layer to ensure zero downtime and asynchronous processing.

* **Frontend Interface:** Telegram Bot API
* **Cloud Receptionist (Web Layer):** FastAPI hosted on Render
* **Message Broker:** Upstash Redis (Secured via TLS/SSL)
* **Background Processing:** Celery Worker (Local/Hybrid environment)
* **Database:** PostgreSQL hosted on Supabase (Accessed via Supavisor Connection Pooler)

## 🚀 Key Engineering Implementations

1. **Asynchronous Task Queueing:** To prevent HTTP timeout errors from the Telegram API during heavy encryption tasks, the FastAPI server acts purely as a router. It packages incoming messages into Celery tasks and pushes them to the Upstash Redis queue. The background worker pulls and processes these tasks independently.
   
2. **IPv4 / IPv6 Connection Pooling:** Overcame Render's IPv4 network limitations when connecting to Supabase's IPv6 database by routing SQLAlchemy traffic through a port `6543` connection pooler, ensuring stable backend connectivity.

3. **Strict TLS/SSL Broker Security:** Configured secure `rediss://` encrypted handshakes between the local Celery worker and the Upstash Redis cluster to prevent plaintext network sniffing of queue data.

4. **Data Type Migration:** Upgraded standard SQLite integer fields to PostgreSQL `BigInteger` (64-bit) standards to safely store and process 10-digit Telegram user IDs without buffer overflows.

## ⚙️ Local Setup for Workers

If running the background worker locally while the FastAPI instance handles cloud webhooks:

1. Spin up the worker:
   `python -m celery -A celery_worker worker --pool=gevent --loglevel=info`
2. (Optional) Spin up the beat scheduler:
   `python -m celery -A celery_worker beat --loglevel=info`

## 📖 User Guide & Operational Flow

The vault is designed for a strict dual-user pairing system. Both nodes (users) must establish a secure handshake before cryptographic storage is permitted.

### Phase 1: Establishing the Secure Handshake (Pairing)
To link two accounts to the same cryptographic vault, both users must register with the database and cross-verify their IDs.

1. **Initialize Node:** Both User A and User B open the Telegram bot and send the `/start` command.
2. **Generate Identifiers:** The bot registers both users in the PostgreSQL database and returns their unique 10-digit Telegram IDs.
3. **Execute Handshake:** User A sends the command `/connect [User B's ID]`.
4. **Verification:** The system updates the relational database, linking both `partner_id` fields. The bot immediately dispatches a success notification to both users, confirming the vault is locked and linked.

### Phase 2: Daily Memory Synchronization
Once paired, the bot utilizes a Redis-backed state machine to guide users through standard memory capture. 

1. **Initiate Protocol:** Send any standard greeting (e.g., "Hi") to wake the bot and trigger the state machine.
2. **Categorization:** The bot will prompt: *"Was this a Good or Bad memory?"* Reply with exactly `Good` or `Bad`. This caches the state in Redis.
3. **Data Entry:** The bot will prompt for the actual memory. Type and send the full text of your memory.
4. **Encryption & Storage:** The FastAPI server receives the text, pushes it to the Celery task queue, and clears the Redis state. The background worker immediately processes the task, encrypts the string using AES-256, and writes the ciphertext permanently into the Supabase vault. 
5. **Confirmation:** The bot sends a ✅ success message, confirming the memory is secure and the state machine has reset.