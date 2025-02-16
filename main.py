import asyncio
import logging
from telethon import TelegramClient, connection
from telethon.sessions import StringSession
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
    "scam": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}


async def report_entity(client, entity, reason, times_to_report, message_id=None, custom_message=None):
    """Report an entity or a specific message with error handling and logging."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return 0

        entity_peer = await client.get_input_entity(entity)
        message = custom_message if custom_message else f"Reported for {reason}."
        successful_reports = 0

        for _ in range(times_to_report):
            try:
                if message_id:
                    result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message, message_id))
                else:
                    result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message))

                if result:
                    successful_reports += 1
                    logger.info(f"[✓] Reported {entity} (Message ID: {message_id}) for {reason}.")
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
    
    # Ask user what type of entity to report
    print("\nSelect the type of entity to report:")
    print("1 - Group")
    print("2 - Channel")
    print("3 - User")
    print("4 - Specific Message")
    choice = int(input("Enter your choice (1/2/3/4): "))

    entity = None
    message_id = None

    if choice in [1, 2, 3]:
        entity = input("Enter the group/channel username or user ID to report: ").strip()
    elif choice == 4:
        entity = input("Enter the group/channel username or user ID where the message is located: ").strip()
        message_id = int(input("Enter the message ID to report: ").strip())
    else:
        print("Invalid choice. Exiting.")
        return

    print("\nAvailable reasons for reporting:")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        print(f"{idx} - {reason.capitalize()}")
    reason_choice = int(input("Enter your choice: "))
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    custom_message = input("Enter a custom report message (leave blank for default): ").strip() or None
    times_to_report = int(input("Enter the number of times to report: "))

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        print(f"\n[✓] Using {account_count} existing sessions.")
        clients = [TelegramClient(StringSession(doc["session_string"]), API_ID, API_HASH) for doc in session_docs[:account_count]]
    else:
        print("\nNot enough existing sessions. Please log in to new accounts.")
        clients = []
        for i in range(account_count - existing_count):
            phone = input(f"Enter phone number {i+1}: ").strip()
            client = TelegramClient(f'session_{phone}', API_ID, API_HASH)
            await client.connect()
            clients.append(client)

    total_successful_reports = sum(
        await report_entity(client, entity, reason, times_to_report, message_id, custom_message)
        for client in clients
    )

    print(f"\n[✓] Total successful reports submitted: {total_successful_reports}")

    for client in clients:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
