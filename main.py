import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from pymongo import MongoClient
from telethon.errors import ProxyConnectionError

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
        except ProxyConnectionError as e:
            logger.warning(f"[!] Attempt {attempt} failed: {str(e)}")
    return False

async def connect_existing_sessions(proxies, required_count):
    """Retrieve and connect to sessions already in the database using proxies."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    proxy_index = 0

    for session_data in session_docs[:required_count]:
        phone = session_data["phone"]
        session_string = session_data["session_string"]
        success = False

        for _ in range(len(proxies)):  # Loop through proxies until success
            proxy = proxies[proxy_index % len(proxies)]
            formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2]))

            try:
                client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=formatted_proxy)
                logger.info(f"[*] Attempting to connect {phone} with proxy: {formatted_proxy}")

                if await connect_with_retry(client):
                    logger.info(f"[✓] Connected to existing session for phone: {phone} using proxy: {formatted_proxy}")
                    existing_sessions.append(client)
                    success = True
                    break
                else:
                    logger.warning(f"[!] Failed to authorize session for {phone}. Removing from database.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()

            except Exception as e:
                logger.error(f"[!] Failed to connect for phone: {phone} with proxy {formatted_proxy}. Error: {str(e)}")

            proxy_index += 1  # Move to the next proxy

        if not success:
            logger.error(f"[!] Could not connect session for {phone} after trying all proxies.")

    return existing_sessions

async def login(phone, proxy=None):
    """Login to a new Telegram account."""
    try:
        client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=proxy)
        await client.connect()

        if not await client.is_user_authorized():
            print(f"\n[!] Account {phone} is not authorized. Logging in...")
            await client.send_code_request(phone)
            otp = input(f"Enter the OTP for {phone}: ")
            await client.sign_in(phone, otp)

            # Handle 2FA if enabled
            if not await client.is_user_authorized():
                password = input(f"Enter the 2FA password for {phone}: ")
                await client.sign_in(password=password)

            # Save the session string to MongoDB
            session_string = StringSession.save(client.session)
            sessions_collection.update_one(
                {"phone": phone},
                {"$set": {"session_string": session_string}},
                upsert=True,
            )
            print(f"[✓] Session saved for account {phone}.")
        else:
            print(f"[✓] Account {phone} is already authorized.")

        return client

    except Exception as e:
        print(f"[!] Error during login for account {phone}: {str(e)}")
        return None

async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    """Log in to new accounts using proxies."""
    new_sessions = []
    proxy_index = 0

    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        success = False

        for _ in range(len(proxies)):  # Loop through proxies until success
            proxy = proxies[proxy_index % len(proxies)]
            formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2]))

            client = await login(phone, proxy=formatted_proxy)
            if client:
                print(f"[✓] Logged in to new account {phone} using proxy: {formatted_proxy}")
                new_sessions.append(client)
                success = True
                break

            proxy_index += 1  # Move to the next proxy

        if not success:
            print(f"[!] Could not log in to {phone} after trying all proxies.")

    return new_sessions

async def main():
    print("\n=== Telegram Multi-Account Reporting Tool ===")
    print("\nThis tool helps you report entities using multiple Telegram accounts.\n")

    account_count = int(input("Enter the number of accounts to use for reporting: "))
    proxies = load_proxies()

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"\n[✓] There are {account_count} existing sessions. No new accounts required.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        print(f"\n[✓] {existing_count} sessions found in the database.")
        new_accounts_needed = account_count - existing_count
        print(f"[!] Please log in to {new_accounts_needed} new accounts.")
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, new_accounts_needed)
        clients = existing_clients + new_clients

    print("\nReporting functionality can be implemented here.")
    # Additional reporting logic

    for client in clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
                                                                                                                  
