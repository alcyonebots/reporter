from telethon import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonOther
)
import asyncio

async def main():
    # Initialize client with string session
    print("=== Telegram Message Reporter ===")
    string_session = input("Enter your Telethon string session: ")
    api_id = int(input("Enter your API ID: "))
    api_hash = input("Enter your API Hash: ")

    # Create client using the string session
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()

    # Get target chat/channel
    target = input("\nEnter username/ID of group/channel (e.g., 'mygroup' or -100123456789): ")
    try:
        entity = await client.get_entity(target)
    except Exception as e:
        print(f"Error finding entity: {e}")
        return

    # Get message ID
    try:
        msg_id = int(input("\nEnter the message ID to report: "))
    except ValueError:
        print("Invalid message ID! Must be a number.")
        return

    # Select reason
    print("\nSelect report reason:")
    print("1. Spam")
    print("2. Violence")
    print("3. Pornography")
    print("4. Child Abuse")
    print("5. Other")
    
    reason_choice = input("Enter choice (1-5): ")
    reason_map = {
        '1': InputReportReasonSpam(),
        '2': InputReportReasonViolence(),
        '3': InputReportReasonPornography(),
        '4': InputReportReasonChildAbuse(),
        '5': InputReportReasonOther()
    }
    
    reason = reason_map.get(reason_choice)
    if not reason:
        print("Invalid reason selection!")
        return

    # Get report count
    try:
        report_count = int(input("\nHow many times to report? (1-10 recommended): "))
        if report_count < 1 or report_count > 100:
            print("Please enter between 1-100 reports")
            return
    except ValueError:
        print("Invalid number!")
        return

    # Confirm
    confirm = input(f"\nWARNING: You're about to report message {msg_id} in {entity.title} {report_count} times as {type(reason).__name__}. Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted!")
        return

    # Perform reporting
    print("\nReporting...")
    for i in range(report_count):
        try:
            await client(ReportRequest(
                peer=entity,
                id=[msg_id],  # Must be list even for single message
                reason=reason,
                message="illegal"
            ))
            print(f"Report #{i+1} sent successfully")
            await asyncio.sleep(1)  # Add small delay between requests
        except Exception as e:
            print(f"Error in report #{i+1}: {str(e)}")
    
    print("\nReporting process completed!")

if __name__ == "__main__":
    asyncio.run(main())
