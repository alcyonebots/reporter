import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import InputReportReasonSpam, InputReportReasonViolence, InputReportReasonPornography, InputReportReasonChildAbuse, InputReportReasonCopyright, InputReportReasonFake, InputReportReasonOther
from telethon.sessions import StringSession

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = "29872536"  # Your API ID
API_HASH = "65e1f714a47c0879734553dc460e98d6"  # Your API Hash

# Accounts configuration
ACCOUNTS = [
    {"phone": "+919108454466", "report_count": 0, "client": None, "string_session": None},
    {"phone": "+918329056828", "report_count": 0, "client": None, "string_session": None},
    # Add more accounts here if needed
]

# Report reasons mapping
REPORT_REASONS = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child abuse": InputReportReasonChildAbuse(),
    "copyright": InputReportReasonCopyright(),
    "fake": InputReportReasonFake(),
    "other": InputReportReasonOther(),
}

# Initialize clients and load sessions
def initialize_clients():
    for account in ACCOUNTS:
        # Create a new client for each account (ensure it's not using old sessions)
        account["client"] = TelegramClient(StringSession(), API_ID, API_HASH)
        logger.info(f"Client for {account['phone']} initialized.")

# Function to handle OTP and 2FA
async def handle_otp(account, client):
    try:
        # Attempt to start the client; it will prompt for OTP if required
        await client.start(phone=account["phone"])
    except PhoneCodeInvalidError:  # OTP required
        logger.info(f"OTP required for {account['phone']}. Please provide the OTP.")
        otp = input(f"Enter OTP for {account['phone']}: ")
        await client.start(phone=account["phone"], code=otp)
    except SessionPasswordNeededError:  # 2FA required
        logger.info(f"2FA required for {account['phone']}. Please provide the password.")
        password = input(f"Enter 2FA password for {account['phone']}: ")
        await client.start(phone=account["phone"], password=password)

# Reporting a group
async def report_group(account, group_link, reason_text, times_to_report):
    try:
        reason = REPORT_REASONS.get(reason_text.lower(), None)
        if not reason:
            return "Invalid reason. Please choose from 'spam', 'violence', 'pornography', 'child abuse', 'copyright', 'fake', or 'other'."
        
        # Get the group chat by link
        group = await account["client"].get_entity(group_link)
        
        # Check if bot is a member of the group
        try:
            await account["client"](JoinChannelRequest(group))
        except Exception as e:
            logger.error(f"Error joining group {group_link}: {e}")
            return f"Error: Could not join group {group_link}. Please make sure the group is public or the bot is already a member."

        # Report the group for the specified number of times
        for _ in range(times_to_report):
            await account["client"](ReportPeerRequest(group, reason))
            account["report_count"] += 1

        return f"Successfully reported {group_link} for {reason_text} {times_to_report} times. Total reports by this account: {account['report_count']}."
    
    except ChatAdminRequiredError:
        return "Error: You must be an admin to report this group."
    except Exception as e:
        logger.error(f"Error while reporting group {group_link}: {e}")
        return f"Error: {e}"

# Command to report a group
def report(update, context):
    if len(context.args) < 3:
        update.message.reply_text("Usage: /report <group_link> <reason> <number_of_reports>")
        return

    group_link = context.args[0]
    reason_text = context.args[1]
    try:
        times_to_report = int(context.args[2])
    except ValueError:
        update.message.reply_text("Invalid number of reports. Please provide a valid integer.")
        return

    # Find the account with the lowest report count
    account = min(ACCOUNTS, key=lambda acc: acc["report_count"])

    # Run the report asynchronously
    result = asyncio.run(report_group(account, group_link, reason_text, times_to_report))
    update.message.reply_text(result)

    # Inform if an account has reported 10 times
    if account["report_count"] >= 10:
        update.message.reply_text(f"Account {account['phone']} has reported 10 times!")

    # Save the string session for the account
    account["string_session"] = account["client"].session.save()

# Command to show stats
def stats(update, context):
    stats_msg = "Report Stats:\n"
    for account in ACCOUNTS:
        stats_msg += f"Account {account['phone']}: {account['report_count']} reports\n"
    update.message.reply_text(stats_msg)

# Function to handle start command
def start(update, context):
    update.message.reply_text("Welcome! Send /report <group_link> <reason> <number_of_reports> to report a group.\nSend /stats to see report stats.")

# Main function to set up the bot
def main():
    # Initialize clients and load sessions
    initialize_clients()

    # Set up the updater and dispatcher
    updater = Updater("8077898847:AAHteiAz12NWkO096hBmkEIoqAjk0--DtEk", use_context=True)
    dispatcher = updater.dispatcher

    # Set up handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("report", report))
    dispatcher.add_handler(CommandHandler("stats", stats))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
        
