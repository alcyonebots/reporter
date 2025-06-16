import asyncio
import logging
import socks
from telethon import TelegramClient, connection
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

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB setup
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "idnunu"
COLLECTION_NAME = "sessions"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

# Report reasons
REPORT_REASONS = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child abuse": InputReportReasonChildAbuse(),
    "copyright infringement": InputReportReasonCopyright(),
    "scam": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}

# Load SOCKS5 proxies from file
def load_proxies(file_path="proxy.txt"):
    try:
        with open(file_path, "r") as f:
            proxies = [tuple(line.strip().split(",")) for line in f if line.strip()]
        return proxies
    except FileNotFoundError:
        logger.error(f"Proxy file '{file_path}' not found.")
        return []

# Format proxy tuple for Telethon
def format_socks5(proxy_tuple):
    host, port = proxy_tuple[0], int(proxy_tuple[1])
    user = proxy_tuple[2] if len(proxy_tuple) > 2 else None
    pwd = proxy_tuple[3] if len(proxy_tuple) > 3 else None
    return (socks.SOCKS5, host, port, True, user, pwd)

# Connect to existing sessions from DB
async def connect_existing_sessions(proxies, required_count):
    existing_sessions = []
    session_docs = list(sessions_collection.find())
    for i, session_data in enumerate(session_docs[:required_count]):
        phone = session_data["phone"]
        session_string = session_data["session_string"]

        for retry in range(5):
            proxy = None if not proxies else format_socks5(proxies[(i + retry) % len(proxies)])

            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH,
                    proxy=proxy,
                    connection=connection.ConnectionTcpFull
                )
                await client.connect()
                if await client.is_user_authorized():
                    logger.info(f"Connected: {phone} using SOCKS5: {proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Unauthorized session: {phone}. Removing.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(f"Retry {retry+1} for {phone} with proxy {proxy}: {e}")
    return existing_sessions

# Login new session
async def login(phone, proxy=None):
    try:
        formatted_proxy = format_socks5(proxy) if proxy else None
        client = TelegramClient(
            f'session_{phone}',
            API_ID,
            API_HASH,
            proxy=formatted_proxy,
            connection=connection.ConnectionTcpFull
        )
        await client.connect()

        if not await client.is_user_authorized():
            logger.info(f"Login required for {phone}")
            await client.send_code_request(phone)
            otp = input(f"Enter OTP for {phone}: ")
            await client.sign_in(phone, otp)

            if not await client.is_user_authorized():
                password = input(f"Enter 2FA password for {phone}: ")
                await client.sign_in(password=password)

            session_string = StringSession.save(client.session)
            sessions_collection.update_one(
                {"phone": phone},
                {"$set": {"session_string": session_string}},
                upsert=True,
            )
            logger.info(f"Session saved: {phone}")
        else:
            logger.info(f"Authorized session found: {phone}")

        return client

    except Exception as e:
        logger.error(f"Login error for {phone}: {str(e)}")
        return None

# Assign proxies to new sessions
async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    new_sessions = []
    for i in range(accounts_needed):
        phone = input(f"Enter phone number for account {i + 1}: ")
        proxy = None if not proxies else proxies[i % len(proxies)]
        client = await login(phone, proxy=proxy)
        if client:
            logger.info(f"[✓] Logged in {phone} with SOCKS5")
            new_sessions.append(client)
    return new_sessions

# Report function
async def report_entity(client, entity, reason, times_to_report, message, msg_id=None):
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        entity_peer = await client.get_input_entity(entity)
        successful_reports = 0

        for _ in range(times_to_report):
            try:
                if msg_id:
                    result = await client(ReportRequest(
                        peer=entity_peer,
                        id=[msg_id],
                        reason=REPORT_REASONS[reason],
                        message=message
                    ))
                else:
                    result = await client(ReportPeerRequest(
                        peer=entity_peer,
                        reason=REPORT_REASONS[reason],
                        message=message
                    ))

                if result:
                    successful_reports += 1
                    logger.info(f"[✓] Reported {entity} for {reason} ({'message' if msg_id else 'peer'})")
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"Reporting failed for {entity}: {e}")
        return successful_reports

    except Exception as e:
        logger.error(f"Report setup error: {str(e)}")
        return 0

# Main
async def main():
    print("\n=== Telegram Multi-Account Reporter [SOCKS5] ===\n")
    account_count = int(input("Enter number of accounts to use: "))
    proxies = load_proxies()

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"[✓] {account_count} sessions available.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        new_needed = account_count - existing_count
        print(f"[!] Logging into {new_needed} new accounts...")
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, new_needed)
        clients = existing_clients + new_clients

    print("\nSelect target type:")
    print("1 - Group")
    print("2 - Channel")
    print("3 - User")
    print("4 - Specific message in a chat")
    choice = int(input("Enter choice (1/2/3/4): "))

    entity = input("Enter target username or ID: ").strip()
    msg_id = int(input("Enter message ID to report (only for option 4): ")) if choice == 4 else None

    print("\nReasons:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    reason_choice = int(input("Choose reason: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    times_to_report = int(input("Number of times to report: "))
    message = input("Custom report message: ").strip()

    tasks = [
        report_entity(client, entity, reason, times_to_report, message, msg_id=msg_id)
        for client in clients
    ]
    results = await asyncio.gather(*tasks)
    total_success = sum(results)

    print(f"\n[✓] Total successful reports: {total_success}")

    for client in clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
