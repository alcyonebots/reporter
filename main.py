import asyncio
import logging
import re
from telethon import TelegramClient, connection
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.account import ReportPeerRequest
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

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "report"
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
    "scam": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}


def load_proxies(file_path="proxy.txt"):
    """Load MTProto proxies from a file."""
    try:
        with open(file_path, "r") as f:
            proxies = [tuple(line.strip().split(",")) for line in f.readlines() if line.strip()]
        return proxies
    except FileNotFoundError:
        logger.error(f"Proxy file '{file_path}' not found.")
        return []


async def connect_existing_sessions(proxies, required_count):
    """Retrieve and connect to sessions in the database with MTProto proxy support."""
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]

        for retry in range(5):  # Retry multiple times per proxy
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
                    logger.info(f"Connected to session for phone: {phone} using proxy: {formatted_proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session for {phone} not authorized. Removing from DB.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception:
                logger.warning(f"Proxy issue for session {phone}: {formatted_proxy}. Retrying... ({retry + 1}/5)")

    return existing_sessions


async def report_message(client, chat_id, message_id, reason, custom_message):
    """Report a specific message in a group."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        result = await client(ReportRequest(
            peer=chat_id,
            id=[message_id],  
            reason=REPORT_REASONS[reason],
            message=custom_message
        ))

        if result:
            logger.info(f"[✓] Reported message {message_id} in chat {chat_id} for {reason}.")
            return 1
        else:
            logger.warning(f"[✗] Failed to report message {message_id} in chat {chat_id}.")
            return 0

    except Exception as e:
        logger.error(f"Error reporting message {message_id} in chat {chat_id}: {str(e)}")
        return 0


def extract_chat_and_message_id(message_link):
    """Extract chat ID and message ID from Telegram message links (private and public)."""
    
    # Private group message (e.g., t.me/c/123456789/567)
    private_match = re.search(r"https://t\.me/c/(\d+)/(\d+)", message_link)
    if private_match:
        chat_id = int(f"-100{private_match.group(1)}")  # Convert to full chat ID
        message_id = int(private_match.group(2))
        return chat_id, message_id
    
    # Public group/channel message (e.g., t.me/username/567)
    public_match = re.search(r"https://t\.me/([\w\d_]+)/(\d+)", message_link)
    if public_match:
        username = public_match.group(1)
        message_id = int(public_match.group(2))
        return username, message_id  # Return username instead of chat ID
    
    return None, None  # Invalid link

async def report_entity(client, entity, reason, custom_message):
    """Report a user, group, or channel."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        entity_peer = await client.get_input_entity(entity)
        result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], custom_message))

        if result:
            logger.info(f"[✓] Reported {entity} for {reason}.")
            return 1
        else:
            logger.warning(f"[✗] Failed to report {entity}.")
            return 0

    except Exception as e:
        logger.error(f"Error reporting {entity}: {str(e)}")
        return 0

async def assign_proxies_to_new_sessions(proxies, count):
    """Log in new accounts with a proxy and store their session strings."""
    new_clients = []

    for i in range(count):
        phone = input(f"Enter phone number for new account {i + 1}: ").strip()

        for retry in range(5):  # Try different proxies if needed
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]
            formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])

            client = TelegramClient(
                StringSession(),
                API_ID,
                API_HASH,
                connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
                proxy=formatted_proxy,
            )

            await client.connect()

            try:
                sent_code = await client.send_code_request(phone)
                otp = input(f"Enter OTP for {phone}: ").strip()
                await client.sign_in(phone, otp, phone_code_hash=sent_code.phone_code_hash)

                if await client.is_user_authorized():
                    print(f"[✓] Logged in successfully: {phone}")

                    # Save session
                    session_string = client.session.save()
                    sessions_collection.insert_one({"phone": phone, "session_string": session_string})

                    new_clients.append(client)
                    break  # Stop retrying since login worked

            except Exception as e:
                print(f"[✗] Error logging in {phone} with proxy {formatted_proxy}: {str(e)}")
                await client.disconnect()
                continue  # Try another proxy

    return new_clients

async def main():
    print("\n=== Telegram Multi-Account Reporting Tool ===")

    account_count = int(input("Enter the number of accounts to use for reporting: "))
    proxies = load_proxies()

    # Load existing sessions
    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"\n[✓] {existing_count} existing sessions found. No new accounts needed.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        print(f"\n[!] Only {existing_count} sessions found. Logging in {account_count - existing_count} new accounts.")
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, account_count - existing_count)
        clients = existing_clients + new_clients  # Combine both sets of clients

    # Report selection
    print("\nSelect the type of report:")
    print("1 - Report a Group/Channel/User")
    print("2 - Report a Specific Message in a Group")
    choice = int(input("Enter your choice (1/2): "))

    if choice == 1:
        entity = input("Enter the group/channel username or user ID to report: ").strip()
    elif choice == 2:
        message_link = input("Enter the message link to report: ").strip()
        entity, message_id = extract_chat_and_message_id(message_link)
        if not entity or not message_id:
            print("[✗] Invalid message link!")
            return

    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    reason_choice = int(input("Enter your choice: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]
    custom_message = input("Enter a custom report message: ")

    # Execute reports
    for client in clients:
        if choice == 1:
            await report_entity(client, entity, reason, custom_message)
        elif choice == 2:
            await report_message(client, entity, message_id, reason, custom_message)

    print("\n[✓] Reports submitted successfully!")

    # Disconnect all clients
    for client in clients:
        await client.disconnect()
