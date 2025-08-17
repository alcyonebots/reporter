import asyncio
import logging
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from pymongo import MongoClient

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

API_ID = 29872536
API_HASH = "65e1f714a47c0879734553dc460e98d6"

MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "idsex"
COLLECTION_NAME = "sessions"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

def save_all_sessions_with_status(docs, filename="sessions_backup.txt"):
    try:
        with open(filename, "w") as f:
            for doc in docs:
                phone = doc.get("phone", "")
                session_str = doc.get("session_string", "")
                status = doc.get("status", "UNKNOWN")
                f.write(f"{phone}|||{session_str}|||{status}\n")
        logger.info(f"Saved {len(docs)} sessions with status to {filename}.")
    except Exception as e:
        logger.error(f"Error saving sessions to file: {str(e)}")

async def connect_existing_sessions(required_count):
    checked_sessions = []
    clients = []
    phones = []

    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]
        session_data["status"] = "FAILED"  # Default status
        for retry in range(5):
            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH,
                )
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"Connected to existing session for phone: {phone} successfully.")
                    session_data["status"] = "SUCCESS"
                    checked_sessions.append(session_data)
                    clients.append(client)
                    phones.append(phone)
                    break
                else:
                    logger.warning(f"Session for {phone} not authorized. Removing from DB.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(f"Connection issue for session {phone}. Retry {retry + 1}/5.")
                if retry == 4:
                    logger.error(f"Failed to connect to session for {phone} after retries.")
                    checked_sessions.append(session_data)
        else:
            # No successful connect in 5 retries
            checked_sessions.append(session_data)

    save_all_sessions_with_status(checked_sessions)
    return clients, phones

async def login(phone):
    try:
        client = TelegramClient(
            f'session_{phone}',
            API_ID,
            API_HASH,
        )
        await client.connect()
        if not await client.is_user_authorized():
            logger.info(f"Account {phone} not authorized. Logging in...")
            await client.send_code_request(phone)
            otp = input(f"Enter the OTP for {phone}: ")
            await client.sign_in(phone, otp)
            if not await client.is_user_authorized():
                password = input(f"Enter the 2FA password for {phone}: ")
                await client.sign_in(password=password)
            session_string = StringSession.save(client.session)
            sessions_collection.update_one(
                {"phone": phone},
                {"$set": {"session_string": session_string}},
                upsert=True,
            )
            logger.info(f"Session saved for account {phone}.")
        else:
            logger.info(f"Account {phone} is already authorized.")
        return client, phone
    except Exception as e:
        logger.error(f"Error during login for {phone}: {str(e)}")
        return None, None

async def assign_new_sessions(accounts_needed):
    new_sessions = []
    new_phones = []
    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        client, p = await login(phone)
        if client:
            logger.info(f"[✓] Logged in to new account {phone}.")
            new_sessions.append(client)
            new_phones.append(p)
    return new_sessions, new_phones

async def monitor_otps(clients, phones):
    print("Monitoring all sessions for OTPs (5/6 digit codes)... Press Ctrl+C to stop.")
    for idx, client in enumerate(clients):
        phone = phones[idx]
        @client.on(events.NewMessage(incoming=True))
        async def handler(event, phone=phone):
            match = re.search(r'\b\d{5,6}\b', event.raw_text)
            if match:
                print(f"[{phone}] OTP received: {match.group()}")
    await asyncio.gather(*[client.run_until_disconnected() for client in clients])

async def main():
    print("\n=== Telegram Multi-Account Manager without MTProto Proxy ===\n")
    account_count = int(input("Enter the number of accounts to use: "))

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"[✓] {account_count} sessions available.")
        clients, phones = await connect_existing_sessions(account_count)
    else:
        print(f"[✓] {existing_count} existing sessions found.")
        new_needed = account_count - existing_count
        print(f"[!] Logging in to {new_needed} new accounts.")
        existing_clients, existing_phones = await connect_existing_sessions(existing_count)
        new_clients, new_phones = await assign_new_sessions(new_needed)
        clients = existing_clients + new_clients
        phones = existing_phones + new_phones

    await monitor_otps(clients, phones)

if __name__ == "__main__":
    asyncio.run(main())
