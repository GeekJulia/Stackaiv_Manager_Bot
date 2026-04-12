import os
import logging
import hmac
import hashlib
import telebot
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# testing production12
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

from .utils.messages import escape_html

#  ADD ERROR HANDLING FOR BOT IMPORT
try:
    from .main import bot
except Exception as e:
    logger.error(f" CRITICAL: Failed to import bot from main: {e}", exc_info=True)
    bot = None  # Set to None so we can check later

from .services.payments import handle_payment_webhook
from .database.queries import get_user_program_id, get_payment_by_reference, get_program_info
from .database.clients import pool
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


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


def extract_user_id_from_reference(reference):
    """Parse telegram user_id out of a payment reference string.
    
    Reference format: STK_{type}_U{user_id}[_P{program_id}]_{ts}_{rand}
    Walks each underscore-separated part and returns the first one that
    starts with 'U' and has a purely numeric suffix.
    """
    if not reference:
        return None
    try:
        for part in reference.split('_'):
            if part.startswith('U') and part[1:].isdigit():
                return int(part[1:])
    except Exception:
        pass
    return None

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
            fulfillment = handle_payment_webhook(data)
            
            if fulfillment.get("status"):
                ftype = fulfillment.get("type")
                if ftype == "hub_activation":
                    program_id   = fulfillment['program_id']
                    program_name = fulfillment.get('program_name', 'Your Program')
                    notify_users = fulfillment.get('notify_users', [])
                    logger.info(f"Program {program_id} activated. Notifying {len(notify_users)} user(s).")

                    if bot:
                        kb = InlineKeyboardMarkup()
                        kb.add(InlineKeyboardButton("Enter Hub →", callback_data="hub:enter_own"))
                        for tg_id in notify_users:
                            try:
                                bot.send_message(
                                    tg_id,
                                    f"✅ <b>Hub Activated!</b>\n\n"
                                    f"Your <b>{escape_html(program_name)}</b> Hub is now live!\n"
                                    "You and your coursemates now have full access.\n\n"
                                    "Tap below to enter your Hub.",
                                    parse_mode="HTML",
                                    reply_markup=kb
                                )
                            except Exception as notify_err:
                                logger.warning(f"Could not notify user {tg_id}: {notify_err}")

                    return jsonify({"status": "success", "message": "Hub activated"}), 200

                elif ftype == "archive_access":
                    user_id = fulfillment.get("user_id")
                    target_name = fulfillment.get("target_name", "your requested resources")
                    logger.info(f"Archive access granted for User {user_id}: {target_name}")

                    if bot and user_id:
                        kb = InlineKeyboardMarkup()
                        kb.add(InlineKeyboardButton("🗄 Go to Archives", callback_data="hub:archives"))
                        try:
                            bot.send_message(
                                user_id,
                                f"✅ <b>Access Granted!</b>\n\n"
                                f"Your payment to unlock <b>{escape_html(target_name)}</b> has been verified.\n"
                                "You can now access these resources in your Academic Vault.",
                                parse_mode="HTML",
                                reply_markup=kb
                            )
                        except Exception as notify_err:
                            logger.warning(f"Could not notify user {user_id} of archive success: {notify_err}")

                    return jsonify({"status": "success", "message": "Archive access granted"}), 200
                else:
                    return jsonify({"status": "success", "message": "Payment processed"}), 200
            else:
                logger.error(f"Payment verification failed: {fulfillment.get('error')}")
                return jsonify({"status": "error", "message": fulfillment.get("error")}), 400
        
        # Notify user on failed or abandoned payments
        elif event in ["charge.failure", "charge.abandon"]:
            reference = data.get("data", {}).get("reference", "")
            logger.info(f"Payment {event} for reference={reference}")

            if bot and reference:
                # Attempt to identify who initiated this payment
                tg_id = None
                program_name = None
                try:
                    payment_record = get_payment_by_reference(reference)
                    if payment_record:
                        # Try metadata first (most reliable)
                        tg_id = payment_record.get('metadata', {}).get('user_id')
                        # Fallback: parse from reference string
                        if not tg_id:
                            tg_id = extract_user_id_from_reference(reference)
                        # Get program name for a helpful message
                        prog_id = payment_record.get('program_id')
                        if prog_id:
                            prog = get_program_info(prog_id)
                            program_name = prog['program_name'] if prog else None
                    else:
                        tg_id = extract_user_id_from_reference(reference)
                except Exception as lookup_err:
                    logger.warning(f"Could not look up payment for failure notify: {lookup_err}")
                    tg_id = extract_user_id_from_reference(reference)

                if tg_id:
                    try:
                        if event == "charge.failure":
                            bot.send_message(
                                tg_id,
                                f"❌ <b>Payment Failed</b>\n\n"
                                f"Your payment{' for <b>' + escape_html(program_name) + '</b>' if program_name else ''} "
                                "could not be processed.\n\n"
                                "Please try again. If the problem persists, contact your bank or reach out to support.",
                                parse_mode="HTML"
                            )
                        else:  # charge.abandon
                            bot.send_message(
                                tg_id,
                                f"⚠️ <b>Payment Not Completed</b>\n\n"
                                f"Your Hub activation payment{' for <b>' + escape_html(program_name) + '</b>' if program_name else ''} "
                                "was not completed.\n\n"
                                "Your slot is still reserved. You can activate anytime by using /start → Activate Hub.",
                                parse_mode="HTML"
                            )
                    except Exception as notify_err:
                        logger.warning(f"Could not send failure notice to {tg_id}: {notify_err}")

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

    if bot is None:
        return jsonify({**health, "status": "error", "reason": "bot_uninitialized"}), 503

    health["bot_initialized"] = True

    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
        health["db_connected"] = True
    except Exception:
        logger.error("DB health check failed", exc_info=True)
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