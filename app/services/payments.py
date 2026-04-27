import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from ..database.queries import (
    save_payment, 
    get_payment_by_reference, 
    activate_program,
    save_archive_subscription,
    get_users_by_program_id,
    get_program_info,
    get_course_info
)

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

PAYSTACK_BASE_URL = "https://api.paystack.co"

# -------------------------
# PAYSTACK API FUNCTIONS
# -------------------------

def initialize_transaction(email, amount, reference, payment_type='hub_activation', program_id=None, target_id=None, target_level=None, telegram_id=None):
    """
    Initialize a Paystack transaction with dynamic metadata for fulfillment.
    
    Args:
        email: User email (required by Paystack)
        amount: Amount in Naira
        reference: Unique reference
        payment_type: 'hub_activation' or 'archive_access'
        program_id: Associated program (optional for archive)
        target_id: course_id if type is course archive
        target_level: level string if type is level archive
        telegram_id: Telegram user ID of the paying user (stored in metadata for failure notifications)
    """
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    
    if not secret_key:
        return {"status": False, "error": "Paystack secret key not configured."}

    url = f"{PAYSTACK_BASE_URL}/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {secret_key.strip()}",
        "Content-Type": "application/json",
    }
    
    # Bundle metadata for the webhook — include telegram_id so we can notify on
    # failure/success even if Paystack strips all other metadata from a response
    metadata = {
        "payment_type": payment_type,
        "program_id": program_id,
        "target_id": target_id,
        "target_level": target_level,
        "user_id": telegram_id,
    }
    
    payload = {
        "email": email,
        "amount": int(amount) * 100, # Kobo
        "reference": reference,
        "currency": "NGN",
        "metadata": metadata,
        "channels": ["card", "bank", "bank_transfer"]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status"):
            # Save internal payment record
            save_payment(
                program_id=program_id,
                reference=reference,
                amount=amount,
                status="pending",
                payment_type=payment_type,
                metadata=metadata
            )
            
            return {
                "status": True,
                "authorization_url": data["data"]["authorization_url"],
                "reference": reference
            }
        else:
            return {"status": False, "error": data.get("message", "Initialization failed")}
    except Exception as e:
        return {"status": False, "error": str(e)}

def handle_payment_webhook(data):
    """
    Dispatch fulfillment based on payment metadata.
    """
    try:
        tx_data = data.get("data", {})
        reference = tx_data.get("reference")
        amount_kobo = tx_data.get("amount")
        metadata = tx_data.get("metadata", {})
        
        if not reference:
            return {"status": False, "error": "No reference"}

        # Get metadata from Paystack or fallback to local DB if Paystack stripped it
        payment_type = metadata.get("payment_type")
        program_id = metadata.get("program_id")
        
        # Verify internally
        payment = get_payment_by_reference(reference)
        if not payment:
            return {"status": False, "error": "Payment record missing"}
        
        # Update status to success
        save_payment(
            program_id=payment.get('program_id'),
            reference=reference,
            amount=payment['amount'],
            status="success"
        )

        # FULFILLMENT DISPATCH
        if payment_type == 'hub_activation' or payment.get('payment_type') == 'hub_activation':
            # Activate Program Hub (₦3000)
            target_prog_id = program_id or payment.get('program_id')
            activate_program(target_prog_id)

            # Collect all linked users so webhook.py can notify them
            notify_users = get_users_by_program_id(target_prog_id)
            program = get_program_info(target_prog_id)
            program_name = program['program_name'] if program else "Your Program"

            return {
                "status": True,
                "type": "hub_activation",
                "program_id": target_prog_id,
                "notify_users": notify_users,
                "program_name": program_name,
            }
            
        elif payment_type == 'archive_access' or payment.get('payment_type') == 'archive_access':
            # Academic Vault Access (₦500 / ₦3000 / ₦10000)
            user_id = metadata.get("user_id") or payment.get('metadata', {}).get('user_id')
            
            # Fallback user_id extraction: usually part of the reference for us
            try:
                if not user_id:
                    user_id = int(reference.split('_')[2][1:]) # Updated to match STK_ARC_U123 format
            except: pass

            target_id = metadata.get('target_id')
            target_level = metadata.get('target_level')
            access_type = 'course' if target_id else ('level' if (target_level and target_level != 'FULL_VAULT') else 'full')
            
            # Get a readable name for the success message
            target_name = "Full Vault Access"
            if access_type == 'course':
                course = get_course_info(target_id)
                target_name = course['course_code'] if course else f"Course ID {target_id}"
            elif access_type == 'level':
                target_name = target_level

            save_archive_subscription(
                user_id=user_id,
                access_type=access_type,
                target_id=target_id,
                target_level=target_level,
                reference=reference
            )
            return {
                "status": True, 
                "type": "archive_access", 
                "user_id": user_id,
                "target_name": target_name
            }

        return {"status": False, "error": "Unknown payment type"}
        
    except Exception as e:
        return {"status": False, "error": f"Fulfillment error: {str(e)}"}

def verify_transaction(reference):
    """
    Manually verify a Paystack transaction by its reference.
    Useful for polling or manual checks when webhooks fail.
    """
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    if not secret_key:
        return {"status": False, "error": "Paystack secret key not configured."}

    url = f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {secret_key.strip()}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") and data.get("data", {}).get("status") == "success":
            return {"status": True, "data": data["data"]}
        else:
            return {"status": False, "error": data.get("message", "Verification failed")}
    except Exception as e:
        return {"status": False, "error": str(e)}

def generate_payment_reference(user_id, program_id=None, ptype='ACT'):
    """Generate a unique payment reference"""
    import time
    import uuid
    ts = int(time.time())
    rand = uuid.uuid4().hex[:4].upper()
    prog_part = f"_P{program_id}" if program_id else ""
    return f"STK_{ptype}_U{user_id}{prog_part}_{ts}_{rand}"
