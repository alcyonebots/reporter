import asyncio
import logging
from telethon import TelegramClient, connection
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ReportRequest  # Import required function    
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "testsex"
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
            proxies = [
                tuple(line.strip().split(",")) for line in f.readlines() if line.strip()
            ]
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
                    logger.info(f"Connected to existing session for {phone} using MTProto Proxy: {formatted_proxy}")
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(f"Session for {phone} is not authorized. Removing from database.")
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(f"Proxy issue for session {phone}: {formatted_proxy}. Retrying... ({retry + 1}/5)")
    
    return existing_sessions

async def login(phone, proxy=None):
    """Login function with MTProto proxy support."""
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
            logger.info(f"Account {phone} is not authorized. Logging in...")
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
        logger.error(f"Error during login for account {phone}: {str(e)}")
        return None

async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    """Log in to new accounts using MTProto proxies."""
    new_sessions = []
    for i in range(accounts_needed):
        phone = input(f"Enter the phone number for account {i + 1}: ")
        proxy = None if not proxies else proxies[i % len(proxies)]
        formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])

        client = await login(phone, proxy=proxy)
        if client:
            logger.info(f"[✓] Logged in to new account {phone} using MTProto Proxy: {formatted_proxy}")
            new_sessions.append(client)
    
    return new_sessions
    
async def report_entity(client, entity, reason, times_to_report, message_id=None, custom_message=None):
    """Report an entity (user/group/channel) or a specific message."""
    try:
        entity_peer = await client.get_input_entity(entity)
        message = custom_message if custom_message else f"Reported for {reason}."
        successful_reports = 0

        for _ in range(times_to_report):
            try:
                if message_id:
                    # ✅ Correct usage of `messages.ReportRequest`
                    result = await client(ReportRequest(
                        peer=entity_peer,  
                        id=[int(message_id)],  # Message ID inside a list
                        option=1,  # Required field (1 is the standard option for reporting)
                        message=message  # Required field (custom or default)
                    ))
                else:
                    # ✅ Correct usage of `ReportPeerRequest`
                    result = await client(ReportPeerRequest(
                        peer=entity_peer,
                        reason=REPORT_REASONS[reason],
                        message=message
                    ))

                if result:
                    successful_reports += 1
                    logger.info(f"[✓] Successfully reported {entity}.")
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

    account_count = int(input("Enter the number of accounts to use for reporting: "))
    proxies = load_proxies()

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"\n[✓] Using {account_count} existing sessions.")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        print(f"\n[!] {existing_count} sessions found. {account_count - existing_count} more accounts are needed.")
        new_accounts_needed = account_count - existing_count
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, new_accounts_needed)
        clients = existing_clients + new_clients

    print("\nSelect the type of entity to report:")
    print("1 - Group")
    print("2 - Channel")
    print("3 - User")
    print("4 - Specific Message")
    choice = int(input("Enter your choice (1/2/3/4): "))

    entity = input("Enter the entity username or ID: ").strip()

    # Ask for message ID **only** if reporting a specific message
    message_id = None
    if choice == 4:
        message_id = int(input("Enter the Message ID to report: "))

    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")

    reason_choice = int(input("Enter your choice for report reason: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    custom_message = input("Enter a custom report message (leave blank for default): ").strip() or None
    times_to_report = int(input("Enter the number of times to report: "))

    # ✅ Run all report tasks concurrently
    tasks = [report_entity(client, entity, reason, times_to_report, message_id, custom_message) for client in clients]
    results = await asyncio.gather(*tasks)
    total_successful_reports = sum(results)

    print(f"\n[✓] Total successful reports submitted: {total_successful_reports}")

    for client in clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
