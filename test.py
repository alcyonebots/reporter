from telethon import TelegramClient, functions
from telethon.sessions import StringSession

# Replace these with your actual values
api_id = 29872536        # e.g., 123456
api_hash = '65e1f714a47c0879734553dc460e98d6'  # e.g., '0123456789abcdef0123456789abcdef'

# Prompt for required data
string_session = input("Enter your Telethon string session: ")
group_identifier = input("Enter the group username or ID: ")
message_id_input = input("Enter the message ID to report: ")

try:
    message_id = int(message_id_input)
except ValueError:
    print("Invalid message ID. It must be an integer.")
    exit(1)

client = TelegramClient(StringSession(string_session), api_id, api_hash)

async def report_message():
    try:
        # Retrieve the group entity
        group = await client.get_entity(group_identifier)
        
        # Create the ReportSpamRequest with only the peer argument
        req = functions.messages.ReportSpamRequest(group)
        # Manually set the 'id' attribute (a list of message IDs)
        req.id = [message_id]
        
        # Send the request
        await client(req)
        print("Message reported successfully.")
    except Exception as e:
        print("An error occurred:", e)

with client:
    client.loop.run_until_complete(report_message())
