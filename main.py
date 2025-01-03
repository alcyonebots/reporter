import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import UserPrivacyRestrictedError, FloodWaitError
from telethon.errors import ChatAdminRequiredError
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.messages import JoinChannelRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonFake,
    InputReportReasonDrugs,
    InputReportReasonOther,
)

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8077898847:AAHteiAz12NWkO096hBmkEIoqAjk0--DtEk"

# Telegram account credentials
ACCOUNTS = [
    {"string_session": "1BVtsOIgBuxZ_i9g5pFp1IiN_9uzQSmV_ihyFq2hY0uhuySWHmHEZR1zb7XUWdmXdYg8hvC6ET9URHbTb6xKAZGnVO8koAeLVKJQ3tS_1HOw4LUZn4YgaVerfix3gY67w5I739t_D1jXGoNJZN1sjcEdI2rwpWHA8N616CMroED-oAd2DQ6EUjkrUzxideiPUXQk98zIAOSiuKnK3DsUps_RnTxVQnSb300Dm2rBpihd9xD0YaYuWmhRYpKPCh5gYsqJgkZLQjVD_k5eiTCgNWrp1FxNrJ1BrvErcJkre4UpvJBbD89Dg15-UOJFMndqAOPDb1kr1PI6ivnk5BFCCFHVKq4IFz6Q=", "phone": "+919108454466", "report_count": 0},
    {"string_session": "1BVtsOIgBu74VmxmT5QrA-sHXOI0UjhQ0r4Tqjus6pX8FGFKEYA__3cG7IX5MnZaDRrRuSVvCdfXzhEsAwaUbPibE2JuYsVJ53Eirh0lnrcNfKG3z70dwS0YGO5akspc3xg_UrfnyQkdSneBtZrSbx5DJvTTuGZmJ7WyXPPLovxItFSG9im3W_XU5DWxvDT0pNEFrTp9M33S4SzmNEUNi69H_30WBkoZzpOj3x5fAPgXPoByCWbC4IT4PyG13nunyfFuGfHYPfgzyoKaTSjoLEW4r9aDhRoPILVNPAJZ6LYLEzzt9xRnjPyRgdC8IBV-FwLeAsWaGLQPcyBlTYCV0EFyl2gIX-1g=", "phone": "+918329056828", "report_count": 0},
    # Add more accounts here with their string sessions
]

# Report reasons mapping
REPORT_REASONS = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child abuse": InputReportReasonChildAbuse(),
    "copyright": InputReportReasonCopyright(),
    "fake": InputReportReasonFake(),
    "drugs": InputReportReasonDrugs(),
    "other": InputReportReasonOther(),
}

async def report_group(account, group_link, reason_text, times_to_report, update):
    """Report a group using a specific account."""
    client = TelegramClient(f"session_{account['phone']}", api_id=API_ID, api_hash=API_HASH)
    await client.connect()

    try:
        logger.info(f"Logged in as {account['phone']} using string session")
        if not await client.is_user_authorized():
            logger.error(f"Account {account['phone']} is not authorized.")
            return "Account not authorized."

        # Check if bot is part of the group
        group = await client.get_entity(group_link)
        if not group.is_participant:
            try:
                await client(JoinChannelRequest(group_link))
                logger.info(f"Joined group: {group_link}")
            except ChatAdminRequiredError:
                logger.error(f"Cannot join group {group_link}. Admin privileges required.")
                return "Cannot join group. Admin privileges required."

        # Report the group multiple times
        for _ in range(times_to_report):
            report_reason = REPORT_REASONS.get(reason_text.lower(), REPORT_REASONS["other"])
            await client(
                ReportPeerRequest(
                    peer=group,
                    reason=report_reason,
                    message=f"Reported group '{group.title}' for: {reason_text}"
                )
            )
            account["report_count"] += 1
            logger.info(f"Reported group '{group.title}' for: {reason_text}")

        # Check if the account has reported 10 times
        if account["report_count"] >= 10:
            logger.info(f"Account {account['phone']} has reported 10 times.")
            await update.message.reply_text(f"Account {account['phone']} has reported 10 times.")
            return f"Account {account['phone']} has reported 10 times."

        return f"Successfully reported group '{group.title}' {times_to_report} times for: {reason_text}"

    except UserPrivacyRestrictedError:
        logger.error("Privacy restrictions prevent reporting.")
        return "Privacy restrictions prevent reporting."
    except FloodWaitError as e:
        logger.warning(f"Flood wait: wait {e.seconds} seconds before retrying.")
        return f"Flood wait: wait {e.seconds} seconds before retrying."
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}"
    finally:
        await client.disconnect()

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /report command."""
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /report <group_link> <reason> <number_of_times_to_report>\n\n"
            "Example: /report https://t.me/examplegroup spam 5"
        )
        return

    group_link = context.args[0]
    reason_text = context.args[1]
    times_to_report = int(context.args[2])

    results = []
    for account in ACCOUNTS:
        result = await report_group(account, group_link, reason_text, times_to_report, update)
        results.append(result)

    await update.message.reply_text("\n".join(results))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reporting stats."""
    stats = "\n".join([f"{acc['phone']}: {acc['report_count']} reports" for acc in ACCOUNTS])
    await update.message.reply_text(f"Report stats:\n{stats}")

def main():
    """Start the bot."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("stats", stats))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
