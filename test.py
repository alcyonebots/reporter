import asyncio
import logging
import os
import random
import pyfiglet
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam, InputReportReasonViolence, InputReportReasonPornography, 
    InputReportReasonChildAbuse, InputReportReasonCopyright, InputReportReasonFake, 
    InputReportReasonOther
)
from pymongo import MongoClient
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# ASCII Title
ascii_title = pyfiglet.figlet_format("Massacres", font="slant")
print(Fore.RED + ascii_title + Style.RESET_ALL)

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Telegram API Credentials
API_ID = "29872536"
API_HASH = "65e1f714a47c0879734553dc460e98d6"

# MongoDB connection
MONGO_URI = "mongodb+srv://denji3494:denji3494@cluster0.bskf1po.mongodb.net/"
DB_NAME = "Report"
COLLECTION_NAME = "session"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db[COLLECTION_NAME]

# Load proxy from file
PROXIES = []
if os.path.exists("proxy.txt"):
    with open("proxy.txt", "r") as f:
        PROXIES = [line.strip() for line in f if line.strip()]

async def login_new_account():
    """Prompt user for login and save session to MongoDB."""
    phone = input(Fore.LIGHTBLUE_EX + "Enter your phone number (with country code): " + Style.RESET_ALL)

    session = StringSession()
    tg_client = TelegramClient(session, API_ID, API_HASH)

    if PROXIES:
        proxy = random.choice(PROXIES)
        tg_client.session.proxy = proxy

    await tg_client.connect()

    try:
        await tg_client.send_code_request(phone)
        otp = input(Fore.YELLOW + "Enter the OTP sent to your Telegram: " + Style.RESET_ALL)
        await tg_client.sign_in(phone, otp)
    except SessionPasswordNeededError:
        password = input(Fore.RED + "2FA is enabled. Enter your password: " + Style.RESET_ALL)
        await tg_client.sign_in(password=password)

    session_string = tg_client.session.save()
    sessions_collection.insert_one({"session": session_string})
    print(Fore.GREEN + "[✓] Login successful! Session saved." + Style.RESET_ALL)
    await tg_client.disconnect()

async def load_sessions():
    """Load active sessions from MongoDB."""
    sessions = sessions_collection.find()
    if sessions:
        return [session["session"] for session in sessions]
    return []

async def report_target(client, entity, reason, comment, report_count):
    """Send reports using Telethon."""
    reasons = {
        1: InputReportReasonSpam(),
        2: InputReportReasonViolence(),
        3: InputReportReasonPornography(),
        4: InputReportReasonChildAbuse(),
        5: InputReportReasonCopyright(),
        6: InputReportReasonFake(),
        7: InputReportReasonOther()
    }

    success_count = 0

    for i in range(report_count):
        try:
            await client(ReportPeerRequest(peer=entity, reason=reasons[reason], message=comment))
            success_count += 1
            print(Fore.GREEN + f"[✓] Report {i+1} sent successfully." + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f"[X] Report {i+1} failed: {e}" + Style.RESET_ALL)

    print(Fore.CYAN + f"\n[✓] Total successful reports submitted: {success_count}" + Style.RESET_ALL)

async def main():
    """Main function to handle reporting."""
    # Load existing sessions
    sessions = await load_sessions()
    if not sessions:
        print(Fore.YELLOW + "[!] No active sessions found. Please log in first." + Style.RESET_ALL)
        await login_new_account()
        sessions = await load_sessions()

    num_accounts = int(input(Fore.LIGHTCYAN_EX + "Enter the number of accounts to use for reporting: " + Style.RESET_ALL))
    
    # Select type of entity to report
    print(Fore.MAGENTA + "\nSelect the type of entity to report:" + Style.RESET_ALL)
    print(Fore.CYAN + "1 - User\n2 - Group\n3 - Channel\n4 - Message" + Style.RESET_ALL)
    entity_type = int(input(Fore.LIGHTCYAN_EX + "Enter your choice (1/2/3/4): " + Style.RESET_ALL))

    entity = input(Fore.YELLOW + "Enter the username or user ID to report: " + Style.RESET_ALL)

    # Select reason for reporting
    print(Fore.MAGENTA + "\nAvailable reasons for reporting:" + Style.RESET_ALL)
    print(Fore.CYAN + "1 - Spam\n2 - Violence\n3 - Pornography\n4 - Child Abuse\n5 - Copyright Infringement\n6 - Scam\n7 - Other" + Style.RESET_ALL)
    reason = int(input(Fore.LIGHTCYAN_EX + "Enter your choice: " + Style.RESET_ALL))

    comment = input(Fore.YELLOW + "Enter a comment for the report (optional): " + Style.RESET_ALL)
    report_count = int(input(Fore.LIGHTCYAN_EX + "Enter the number of times to report: " + Style.RESET_ALL))

    tasks = []
    for session in sessions[:num_accounts]:
        tg_client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await tg_client.connect()

        if PROXIES:
            proxy = random.choice(PROXIES)
            tg_client.session.proxy = proxy

        tasks.append(report_target(tg_client, entity, reason, comment, report_count))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
