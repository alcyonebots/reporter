import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    ReportReasonSpam,
    ReportReasonViolence,
    ReportReasonPornography,
    ReportReasonChildAbuse,
    ReportReasonCopyright,
    ReportReasonScam,
    ReportReasonOther,
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
    "spam": ReportReasonSpam(),
    "violence": ReportReasonViolence(),
    "pornography": ReportReasonPornography(),
    "child abuse": ReportReasonChildAbuse(),
    "copyright infringement": ReportReasonCopyright(),
    "scam": ReportReasonScam(),
    "other": ReportReasonOther(),
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
    """Retrieve and connect to sessions in the database with proxy rotation."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]

        for retry in range(2):  # Retry twice per proxy
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]
            formatted_proxy = {
                'proxy_type': proxy[0].lower(),
                'addr': proxy[1],
                'port': int(proxy[2]),
            } if proxy else None

            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH,
                    connection_proxy=formatted_proxy,
                )
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"Connected to existing session for phone: {phone} using proxy: {formatted_proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session for {phone} is not authorized. Removing it from the database.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except (OSError, ConnectionError) as e:
                logger.warning(f"Proxy issue for session {phone}: {formatted_proxy}. Retrying... ({retry + 1}/2)")
            except Exception as e:
                logger.error(f"Failed to connect to session for phone: {phone}. Error: {str(e)}")
                break
    return existing_sessions

async def login(phone, proxy=None):
    """Login function with improved logging and error handling."""
    try:
        client = TelegramClient(f'session_{phone}', API_ID, API_HASH, connection_proxy=proxy)
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

async def report_entity(client, entity, reason, times_to_report):
    """Report an entity with improved error handling and logging."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        entity_peer = await client.get_entity(entity)
        default_messages = {
            "spam": "This is spam.",
            "violence": "This content promotes violence.",
            "pornography": "This content contains pornography.",
            "child abuse": "This content is related to child abuse.",
            "copyright infringement": "This content infringes on copyright.",
            "scam": "This account is impersonating Pavel Durov and attempting to scam users. They are misleading people by pretending to be the founder of Telegram. Please review and take necessary action to label this account as a scam.",
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
    # Main entry point remains unchanged
    pass  # Update similarly as needed

if __name__ == "__main__":
    asyncio.run(main())
