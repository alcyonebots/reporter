import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonOther,
    InputPeerChat,
    InputPeerChannel,
    InputPeerUser,
)
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

# Reasons for reporting
REPORT_REASONS = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child abuse": InputReportReasonChildAbuse(),
    "copyright infringement": InputReportReasonCopyright(),
    "other": InputReportReasonOther(),
}

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

async def connect_existing_sessions(proxies, required_count):
    """Retrieve and connect to sessions already in the database using proxies."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]
        proxy = None if not proxies else proxies[i % len(proxies)]
        formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2])) if proxy else None

        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=formatted_proxy)
            await client.connect()
            if await client.is_user_authorized():
                logger.info(f"Connected to existing session for phone: {phone} using proxy: {formatted_proxy}")
                existing_sessions.append(client)
            else:
                logger.warning(f"Session for {phone} is not authorized.")
                await client.disconnect()
        except Exception as e:
            logger.error(f"Failed to connect to session for phone: {phone}. Error: {str(e)}")
    return existing_sessions

async def login(phone, proxy=None):
    try:
        client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=proxy)
        await client.connect()

        if not await client.is_user_authorized():
            logger.info(f"Account {phone} is not authorized. Logging in...")
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
            logger.info(f"Session saved for account {phone}.")
        else:
            logger.info(f"Account {phone} is already authorized.")

        return client

    except Exception as e:
        logger.error(f"An error occurred during login for account {phone}: {str(e)}")
        return None

async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    """Log in to new accounts using proxies."""
    new_sessions = []
    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        proxy = None if not proxies else proxies[i % len(proxies)]
        formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2])) if proxy else None

        client = await login(phone, proxy=formatted_proxy)
        if client:
            logger.info(f"Logged in to new account {phone} using proxy: {formatted_proxy}")
            new_sessions.append(client)
    return new_sessions

async def main():
    print("=== Telegram Multi-Account Reporting Tool ===")

    # Step 1: Ask for the number of accounts to use
    account_count = int(input("Enter the number of accounts to use for reporting: "))

    # Load proxies
    proxies = load_proxies()

    # Step 2: Retrieve existing sessions
    existing_sessions = await connect_existing_sessions(proxies, account_count)
    existing_count = len(existing_sessions)

    # Step 3: If more accounts are needed, prompt for new logins
    if existing_count >= account_count:
        print(f"There are {existing_count} existing sessions. No need to log in to new accounts.")
        clients = existing_sessions[:account_count]
    else:
        print(f"{existing_count} sessions found in the database. Logging into {account_count - existing_count} new accounts.")
        new_sessions = await assign_proxies_to_new_sessions(proxies, account_count - existing_count)
        clients = existing_sessions + new_sessions

    # Step 4: Select type of entity to report
    print("\nSelect the type of entity to report:")
    print("1 - Group")
    print("2 - Channel")
    print("3 - User")
    try:
        choice = int(input("Enter your choice (1/2/3): "))
        if choice not in [1, 2, 3]:
            print("Invalid choice. Exiting.")
            return
    except ValueError:
        print("Invalid input. Exiting.")
        return

    # Step 5: Get the entity and reason
    entity = input("Enter the group/channel username or user ID to report: ").strip()
    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    try:
        reason_choice = int(input("Enter your choice (1-{}): ".format(len(REPORT_REASONS))))
        reason_map = list(REPORT_REASONS.keys())
        if reason_choice < 1 or reason_choice > len(reason_map):
            print("Invalid reason choice. Exiting.")
            return
        reason = reason_map[reason_choice - 1]
    except ValueError:
        print("Invalid input. Exiting.")
        return

    # Step 6: Get the number of reports
    try:
        times_to_report = int(input("Enter the number of times to report: "))
        if times_to_report <= 0:
            print("Number of reports must be greater than 0. Exiting.")
            return
    except ValueError:
        print("Invalid input. Exiting.")
        return

    # Step 7: Report the entity from all accounts
    async def report_entity(client):
        entity_peer = await client.get_input_entity(entity)
        message = f"Reported for {reason.capitalize()}."
        for _ in range(times_to_report):
            await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message))
        logger.info(f"Successfully reported {entity} for {reason}.")

    for client in clients:
        await report_entity(client)

    # Step 8: Disconnect all clients
    for client in clients:
        await client.disconnect()
    print(f"Reports submitted {times_to_report} times. All clients disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
        
