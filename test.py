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

MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "ids"
COLLECTION_NAME = "sessions"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

def save_all_sessions_with_status(docs, filename="sessions_backup.txt"):
    """
    Save all sessions with status in one file.
    Each line: phone ||| session_string ||| status (SUCCESS or FAILED)
    """
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

async def connect_existing_sessions(proxies, required_count):
    checked_sessions = []

    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]
        session_data["status"] = "FAILED"  # Default status
        for retry in range(1):
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
                    session_data["status"] = "SUCCESS"
                    checked_sessions.append(session_data)
                    break
                else:
                    logger.warning(f"Session for {phone} not authorized. Removing from DB.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(f"Proxy issue for session {phone}: {formatted_proxy}. Retry {retry + 1}/5.")
                if retry == 4:
                    logger.error(f"Failed to connect to session for {phone} after retries.")
                    checked_sessions.append(session_data)
        else:
            # No successful connect in 5 retries
            checked_sessions.append(session_data)

    # Save all checked sessions with status to file
    save_all_sessions_with_status(checked_sessions)

    # Return TelegramClient objects or session_data for further use if needed
    # Here, returning all successful session_data
    return [s for s in checked_sessions if s["status"] == "SUCCESS"]

def load_proxies(file_path="proxy.txt"):
    """Load MTProto proxies from a file."""
    try:
        with open(file_path, "r") as f:
            proxies = [
                tuple(line.strip().split(",")) for line in f.readlines() if line.strip()
            ]
        return proxies
    except FileNotFoundError:
        logger.error(f"Proxy file '{file_path}' not found.")
        return []

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
    print("\n=== Telegram Multi-Account Manager with Session Backup ===\n")
    account_count = int(input("Enter the number of accounts to use: "))
    proxies = load_proxies()

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

    # You can add your additional logic here (e.g., reporting, monitoring)

    # Disconnect all clients when done
    for client in clients:
        await client.disconnect()
    print("All clients disconnected. Done.")

if __name__ == "__main__":
    asyncio.run(main())
