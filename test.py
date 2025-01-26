from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import InputPhoneContact
from telethon.network.proxy import MTProtoProxy
import os

# Replace with your proxy settings
proxy = MTProtoProxy(
    addr='rakadron.komperiistaionnop.info',  # Proxy address
    port=443,  # Proxy port
    secret=b'ee151151151151151151151151151151152D2D2D2D2D2D7765622E61707063656E7465722E6D73692D2D2D2D2D2Da'  # Proxy secret (should be bytes)
)

# Set your api_id and api_hash from Telegram
api_id = '29872536'
api_hash = '65e1f714a47c0879734553dc460e98d6'

# Define the phone number and initiate the login
async def main():
    phone_number = input("Enter your phone number (with country code): ")

    # Create a new Telethon client with MTProtoProxy
    client = TelegramClient(StringSession(), api_id, api_hash, proxy=proxy)

    # Start the client
    await client.start(phone_number)

    try:
        # Check if 2FA is enabled, prompt for password if needed
        if await client.is_user_authorized():
            print("Logged in successfully!")
        else:
            print("Two-factor authentication required.")
            await client.send_code_request(phone_number)
            otp = input("Enter the OTP: ")
            await client.sign_in(phone_number, otp)
            print("Logged in successfully!")

    except SessionPasswordNeededError:
        password = input("Enter your password for 2FA: ")
        await client.start(password=password)
        print("Logged in successfully!")

    # Use the client as needed, for example:
    me = await client.get_me()
    print(f"Logged in as: {me.username}")

    # Remember to disconnect after you're done
    await client.disconnect()

# Run the event loop
import asyncio
asyncio.run(main())
