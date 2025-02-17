from telethon import TelegramClient, functions
from telethon.sessions import StringSession

# Replace these with your actual api_id and api_hash
api_id = 29872536        # e.g., 123456
api_hash = '65e1f714a47c0879734553dc460e98d6'  # e.g., '0123456789abcdef0123456789abcdef'

# Prompt for necessary information
string_session = input("Enter your Telethon string session: ")
group_identifier = input("Enter the group username or ID: ")
message_id_input = input("Enter the message ID to report: ")

# Validate and convert message ID to integer
try:
    message_id = int(message_id_input)
except ValueError:
    print("Invalid message ID. It must be an integer.")
    exit(1)

# Initialize the Telegram client with the provided string session
client = TelegramClient(StringSession(string_session), api_id, api_hash)

async def report_message():
    try:
        # Retrieve the group entity based on the provided username/ID
        group = await client.get_entity(group_identifier)
        
        # Report the message as spam (the only available report type via the API)
        await client(functions.messages.ReportSpamRequest(
            peer=group,
            id=[message_id]
        ))
        print("Message reported successfully.")
    except Exception as e:
        print("An error occurred:", e)

# Run the asynchronous function within the client's event loop
with client:
    client.loop.run_until_complete(report_message())
