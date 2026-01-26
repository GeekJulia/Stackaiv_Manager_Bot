import os
import telebot
from dotenv import load_dotenv
from handlers.start import start_handler

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

# Register handlers
start_handler(bot)

print("Bot is running...")
bot.infinity_polling()