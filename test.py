import asyncio
import logging
import os
import pyfiglet
import random
from telethon import TelegramClient
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
from colorama import Fore, Style, init

init(autoreset=True)

# ASCII Title
ascii_title = pyfiglet.figlet_format("Massacres", font="slant")
print(Fore.RED + ascii_title + Style.RESET_ALL)

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "Report"
COLLECTION_NAME = "session"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

# Load proxies from proxy.txt
def load_proxies():
    """Load SOCKS5 proxies from proxy.txt"""
    proxies = []
    if os.path.exists("proxy.txt"):
        with open("proxy.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies

PROXIES = load_proxies()

REPORT_REASONS = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child abuse": InputReportReasonChildAbuse(),
    "copyright infringement": InputReportReasonCopyright(),
    "scam": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}

async def connect_existing_sessions():
    """Connect to existing Telegram sessions stored in MongoDB."""
    clients = []
    for session_data in sessions_collection.find():
        session_string = session_data["session_string"]
        phone = session_data["phone"]
        
        # Use a random proxy if available
        proxy = random.choice(PROXIES) if PROXIES else None
        proxy_config = {"proxy_type": "socks5", "addr": proxy.split(":")[0], "port": int(proxy.split(":")[1])} if proxy else None

        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=proxy_config)
            await client.connect()
            if await client.is_user_authorized():
                logger.info(Fore.GREEN + f"Connected to session for {phone}" + Style.RESET_ALL)
                clients.append(client)
            else:
                logger.warning(Fore.YELLOW + f"Session for {phone} is not authorized. Removing it." + Style.RESET_ALL)
                sessions_collection.delete_one({"phone": phone})
        except Exception as e:
            logger.error(Fore.RED + f"Failed to connect {phone}: {str(e)}" + Style.RESET_ALL)
    return clients

async def report_entity(client, entity, reason, times, comment):
    """Report a user, group, or channel with a custom comment."""
    try:
        if reason not in REPORT_REASONS:
            logger.error(Fore.RED + f"Invalid reason: {reason}" + Style.RESET_ALL)
            return 0

        entity_peer = await client.get_input_entity(entity)

        success_count = 0
        for _ in range(times):
            try:
                result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], comment))
                if result:
                    success_count += 1
                    logger.info(Fore.GREEN + f"[✓] Report {success_count}/{times} sent successfully!" + Style.RESET_ALL)
            except Exception as e:
                logger.warning(Fore.YELLOW + f"Failed to report: {e}" + Style.RESET_ALL)

        return success_count
    except Exception as e:
        logger.error(Fore.RED + f"Error reporting {entity}: {str(e)}" + Style.RESET_ALL)
        return 0

async def main():
    """Main function to handle reporting logic."""
    print(Fore.CYAN + "\n=== Telegram Multi-Account Reporting Tool ===" + Style.RESET_ALL)
    
    num_accounts = int(input(Fore.LIGHTBLUE_EX + "Enter the number of accounts to use for reporting: " + Style.RESET_ALL))
    
    existing_clients = await connect_existing_sessions()
    available_clients = existing_clients[:num_accounts]

    if not available_clients:
        print(Fore.RED + "[!] No active sessions found. Please log in first." + Style.RESET_ALL)
        return

    print(Fore.GREEN + f"[✓] {len(available_clients)} sessions loaded successfully." + Style.RESET_ALL)

    print("\nSelect the type of entity to report:")
    print("1 - User")
    print("2 - Group")
    print("3 - Channel")
    print("4 - Specific Message")
    choice = input(Fore.LIGHTBLUE_EX + "Enter your choice (1/2/3/4): " + Style.RESET_ALL)

    entity = input(Fore.LIGHTBLUE_EX + "Enter the username or user ID to report: " + Style.RESET_ALL)

    print("\nAvailable reasons for reporting:")
    print("1 - Spam")
    print("2 - Violence")
    print("3 - Pornography")
    print("4 - Child abuse")
    print("5 - Copyright infringement")
    print("6 - Scam")
    print("7 - Other")
    
    reason_choice = int(input(Fore.LIGHTBLUE_EX + "Enter your choice: " + Style.RESET_ALL))
    reason_mapping = {
        1: "spam",
        2: "violence",
        3: "pornography",
        4: "child abuse",
        5: "copyright infringement",
        6: "scam",
        7: "other",
    }
    reason = reason_mapping.get(reason_choice, "other")

    times = int(input(Fore.LIGHTBLUE_EX + "Enter the number of times to report: " + Style.RESET_ALL))

    comment = input(Fore.LIGHTBLUE_EX + "Enter a custom report comment: " + Style.RESET_ALL)
    if not comment.strip():
        comment = "This content violates Telegram's policies."

    total_reports = 0
    for client in available_clients:
        total_reports += await report_entity(client, entity, reason, times, comment)

    print(Fore.GREEN + f"\n[✓] Total successful reports submitted: {total_reports}" + Style.RESET_ALL)

    for client in available_clients:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
