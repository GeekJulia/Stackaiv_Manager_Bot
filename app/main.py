import os
import logging
import telebot
from dotenv import load_dotenv

# Set up logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    logger.error("❌ CRITICAL: BOT_TOKEN not found in environment!")
    raise ValueError("BOT_TOKEN is required")

logger.info(f"Initializing bot with token: {TOKEN[:10]}...")

# Initialize bot
bot = telebot.TeleBot(
    TOKEN,
    parse_mode="Markdown",
    threaded=False
)

# Request timeout configuration
telebot.apihelper.SESSION_TIMEOUT = 30
telebot.apihelper.API_REQUEST_TIMEOUT = 30

# ✅ REGISTER HANDLERS WITH ERROR HANDLING
try:
    logger.info("Registering start_handler...")
    from .handlers.start import start_handler
    start_handler(bot)
    logger.info(f"✅ start_handler registered. Handlers: {len(bot.message_handlers)}")
except Exception as e:
    logger.error(f"❌ Failed to register start_handler: {e}", exc_info=True)

try:
    logger.info("Registering activation_handler...")
    from .handlers.activate import activation_handler
    activation_handler(bot)
    logger.info(f"✅ activation_handler registered")
except Exception as e:
    logger.error(f"❌ Failed to register activation_handler: {e}", exc_info=True)

try:
    logger.info("Registering notes_handler...")
    from .handlers.notes import notes_handler
    notes_handler(bot)
    logger.info(f"✅ notes_handler registered")
except Exception as e:
    logger.error(f"❌ Failed to register notes_handler: {e}", exc_info=True)

try:
    logger.info("Registering groups_handler...")
    from .handlers.groups import groups_handler
    groups_handler(bot)
    logger.info(f"✅ groups_handler registered")
except Exception as e:
    logger.error(f"❌ Failed to register groups_handler: {e}", exc_info=True)

try:
    logger.info("Registering files_handler...")
    from .handlers.files import files_handler
    files_handler(bot)
    logger.info(f"✅ files_handler registered")
except Exception as e:
    logger.error(f"❌ Failed to register files_handler: {e}", exc_info=True)

try:
    logger.info("Registering admin_handler...")
    from .handlers.admin import admin_handler
    admin_handler(bot)
    logger.info(f"✅ admin_handler registered")
except Exception as e:
    logger.error(f"❌ Failed to register admin_handler: {e}", exc_info=True)

logger.info(f"🎉 Bot initialization complete!")
logger.info(f"Total message handlers: {len(bot.message_handlers)}")
logger.info(f"Total callback handlers: {len(bot.callback_query_handlers)}")