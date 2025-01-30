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
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
from rich.style import Style

# Initialize Rich console
console = Console()

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

        for retry in range(5):  # Retry multiple times per proxy
            proxy = None if not proxies else proxies[(i + retry) % len(proxies)]
            formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])  # (host, port, secret)

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
                    logger.info(
                        f"Connected to existing session for phone: {phone} using MTProto Proxy: {formatted_proxy}"
                    )
                    existing_sessions.append(client)
                    break
                else:
                    logger.warning(
                        f"Session for {phone} is not authorized. Removing it from the database."
                    )
                    sessions_collection.delete_one({"phone": phone})
                    await client.disconnect()
                    break
            except Exception as e:
                logger.warning(
                    f"Proxy issue for session {phone}: {formatted_proxy}. Retrying... ({retry + 1}/5)"
                )
    return existing_sessions


async def login(phone, proxy=None):
    """Login function with MTProto proxy support."""
    try:
        formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])  # (host, port, secret)

        client = TelegramClient(
            f'session_{phone}',
            API_ID,
            API_HASH,
            connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=formatted_proxy,
        )
        await client.connect()

        if not await client.is_user_authorized():
            console.print(f"Account [bold]{phone}[/bold] is not authorized. Logging in...", style="bold blue")
            await client.send_code_request(phone)
            otp = Prompt.ask(f"Enter the OTP for [bold]{phone}[/bold]")
            await client.sign_in(phone, otp)

            # Handle 2FA if enabled
            if not await client.is_user_authorized():
                password = Prompt.ask(f"Enter the 2FA password for [bold]{phone}[/bold]", password=True)
                await client.sign_in(password=password)

            # Save the session string to MongoDB
            session_string = StringSession.save(client.session)
            sessions_collection.update_one(
                {"phone": phone},
                {"$set": {"session_string": session_string}},
                upsert=True,
            )
            console.print(f"Session saved for account [bold]{phone}[/bold].", style="bold green")
        else:
            console.print(f"Account [bold]{phone}[/bold] is already authorized.", style="bold green")

        return client

    except Exception as e:
        console.print(f"Error during login for account [bold]{phone}[/bold]: {str(e)}", style="bold red")
        return None


async def assign_proxies_to_new_sessions(proxies, accounts_needed):
    """Log in to new accounts using MTProto proxies."""
    new_sessions = []
    for i in range(accounts_needed):
        phone = Prompt.ask(f"Enter the phone number for account [bold]{i + 1}[/bold]")
        proxy = None if not proxies else proxies[i % len(proxies)]
        formatted_proxy = None if not proxy else (proxy[0], int(proxy[1]), proxy[2])  # (host, port, secret)

        client = await login(phone, proxy=proxy)
        if client:
            console.print(f"[✓] Logged in to new account [bold]{phone}[/bold] using MTProto Proxy: {formatted_proxy}", style="bold green")
            new_sessions.append(client)
    return new_sessions


async def report_entity(client, entity, reason, times_to_report):
    """Report an entity with improved error handling and logging."""
    try:
        if reason not in REPORT_REASONS:
            console.print(f"Invalid report reason: {reason}", style="bold red")
            return 0

        entity_peer = await client.get_input_entity(entity)
        message = f"Reported for {reason}."
        successful_reports = 0

        with Progress() as progress:
            task = progress.add_task(f"[cyan]Reporting {entity}...", total=times_to_report)
            for _ in range(times_to_report):
                try:
                    result = await client(ReportPeerRequest(entity_peer, REPORT_REASONS[reason], message))
                    if result:
                        successful_reports += 1
                        progress.update(task, advance=1, description=f"[green]Reported {entity} for {reason}.")
                    else:
                        progress.update(task, description=f"[yellow]Failed to report {entity}.")
                except Exception as e:
                    progress.update(task, description=f"[red]Error during report attempt for {entity}: {str(e)}")

        return successful_reports

    except Exception as e:
        console.print(f"Failed to report {entity}: {str(e)}", style="bold red")
        return 0


async def main():
    console.print(Panel.fit("=== Telegram Multi-Account Reporting Tool ===", style="bold blue"))
    console.print("This tool helps you report entities using multiple Telegram accounts.\n", style="bold cyan")

    account_count = IntPrompt.ask("Enter the number of accounts to use for reporting", default=1)
    proxies = load_proxies()

    session_docs = list(sessions_collection.find())
    existing_count = len(session_docs)

    if existing_count >= account_count:
        console.print(f"\n[✓] There are {account_count} existing sessions. No new accounts required.", style="bold green")
        clients = await connect_existing_sessions(proxies, account_count)
    else:
        console.print(f"\n[✓] {existing_count} sessions found in the database.", style="bold green")
        new_accounts_needed = account_count - existing_count
        console.print(f"[!] Please log in to {new_accounts_needed} new accounts.", style="bold yellow")
        existing_clients = await connect_existing_sessions(proxies, existing_count)
        new_clients = await assign_proxies_to_new_sessions(proxies, new_accounts_needed)
        clients = existing_clients + new_clients

    console.print("\nSelect the type of entity to report:", style="bold blue")
    console.print("1 - Group\n2 - Channel\n3 - User", style="bold cyan")
    choice = IntPrompt.ask("Enter your choice (1/2/3)", choices=["1", "2", "3"])
    entity = Prompt.ask("Enter the group/channel username or user ID to report").strip()

    console.print("\nAvailable reasons for reporting:", style="bold blue")
    for idx, reason in enumerate(REPORT_REASONS.keys(), 1):
        console.print(f"{idx} - {reason.capitalize()}", style="bold cyan")
    reason_choice = IntPrompt.ask("Enter your choice", choices=[str(i) for i in range(1, len(REPORT_REASONS) + 1)])
    reason = list(REPORT_REASONS.keys())[reason_choice - 1]

    times_to_report = IntPrompt.ask("Enter the number of times to report", default=1)
    total_successful_reports = 0

    for client in clients:
        successful_reports = await report_entity(client, entity, reason, times_to_report)
        total_successful_reports += successful_reports

    console.print(f"\n[✓] Total successful reports submitted: {total_successful_reports}", style="bold green")

    for client in clients:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
