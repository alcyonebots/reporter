import asyncio
import logging
from telethon import TelegramClient, connection
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

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "idnunu"
COLLECTION_NAME = "sessions"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

def save_sessions_to_file(filename="sessions_backup.txt"):
    """Save all current session phone and session strings to a file."""
    try:
        docs = list(sessions_collection.find({}, {"phone": 1, "session_string": 1, "_id": 0}))
        with open(filename, "w") as f:
            for doc in docs:
                phone = doc.get("phone", "")
                session_str = doc.get("session_string", "")
                f.write(f"{phone}|||{session_str}\n")
        logger.info(f"Saved {len(docs)} sessions to {filename}.")
    except Exception as e:
        logger.error(f"Error saving sessions to file: {str(e)}")

async def connect_existing_sessions(proxies, required_count):
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]
        for retry in range(5):
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]
            formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])
            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH,
                    connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
                    proxy=formatted_proxy,
                )
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(
                        f"Connected to existing session for phone: {phone} using MTProto Proxy: {formatted_proxy}"
                    )
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session for {phone} not authorized. Removing.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(f"Proxy issue for session {phone}: {formatted_proxy}. Retrying... ({retry + 1}/5)")
    return existing_sessions

async def login(phone, proxy=None):
    try:
        formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])
        client = TelegramClient(
            f'session_{phone}',
            API_ID,
            API_HASH,
            connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=formatted_proxy,
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
            save_sessions_to_file()  # Save sessions file after each new login
        else:
            logger.info(f"Account {phone} is already authorized.")
        return client
    except Exception as e:
        logger.error(f"Error during login for {phone}: {str(e)}")
        return None

async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    new_sessions = []
    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        proxy = None if not proxies else proxies[i % len(proxies)]
        client = await login(phone, proxy=proxy)
        if client:
            logger.info(f"[✓] Logged in to new account {phone} using Proxy: {proxy}")
            new_sessions.append(client)
    return new_sessions

async def main():
    print("\n=== Telegram Multi-Account Reporter with Session Backup ===\n")
    account_count = int(input("Enter the number of accounts to use: "))
    proxies = []  # Load your proxies here if needed

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"[✓] {account_count} sessions available.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        print(f"[✓] {existing_count} existing sessions found.")
        new_needed = account_count - existing_count
        print(f"[!] Logging in to {new_needed} new accounts.")
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, new_needed)
        clients = existing_clients + new_clients

    # Save all sessions to file once at the end as well
    save_sessions_to_file()

    # Place your reporting or other logic here, or keep clients connected
    # For demonstration, just disconnect
    for client in clients:
        await client.disconnect()
    print("All clients disconnected. Done.")

if __name__ == "__main__":
    asyncio.run(main())
with client:
    client.loop.run_until_complete(report_message())
