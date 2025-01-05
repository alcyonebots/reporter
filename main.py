import asyncio
import random
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
import logging

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

async def login(phone, proxy=None):
    try:
        # Check if session exists in the database
        session_data = sessions_collection.find_one({"phone": phone})
        if session_data:
            session_string = session_data["session_string"]
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=proxy)
        else:
            client = TelegramClient(f'session_{phone}', API_ID, API_HASH, proxy=proxy)

        await client.connect()

        # Check if already authorized
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

    except SessionPasswordNeededError:
        logger.error(f"2FA is enabled. Please enter the 2FA password for account {phone}.")
        password = input(f"Enter the 2FA password for {phone}: ")
        await client.sign_in(password=password)
    except Exception as e:
        logger.error(f"An error occurred during login for account {phone}: {str(e)}")
        return None

async def login_with_proxy(phone, proxies, max_attempts_per_proxy=2):
    """Attempt to log in using proxies, switching proxies after 2 failed attempts."""
    for proxy_index, proxy in enumerate(proxies):
        attempts = 0
        while attempts < max_attempts_per_proxy:
            try:
                formatted_proxy = (proxy[0].upper(), proxy[1], int(proxy[2]))
                logger.info(f"Attempt {attempts + 1}/{max_attempts_per_proxy} for {phone} using proxy: {formatted_proxy}")

                client = await login(phone, proxy=formatted_proxy)
                if client:
                    logger.info(f"Successfully logged in for {phone} using proxy: {formatted_proxy}")
                    return client
            except Exception as e:
                attempts += 1
                logger.error(f"Attempt {attempts} failed for {phone} using proxy {proxy}: {str(e)}")

        logger.warning(f"Switching to the next proxy for {phone} after {max_attempts_per_proxy} failed attempts.")

    logger.error(f"All proxies failed for {phone}. Skipping account.")
    return None

async def report_entity(client, entity, reason, times_to_report):
    try:
        if reason not in REPORT_REASONS:
            logger.error(f"Invalid report reason: {reason}")
            return

        # Resolve entity to InputPeer
        entity_peer = await client.get_input_entity(entity)

        # Check if entity is valid
        if isinstance(entity_peer, (InputPeerChat, InputPeerChannel, InputPeerUser)):
            # Define a default message for each report reason
            default_messages = {
                "spam": "This is spam.",
                "violence": "This content promotes violence.",
                "pornography": "This content contains pornography.",
                "child abuse": "This content is related to child abuse.",
                "copyright infringement": "This content infringes on copyright.",
                "other": "This is an inappropriate entity.",
            }
            message = default_messages.get(reason, "This is a reported entity.")
            
            for _ in range(times_to_report):
                result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message))
                logger.info(f"Successfully reported {entity} for {reason}. Result: {result}")
        else:
            logger.error(f"Invalid entity type for reporting: {type(entity_peer).__name__}")

    except Exception as e:
        logger.error(f"Failed to report {entity}: {str(e)}")

async def main():
    print("=== Telegram Multi-Account Reporting Tool ===")

    # Step 1: Log in to multiple accounts
    account_count = int(input("Enter the number of accounts to use: "))

    # Ask if proxies should be used
    use_proxies = input("Do you want to use proxies? (y/n): ").strip().lower()
    proxies = load_proxies() if use_proxies == "y" else None
    if use_proxies == "y" and not proxies:
        print("No proxies found in 'proxy.txt'. Proceeding without proxies.")
        use_proxies = "n"

    clients = []
    for i in range(account_count):
        phone = input(f"Enter the phone number for account {i + 1} (e.g., +123456789): ")

        if use_proxies == "y":
            client = await login_with_proxy(phone, proxies)
        else:
            client = await login(phone)

        if client:
            clients.append(client)
        else:
            print(f"Skipping account {phone} due to login failure.")

    # Step 2: Select type of entity to report
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

    # Step 3: Get the entity and reason
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

    # Step 4: Get the number of reports
    try:
        times_to_report = int(input("Enter the number of times to report: "))
        if times_to_report <= 0:
            print("Number of reports must be greater than 0. Exiting.")
            return
    except ValueError:
        print("Invalid input. Exiting.")
        return

    # Step 5: Report the entity from all accounts
    for client in clients:
        await report_entity(client, entity, reason, times_to_report)

    # Step 6: Disconnect all clients
    for client in clients:
        await client.disconnect()
    print(f"Reports submitted {times_to_report} times. All clients disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
            
