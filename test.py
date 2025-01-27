from telethon import TelegramClient, connection
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

# Replace these values with your actual API ID and hash
api_id = '29872536'
api_hash = '65e1f714a47c0879734553dc460e98d6'

# Replace these with your MTProto proxy details
proxy_host = 'rakadron.komperiistaionnop.info'
proxy_port = 443
proxy_secret = 'ee151151151151151151151151151151152D2D2D2D2D2D7765622E61707063656E7465722E6D73692D2D2D2D2D2Da'

# Define the phone number and initiate the login
async def main():
    phone_number = input("Enter your phone number (with country code): ")

    # Create a new TelegramClient with MTProto proxy
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=(proxy_host, proxy_port, proxy_secret)
    )

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
