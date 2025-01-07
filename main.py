import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from pymongo import MongoClient

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "reporter"
COLLECTION_NAME = "sessions"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]


def load_proxies(file_path="proxy.txt"):
    """Load proxies from a file."""
    try:
        with open(file_path, "r") as f:
            proxies = [
                tuple(line.strip().split(",")) for line in f.readlines() if line.strip()
            ]
        return proxies
    except FileNotFoundError:
        logger.error(f"Proxy file '{file_path}' not found.")
        return []


async def connect_with_retry(client, max_attempts=2):
    """Try to connect to Telegram with retries."""
    for attempt in range(1, max_attempts + 1):
        try:
            await client.connect()
            if await client.is_user_authorized():
                return True
            else:
                logger.warning("[!] Session is not authorized.")
                return False
        except OSError as e:  # Handle proxy connection errors
            logger.warning(f"[!] Attempt {attempt} failed: {str(e)}")
    return False


async def login_with_proxy(phone, proxies, max_attempts_per_proxy=2):
    """Attempt to log in using proxies, switching proxies if one fails."""
    for proxy in proxies:
        try:
            formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2]))
            client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=formatted_proxy)

            if await connect_with_retry(client, max_attempts_per_proxy):
                logger.info(f"Successfully logged in for {phone} using proxy: {formatted_proxy}")
                return client
            else:
                logger.warning(f"Failed to connect for {phone} using proxy: {formatted_proxy}")

        except Exception as e:
            logger.error(f"Error with proxy {proxy}: {str(e)}")

    logger.error(f"All proxies failed for {phone}. Skipping account.")
    return None


async def login_existing_sessions(proxies):
    """Log in with existing sessions from the database."""
    clients = []
    sessions = list(sessions_collection.find({}))
    for session in sessions:
        try:
            phone = session["phone"]
            session_string = session["session_string"]
            formatted_proxy = random.choice(proxies)
            proxy = (formatted_proxy[0].upper(), formatted_proxy[1], int(formatted_proxy[2]))

            client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=proxy)

            if await connect_with_retry(client):
                logger.info(f"Connected to session for phone: {phone}")
                clients.append(client)
            else:
                logger.warning(f"Session for phone {phone} is invalid. Removing from database.")
                sessions_collection.delete_one({"phone": phone})

        except Exception as e:
            logger.error(f"Error with session for phone {session['phone']}: {str(e)}")

    return clients


async def login_new_accounts(new_accounts, proxies):
    """Log in with new accounts provided by the user."""
    clients = []
    for phone in new_accounts:
        client = await login_with_proxy(phone, proxies)
        if client:
            session_string = StringSession.save(client.session)
            sessions_collection.update_one(
                {"phone": phone},
                {"$set": {"phone": phone, "session_string": session_string}},
                upsert=True,
            )
            logger.info(f"Session saved for account {phone}.")
            clients.append(client)
    return clients


async def report_entity(client, entity, reason, message, times_to_report):
    """Report an entity."""
    success_count = 0
    try:
        entity_peer = await client.get_input_entity(entity)
        for _ in range(times_to_report):
            await client(ReportPeerRequest(entity_peer, reason, message))
            success_count += 1
            logger.info(f"Successfully reported {entity}.")
    except Exception as e:
        logger.error(f"Failed to report {entity}: {str(e)}")
    return success_count


async def main():
    proxies = load_proxies()
    if not proxies:
        logger.error("No proxies available. Exiting.")
        return

    account_count = int(input("Enter the number of accounts to use: "))

    # Log in with existing sessions
    existing_clients = await login_existing_sessions(proxies)
    logger.info(f"Logged in with {len(existing_clients)} existing sessions.")

    # Determine how many new accounts to log in
    if len(existing_clients) < account_count:
        new_account_count = account_count - len(existing_clients)
        logger.info(f"Need to log in to {new_account_count} new accounts.")
        new_accounts = [
            input(f"Enter phone number for new account {i + 1} (e.g., +123456789): ")
            for i in range(new_account_count)
        ]
        new_clients = await login_new_accounts(new_accounts, proxies)
        existing_clients.extend(new_clients)

    # Proceed with reporting
    entity = input("Enter the group/channel username or user ID to report: ").strip()
    reason = InputReportReasonSpam()  # Example reason
    message = "Spam content."
    times_to_report = int(input("Enter the number of times to report: "))

    total_reports = 0
    for client in existing_clients:
        reports = await report_entity(client, entity, reason, message, times_to_report)
        total_reports += reports

    logger.info(f"Total successful reports submitted: {total_reports}")

    # Disconnect clients
    for client in existing_clients:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
            
