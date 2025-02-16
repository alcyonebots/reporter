import asyncio
import logging
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonFake,
    InputReportReasonOther,
)
from pymongo import MongoClient
from colorama import Fore, Style, init
from art import text2art

# Initialize Colorama
init(autoreset=True)

# ASCII Art Title
ascii_title = text2art("The Massacres", font="slant")  # You can change the font

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Telegram API credentials
API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "Report"
COLLECTION_NAME = "session"

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
    "scam": InputReportReasonFake(),
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
    """Retrieve and connect to existing Telegram sessions."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())

    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]

        for retry in range(5):  # Retry up to 5 times with different proxies
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]
            formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2])) if proxy else None

            try:
                client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=formatted_proxy)
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"Connected to session: {phone} using proxy: {formatted_proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session {phone} is unauthorized. Removing from database.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.error(f"Failed to connect to session {phone}: {str(e)}")
                break
    return existing_sessions

async def report_entity(client, entity, reason, times_to_report):
    """Report an entity multiple times."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        entity_peer = await client.get_input_entity(entity)
        default_messages = {
            "spam": "This is spam.",
            "violence": "This content promotes violence.",
            "pornography": "This content contains pornography.",
            "child abuse": "This content is related to child abuse.",
            "copyright infringement": "This content infringes on copyright.",
            "scam": "This account is impersonating someone and attempting to scam users.",
            "other": "This is an inappropriate entity.",
        }
        message = default_messages.get(reason, "This entity violates Telegram policies.")
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

async def report_message(client, message_link, reason):
    """Report a specific message using its link."""
    try:
        match = re.match(r"https://t.me/([^/]+)/(\d+)", message_link)
        if not match:
            logger.error("Invalid Telegram message link format.")
            return 0

        username, message_id = match.groups()
        entity_peer = await client.get_input_entity(username)
        message_id = int(message_id)

        message_reason = REPORT_REASONS.get(reason, InputReportReasonOther())
        result = await client(ReportRequest(peer=entity_peer, id=[message_id], reason=message_reason))
        
        if result:
            logger.info(f"[✓] Successfully reported message {message_id} in {username} for {reason}.")
            return 1
        else:
            logger.warning(f"[✗] Failed to report message {message_id} in {username}.")
            return 0

    except Exception as e:
        logger.error(f"Failed to report message {message_link}: {str(e)}")
        return 0

async def main():
    print(Fore.RED + ascii_title)
    print(Fore.YELLOW + "\n=== Telegram Multi-Account Reporting Tool ===\n")
    
    account_count = int(input("Enter the number of accounts to use for reporting: "))
    proxies = load_proxies()

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"\n[✓] {account_count} existing sessions found.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        print(f"\n[✓] {existing_count} sessions found in the database.")
        print(f"[!] Logging into {account_count - existing_count} new accounts is required.")
        clients = await connect_existing_sessions(proxies, existing_count)

    print("\nSelect the type of entity to report:")
    print("1 - Group/Channel/User")
    print("2 - Specific Message")
    choice = int(input("Enter your choice (1/2): "))

    if choice == 1:
        entity = input("Enter the group/channel username or user ID to report: ").strip()
    else:
        entity = input("Enter the Telegram message link: ").strip()

    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    reason_choice = int(input("Enter your choice: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    times_to_report = int(input("Enter the number of times to report: "))

    total_successful_reports = 0

    for client in clients:
        if choice == 1:
            total_successful_reports += await report_entity(client, entity, reason, times_to_report)
        else:
            total_successful_reports += await report_message(client, entity, reason)

    print(f"\n[✓] Total successful reports submitted: {total_successful_reports}")

    for client in clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
