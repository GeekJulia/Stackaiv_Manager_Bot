import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from ..database.queries import save_payment, get_payment_by_reference, activate_program

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

PAYSTACK_BASE_URL = "https://api.paystack.co"
ACTIVATION_FEE = 3000

# -------------------------
# PAYSTACK API FUNCTIONS
# -------------------------

def initialize_transaction(program_id, email, reference):
    # Ensure the secret key is loaded - reload from environment
    load_dotenv()  # Force reload of .env file
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    
    if not secret_key or secret_key.strip() == "":
        return {
            "status": False,
            "error": "Paystack secret key not configured. Please check your .env file."
        }
    
    # Strip any whitespace from secret key
    secret_key = secret_key.strip()

    url = f"{PAYSTACK_BASE_URL}/transaction/initialize"
    
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "email": email,
        "amount": ACTIVATION_FEE * 100,
        "reference": reference,
        "currency": "NGN",
        "channels": ["card", "bank", "bank_transfer"]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status"):
            # Save payment record with pending status
            save_payment(
                program_id=program_id,
                reference=reference,
                amount=ACTIVATION_FEE,
                status="pending"
            )
            
            return {
                "status": True,
                "authorization_url": data["data"]["authorization_url"],
                "access_code": data["data"]["access_code"],
                "reference": data["data"]["reference"]
            }
        else:
            error_msg = data.get("message", "Unknown error")
            return {"status": False, "error": error_msg}
    
    except requests.exceptions.RequestException as e:
        return {"status": False, "error": f"Payment initialization failed: {str(e)}"}

def verify_transaction(reference):
    """
    Verify a Paystack transaction
    Returns: {status: bool, verified: bool, data: dict}
    """
    secret_key = os.getenv("PAYSTACK_SECRET_KEY") or PAYSTACK_SECRET_KEY
    
    if not secret_key:
        return {
            "status": False,
            "verified": False,
            "error": "Paystack secret key not configured."
        }
    
    url = f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status"):
            transaction_data = data.get("data", {})
            
            # Check if payment was successful and amount matches
            is_verified = (
                transaction_data.get("status") == "success" and
                transaction_data.get("amount") == ACTIVATION_FEE
            )
            
            return {
                "status": True,
                "verified": is_verified,
                "data": transaction_data
            }
        else:
            return {"status": False, "verified": False, "error": data.get("message", "Unknown error")}
    
    except requests.exceptions.RequestException as e:
        return {"status": False, "verified": False, "error": f"Verification failed: {str(e)}"}

def handle_payment_webhook(data):
    """
    Handle Paystack webhook (charge.success event)
    data = request.json from Paystack
    Returns: {status: bool, program_id: int, activated: bool}
    """
    try:
        reference = data.get("data", {}).get("reference")
        amount = data.get("data", {}).get("amount")  # Amount in kobo (1/100 of naira)
        
        # Debug logging
        print(f"DEBUG Webhook: reference={reference}, amount={amount}, expected_amount_kobo={ACTIVATION_FEE * 100}")
        
        if not reference:
            return {"status": False, "error": "Invalid reference"}
        
        # Paystack sends amount in kobo, convert to compare with ACTIVATION_FEE (in naira)
        # 1 naira = 100 kobo, so ACTIVATION_FEE * 100 should match webhook amount
        expected_amount_kobo = ACTIVATION_FEE * 100
        if amount != expected_amount_kobo:
            return {"status": False, "error": f"Invalid amount: got {amount}, expected {expected_amount_kobo}"}
        
        # Get payment record
        payment = get_payment_by_reference(reference)
        if not payment:
            return {"status": False, "error": f"Payment record not found for reference: {reference}"}
        
        program_id = payment["program_id"]
        
        # Update payment status to success
        save_payment(
            program_id=program_id,
            reference=reference,
            amount=ACTIVATION_FEE,  # Store in naira
            status="success"
        )
        
        # Activate program
        activate_program(program_id)
        
        return {
            "status": True,
            "program_id": program_id,
            "activated": True
        }
    
    except Exception as e:
        return {"status": False, "error": f"Webhook processing failed: {str(e)}"}

def generate_payment_reference(user_id, program_id):
    """Generate a unique payment reference for Paystack"""
    import time
    timestamp = int(time.time())
    reference = f"STACKAIV_U{user_id}_P{program_id}_{timestamp}"
    return reference
