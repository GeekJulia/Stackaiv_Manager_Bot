import os
import logging
import hmac
import hashlib
import telebot
from flask import Flask, request, jsonify
from dotenv import load_dotenv
# testing production1
load_dotenv()

app = Flask(__name__)

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Connect to gunicorn logger
gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(logging.INFO)

# ✅ ADD ERROR HANDLING FOR BOT IMPORT
try:
    from .main import bot
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to import bot from main: {e}", exc_info=True)
    bot = None  # Set to None so we can check later

from .services.payments import handle_payment_webhook
from .database.queries import get_user_program_id
from .database.queries import conn as db_conn

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# -------------------------
# VERIFY PAYSTACK WEBHOOK
# -------------------------
def verify_paystack_webhook(request_data, signature):
    """
    Verify that the webhook is genuinely from Paystack
    """
    try:
        secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        
        # Paystack sends signature in X-Paystack-Signature header
        if not signature:
            logger.warning("Missing Paystack signature")
            return False
        
        if not secret_key:
            logger.warning("Paystack secret key not configured")
            return False
        
        # Create hash using SECRET_KEY
        hash_object = hmac.new(
            secret_key.encode(),
            msg=request_data,
            digestmod=hashlib.sha512
        )
        
        computed_signature = hash_object.hexdigest()
        
        # Verify signature matches
        return hmac.compare_digest(computed_signature, signature)
    
    except Exception as e:
        logger.error(f"Webhook verification error: {str(e)}")
        return False

# -------------------------
# PAYSTACK WEBHOOK ENDPOINT
# -------------------------
@app.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():
    """
    Webhook endpoint for Paystack to send payment notifications
    
    Paystack will POST to this endpoint when:
    - Payment is successful (charge.success event)
    - Payment fails
    - Payment is abandoned
    """
    try:
        # Get signature from header
        signature = request.headers.get("X-Paystack-Signature")
        
        # Get raw request data for signature verification
        request_data = request.get_data()
        
        # Verify webhook is from Paystack
        if not verify_paystack_webhook(request_data, signature):
            logger.warning("Invalid Paystack webhook signature")
            return jsonify({"status": "error", "message": "Invalid signature"}), 401
        
        # Parse JSON
        data = request.get_json()
        event = data.get("event")
        logger.info(f"Paystack webhook received: {event}")
        
        # Extract reference from webhook data
        webhook_reference = data.get("data", {}).get("reference")
        webhook_amount = data.get("data", {}).get("amount")
        logger.info(f"Webhook details: reference={webhook_reference}, amount={webhook_amount}")
        
        # Handle successful charge
        if event == "charge.success":
            result = handle_payment_webhook(data)
            
            if result.get("status") and result.get("activated"):
                logger.info(f"Program {result['program_id']} activated successfully")
                return jsonify({"status": "success", "message": "Payment verified and program activated"}), 200
            else:
                logger.error(f"Payment verification failed: {result.get('error')}")
                return jsonify({"status": "error", "message": result.get("error")}), 400
        
        # Other events (failures, abandonments) can be logged but not processed
        elif event in ["charge.failure", "charge.abandon"]:
            logger.info(f"Payment {event}: {data}")
            return jsonify({"status": "info", "message": f"Event {event} logged"}), 200
        
        else:
            logger.warning(f"Unhandled webhook event: {event}")
            return jsonify({"status": "info", "message": "Event logged"}), 200
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# -------------------------
# HEALTH CHECK ENDPOINT
# -------------------------
@app.route("/paystack/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "paystack-webhook"}), 200


@app.route("/telegram/health", methods=["GET"])
def telegram_health():
    """
    Health check for Telegram bot and database.
    
    Returns:
      - 200 OK if bot is initialized and DB is reachable
      - 503 if either bot or DB is not healthy
    """
    health = {
        "service": "telegram-bot",
        "bot_initialized": False,
        "db_connected": False,
    }

    # Check bot object
    if bot is None:
        logger.error("Telegram health check: bot is not initialized (bot is None).")
        return jsonify({**health, "status": "error", "reason": "bot_uninitialized"}), 503
    health["bot_initialized"] = True

    # Check DB connection with a very light query
    try:
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
        health["db_connected"] = True
    except Exception as e:
        logger.error(f"Telegram health check: DB connectivity failed: {e}", exc_info=True)
        return jsonify({**health, "status": "error", "reason": "db_unreachable"}), 503

    return jsonify({**health, "status": "ok"}), 200

@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    try:
        if bot is None:
            logger.error("Telegram webhook received update but bot is not initialized (bot is None).")
            return jsonify({"status": "error", "message": "bot_not_initialized"}), 503

        update = telebot.types.Update.de_json(request.json)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# -------------------------
# ERROR HANDLERS
# -------------------------
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    # This only runs during local development with `python -m app.webhook`
    port = int(os.getenv("WEBHOOK_PORT", 5000))
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    
    print(f"Paystack webhook server running on {host}:{port}")
    app.run(host=host, port=port, debug=False)