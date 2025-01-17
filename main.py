import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types.mtproto import MTProtoProxy
from telethon.tl.types import (
    InputPeerUser,
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonOther,
)
from pymongo import MongoClient

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
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
    "scam": InputReportReasonOther(),
    "other": InputReportReasonOther(),
}

def load_proxies(file_path="proxy.txt"):
    """Load MTProto proxies from a file."""
    try:
        with open(file_path, "r") as f:
            proxies = []
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 4:  # MTProto proxy (type, host, port, secret)
                    proxies.append({"proxy_type": "MTProto", "addr": parts[1], "port": int(parts[2]), "secret": parts[3]})
            return proxies
    except FileNotFoundError:
        logger.error(f"Proxy file '{file_path}' not found.")
        return []

async def connect_existing_sessions(proxies, required_count):
    """Retrieve and connect to sessions in the database with MTProto proxy rotation."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]

        for retry in range(2):  # Retry twice per proxy
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]

            if proxy and proxy["proxy_type"] == "MTProto":
                # Construct MTProto proxy configuration
                mtproto_proxy = MTProtoProxy(
                    server=proxy["addr"], 
                    port=proxy["port"], 
                    secret=proxy["secret"]
                )
                proxy_config = mtproto_proxy
            else:
                proxy_config = None

            try:
                client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=proxy_config)
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"Connected to existing session for phone: {phone} using proxy: {proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session for {phone} is not authorized. Removing it from the database.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except (OSError, ConnectionError) as e:
                logger.warning(f"Proxy issue for session {phone}: {proxy}. Retrying... ({retry + 1}/2)")
            except Exception as e:
                logger.error(f"Failed to connect to session for phone: {phone}. Error: {str(e)}")
                break
    return existing_sessions

async def login(phone, proxy=None):
    """Login function with MTProto proxy support."""
    try:
        if proxy and proxy["proxy_type"] == "MTProto":
            # Construct MTProto proxy configuration
            mtproto_proxy = MTProtoProxy(
                server=proxy["addr"], 
                port=proxy["port"], 
                secret=proxy["secret"]
            )
            proxy_config = mtproto_proxy
        else:
            proxy_config = None

        client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=proxy_config)
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

    except (OSError, ConnectionError) as e:
        logger.error(f"Proxy issue during login for account {phone}. Error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error during login for account {phone}: {str(e)}")
        return None

async def login(phone, proxy=None):
    """Login function with MTProto proxy support."""
    try:
        if proxy and proxy["proxy_type"] == "MTProto":
            # Construct MTProto proxy configuration
            mtproto_proxy = MTProtoProxy(
                server=proxy["addr"], 
                port=proxy["port"], 
                secret=proxy["secret"]
            )
            proxy_config = mtproto_proxy
        else:
            proxy_config = None

        client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=proxy_config)
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

    except (OSError, ConnectionError) as e:
        logger.error(f"Proxy issue during login for account {phone}. Error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error during login for account {phone}: {str(e)}")
        return None

async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    """Log in to new accounts using MTProto proxies."""
    new_sessions = []
    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        proxy = None if not proxies else proxies[i % len(proxies)]

        client = await login(phone, proxy=proxy)
        if client:
            logger.info(f"[✓] Logged in to new account {phone} using proxy: {proxy}")
            new_sessions.append(client)
    return new_sessions

async def report_entity(client, entity, reason, times_to_report):
    """Report an entity with improved error handling and logging."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        # Determine if the input is a user ID or a username
        if entity.isdigit():
            entity_peer = InputPeerUser(user_id=int(entity), access_hash=0)  # Replace `0` with actual access hash if known
        else:
            entity_peer = await client.get_input_entity(entity)

        default_messages = {
            "spam": "This is spam.",
            "violence": "This content promotes violence.",
            "pornography": "This content contains pornography.",
            "child abuse": "This content is related to child abuse.",
            "copyright infringement": "This content infringes on copyright.",
            "scam": "This account is impersonating Pavel Durov and attempting to scam users.",
            "other": "This is an inappropriate entity.",
        }
        message = default_messages.get(reason, "This is a reported entity.")
        successful_reports = 0

        for _ in range(times_to_report):
            try:
                result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message))
                if result:
                    successful_reports += 1
                    logger.info(f"[✓] Reported {entity} for {reason}.")
                else:
                    logger.warning(f"[✗] Failed to report {entity}.")
            except Exception as e:
                logger.error(f"Error during report attempt for {entity}: {str(e)}")

        return successful_reports

    except Exception as e:
        logger.error(f"Failed to report {entity}: {str(e)}")
        return 0

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

    print("\nSelect the type of entity to report:")
    print("1 - Group")
    print("2 - Channel")
    print("3 - User")
    choice = int(input("Enter your choice (1/2/3): "))
    entity = input("Enter the group/channel username or user ID to report: ").strip()
    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    reason_choice = int(input("Enter your choice: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    times_to_report = int(input("Enter the number of times to report: "))
    total_successful_reports = 0

    for client in clients:
        successful_reports = await report_entity(client, entity, reason, times_to_report)
        total_successful_reports += successful_reports

    print(f"\n[✓] Total successful reports submitted: {total_successful_reports}")

    for client in clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
        
