from pyrogram import idle
from bot import bot, user

print("Starting user client...")
user.start()

print("Starting bot client...")
bot.start()

print("Hybrid bot is running.")

idle()

bot.stop()
user.stop()