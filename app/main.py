import os
import telebot
from dotenv import load_dotenv
from .handlers.start import start_handler
from .handlers.notes import notes_handler
from .handlers.files import files_handler
from .handlers.groups import groups_handler
from .handlers.activate import activation_handler
from .handlers.admin import admin_handler

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot with timeout and request kwargs
bot = telebot.TeleBot(
    TOKEN,
    parse_mode="Markdown",
    threaded=False
)

# Request timeout configuration
telebot.apihelper.SESSION_TIMEOUT = 30
telebot.apihelper.API_REQUEST_TIMEOUT = 30

# Register handlers
start_handler(bot)
activation_handler(bot)
notes_handler(bot)
groups_handler(bot)
files_handler(bot)
admin_handler(bot)

# print("Bot is running...")
# # Use infinity_polling with allowed_updates and request_kwargs to handle timeouts
# bot.infinity_polling(timeout=30, long_polling_timeout=30)