import asyncio
from telegram import Bot

bot_token = "8428812998:AAHdD1FgG6fDEhq_QfNmvtA9jlRuc8xRp6A"
bot = Bot(token=bot_token)

async def test_job():
    print("Fetching recent bot updates to resolve Chat ID...")
    try:
        updates = await bot.get_updates(timeout=5)
    except Exception as e:
        print(f"Error connecting to Telegram: {e}")
        return
        
    if not updates:
        print("No messages found in the bot's history.")
        print("Please send a quick 'Hello' message to your bot in Telegram and run this again!")
        return
    
    last_update = updates[-1]
    if not last_update.message:
        print("Latest update isn't a direct message.")
        return

    chat_id = last_update.message.chat_id
    first_name = last_update.message.chat.first_name or "User"
    print(f"Success! Found User: {first_name} with Chat ID: {chat_id}")
    
    print("\n--- Starting customized AI Notification Flow ---")
    custom_msg = (
        f"Good morning {first_name}! 🌅\n\n"
        f"This is the HeyBoss system testing the Step 4 customizable notification hook. "
        f"You successfully completed yesterday's schedule, keep up the great work today!\n\n"
        f"(This message was constructed entirely on the backend without you needing to register on the web interface first!)"
    )
    
    print("\nDispatching customized message...")
    try:
        await bot.send_message(chat_id=chat_id, text=custom_msg)
        print("Message sent successfully and delivered to your phone!")
    except Exception as e:
        print(f"Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(test_job())
