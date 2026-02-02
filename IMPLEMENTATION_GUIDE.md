# Stackaiv Payment & Activation Implementation

## Overview

This document describes the implementation of the program activation flow with Paystack payment integration and comprehensive admin functionality for the Stackaiv Telegram bot.

## 1. Architecture Overview

### New Components

```
app/
├── handlers/
│   ├── activate.py         # Program activation & payment flow
│   ├── admin.py            # Admin control panel
│   └── start.py            # (MODIFIED) Integration with activation
├── services/
│   └── payments.py         # (MODIFIED) Paystack API integration
├── database/
│   └── queries.py          # (MODIFIED) Payment & admin queries
├── webhook.py              # Paystack webhook receiver
└── main.py                 # (MODIFIED) Handler registration
```

---

## 2. Program Activation Flow

### User Journey

```
User Registration Complete
        ↓
💳 Activate Program Button
        ↓
Show Activation Screen (₦3,000 fee)
        ↓
User Clicks: "Proceed with Payment"
        ↓
Bot Initializes Paystack Transaction
        ↓
Bot Sends Payment Link Button
        ↓
User Pays on Paystack
        ↓
Paystack Fires Webhook (charge.success)
        ↓
Webhook Verifies Payment
        ↓
Bot Activates Program
        ↓
Send Confirmation & Proceed to Add Courses
```

### Key Files

**[activate.py](app/handlers/activate.py)** - Activation Handler
- `show_activation_screen()` - Display activation UI with payment details
- `initiate_payment()` - Initialize Paystack transaction
- `cancel_activation()` - Handle cancellation
- `verify_payment_command()` - Manual verification command

---

## 3. Payment Processing

### Paystack Integration

**[payments.py](app/services/payments.py)** - Paystack Service

#### Functions

1. **`initialize_transaction(program_id, email, reference)`**
   - Calls Paystack Initialize Transaction API
   - Returns authorization URL and reference
   - Saves payment record with "pending" status
   - Amount: ₦3,000 (300,000 kobo)

2. **`verify_transaction(reference)`**
   - Calls Paystack Verify Transaction API
   - Validates: status == "success" AND amount == 300,000
   - Returns verification result

3. **`handle_payment_webhook(data)`**
   - Processes Paystack webhook payload
   - Verifies payment reference and amount
   - Updates payment status to "success"
   - Activates program in database
   - Returns activation status

4. **`generate_payment_reference(user_id, program_id)`**
   - Creates unique reference: `STACKAIV_U{user_id}_P{program_id}_{timestamp}`
   - Used for payment tracking

### Environment Variables Required

```env
# Paystack Configuration
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxx  # Your Paystack secret key
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxxxxx  # Your Paystack public key

# Webhook Configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_URL=https://yourdomain.com/paystack/webhook  # Register in Paystack dashboard
```

---

## 4. Database Changes

### New Tables

**payments** - Transaction records
```sql
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    program_id INT REFERENCES programs(id),
    reference TEXT UNIQUE,
    amount INT,
    status TEXT,  -- pending, success, failed
    created_at TIMESTAMP DEFAULT NOW()
);
```

**program_activations** - Activation records
```sql
CREATE TABLE program_activations (
    id SERIAL PRIMARY KEY,
    program_id INT REFERENCES programs(id),
    is_paid BOOLEAN DEFAULT FALSE,
    activated_at TIMESTAMP DEFAULT NOW()
);
```

### Updated Tables

**programs** - Added activation status
```sql
ALTER TABLE programs ADD COLUMN is_active BOOLEAN DEFAULT FALSE;
```

### New Database Functions

Added to [queries.py](app/database/queries.py):

- `save_payment()` - Save/update payment record
- `get_payment_by_reference()` - Fetch payment by reference
- `activate_program()` - Mark program as active
- `get_program_activation_status()` - Check if program is active
- `get_all_programs()` - List all programs (admin)
- `delete_program()` - Delete program and all related data (admin)
- `get_all_transactions()` - List all transactions (admin)
- `get_transaction_by_id()` - Fetch specific transaction (admin)
- `get_all_users()` - List all users (admin)

---

## 5. Admin Panel

### Command

```
/admin7105
```

**Security**: Only accessible by user with `ADMIN_ID` from environment

### Features

```
Admin Control Panel
├── 📊 List Transactions
│   └── Display all payment transactions in table format
│
├── 🔍 Fetch Transaction
│   └── Get details of specific transaction by ID
│
├── 🏫 All Programs
│   └── List all registered programs with creator info and status
│
├── 🗑️ Delete Program
│   ├── Prompt for Program ID
│   ├── Show confirmation with program details
│   └── Cascade delete all related data
│
├── 👥 List Users
│   └── Display all registered users
│
├── 📢 Broadcast Message
│   ├── Prompt for message content
│   ├── Show preview to confirm
│   └── Send to all users with delivery stats
│
└── 🛑 Stop Bot
    ├── Require confirmation
    └── Gracefully shutdown bot
```

### Admin File

**[admin.py](app/handlers/admin.py)** - Complete admin implementation with:
- Session management for multi-step workflows
- Inline keyboard UI for all functions
- Error handling and logging
- Message chunking for large outputs

### Setting Up Admin

```env
ADMIN_ID=123456789  # Your Telegram user ID
```

Get your Telegram ID by sending any message to [@userinfobot](https://t.me/userinfobot)

---

## 6. Webhook Server

### Paystack Webhook Verification

**[webhook.py](app/webhook.py)** - Flask webhook receiver

#### Security

- Verifies webhook signature using HMAC-SHA512
- Only processes webhooks from Paystack
- Validates payment amount matches ₦3,000

#### Endpoints

1. **`POST /paystack/webhook`**
   - Main webhook endpoint
   - Receives Paystack events (charge.success, charge.failure, charge.abandon)
   - Processes successful charges
   - Returns JSON response

2. **`GET /paystack/health`**
   - Health check endpoint
   - Returns status OK

#### Events Handled

- `charge.success` - Process payment and activate program
- `charge.failure` - Log failure (for future analytics)
- `charge.abandon` - Log abandonment (for future analytics)

### Running Webhook Server

**Separate process** from main bot:

```bash
# Terminal 1: Bot
python -m app.main

# Terminal 2: Webhook server
python -m app.webhook
```

Or use a process manager:

```bash
# Using gunicorn (install: pip install gunicorn)
gunicorn -w 1 -b 0.0.0.0:5000 app.webhook:app
```

### Paystack Configuration

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Navigate to Settings → API Keys & Webhooks
3. Set webhook URL: `https://yourdomain.com/paystack/webhook`
4. Subscribe to events: `charge.success`, `charge.failure`, `charge.abandon`

---

## 7. Updated Handler Files

### [start.py](app/handlers/start.py) - Modified

**Change**: Program registration completion now shows activation button instead of course addition

```python
# Before: Direct course addition
kb.add(InlineKeyboardButton("Add courses", callback_data="cmd:addcourses"))

# After: Activation requirement
kb.add(InlineKeyboardButton("💳 Activate Program & Continue", callback_data="action:activate_program"))
```

### [main.py](app/main.py) - Modified

Added handler registration:
```python
from .handlers.activate import activation_handler
from .handlers.admin import admin_handler

activation_handler(bot)
admin_handler(bot)
```

---

## 8. Integration with Course Registration

After program activation:

1. User completes payment → Program marked active
2. Webhook confirmation sent to bot
3. Bot sends message: "✅ Your program is activated!"
4. User can now proceed with course addition (/start or direct to notes)

### Auto-Resume Flow (Optional)

Consider storing pending state so user can continue where they left off:

```python
# In activate.py after successful payment
activation_sessions[user_id] = {
    "program_id": program_id,
    "next_step": "add_courses",
    "stage": "ready"
}
```

---

## 9. Error Handling

### Payment Failures

1. **Paystack API Error**
   - User sees: "Payment Initialization Failed"
   - Bot logs error
   - Session cleared

2. **Invalid Webhook Signature**
   - Webhook rejected with 401
   - Payment not recorded
   - User must manually verify or retry

3. **Database Error**
   - User sees: "Error: [details]"
   - Transaction logged
   - Can be retried

### Recovery Strategies

1. **Manual Verification**: `/verify_payment <reference>`
2. **Retry Payment**: `/start` → Re-register program
3. **Admin Override**: Admin can activate program manually (can be added)

---

## 10. Security Considerations

### Payment Security
✅ HMAC-SHA512 signature verification  
✅ Amount validation (must be exactly ₦3,000)  
✅ Reference uniqueness (includes user_id + program_id + timestamp)  
✅ HTTPS required for webhook URL  

### Admin Security
✅ Admin ID validation (only ADMIN_ID can access)  
✅ Confirmation prompts for destructive actions  
✅ Broadcast delivery tracking  
✅ No sensitive data in logs (remove if needed)  

### Recommendations
- ⚠️ Rotate PAYSTACK_SECRET_KEY periodically
- ⚠️ Use HTTPS for all webhook traffic
- ⚠️ Monitor webhook failures
- ⚠️ Set up bot error logging/monitoring
- ⚠️ Implement rate limiting on admin endpoints

---

## 11. Testing Checklist

### Local Testing

```bash
# 1. Test Paystack Integration
cd /app/services
python -c "from payments import generate_payment_reference; print(generate_payment_reference(123, 456))"

# 2. Test Database Queries
python -c "from database.queries import get_all_programs; print(get_all_programs())"

# 3. Run bot
python -m app.main

# 4. Run webhook (separate terminal)
python -m app.webhook
```

### Manual Testing

1. **Test Payment Flow**
   - Register new program
   - Click "Activate Program"
   - Use Paystack test card: `4111 1111 1111 1111` (expires: 12/25, CVV: 123)
   - Verify payment marked as success

2. **Test Admin Functions**
   - Send `/admin7105` command
   - Test each menu function
   - Verify transactions appear
   - Try delete program flow

3. **Test Webhook**
   - Monitor logs for webhook hits
   - Verify payment verification in database
   - Check program `is_active` status

### Using Paystack Test Mode

Paystack provides test keys for development:

```env
# Development (Test Mode)
PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxxxxx

# Production (Live Mode)
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxxxxx
```

Test cards provided by Paystack [here](https://paystack.com/docs/testing).

---

## 12. Deployment

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
# Add these if not present:
# requests==2.31.0
# flask==3.0.0
# gunicorn==21.2.0
```

### Environment Variables

```env
# .env file
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id

# Database
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=password
DB_DATABASE=stackaiv
DB_PORT=5432

# Paystack
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxx

# Webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_URL=https://yourdomain.com/paystack/webhook
```

### Systemd Service (Ubuntu/Debian)

Create `/etc/systemd/system/stackaiv-bot.service`:
```ini
[Unit]
Description=Stackaiv Telegram Bot
After=network.target

[Service]
Type=simple
User=stackaiv
WorkingDirectory=/opt/stackaiv
ExecStart=/usr/bin/python3 -m app.main
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/stackaiv-webhook.service`:
```ini
[Unit]
Description=Stackaiv Paystack Webhook
After=network.target

[Service]
Type=simple
User=stackaiv
WorkingDirectory=/opt/stackaiv
ExecStart=/usr/bin/python3 -m app.webhook
Restart=always

[Install]
WantedBy=multi-user.target
```

### Running Services

```bash
# Enable and start bot
sudo systemctl enable stackaiv-bot.service
sudo systemctl start stackaiv-bot.service

# Enable and start webhook
sudo systemctl enable stackaiv-webhook.service
sudo systemctl start stackaiv-webhook.service

# Check status
sudo systemctl status stackaiv-bot.service
sudo systemctl status stackaiv-webhook.service

# View logs
sudo journalctl -u stackaiv-bot.service -f
sudo journalctl -u stackaiv-webhook.service -f
```

### Using Nginx as Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /paystack/webhook {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 13. Troubleshooting

### Payment Not Activating

1. **Check webhook logs**
   ```bash
   sudo journalctl -u stackaiv-webhook.service -f
   ```

2. **Verify Paystack configuration**
   - Correct secret key set?
   - Webhook URL registered?
   - Correct events subscribed?

3. **Check database**
   ```sql
   SELECT * FROM payments WHERE reference = 'your_reference';
   SELECT * FROM program_activations WHERE program_id = your_id;
   ```

### Admin Command Not Responding

1. **Verify ADMIN_ID**
   ```bash
   # Check .env file
   grep ADMIN_ID .env
   ```

2. **Get your ID**
   - Send any message to [@userinfobot](https://t.me/userinfobot)
   - Copy your ID to .env

3. **Restart bot**
   ```bash
   sudo systemctl restart stackaiv-bot.service
   ```

### Webhook Signature Verification Failing

1. **Verify secret key**
   - Must use **Secret Key** not Public Key
   - Check Paystack dashboard

2. **Check raw request data**
   - Webhook body should be raw JSON
   - Not form-encoded

3. **Review logs for details**

---

## 14. Future Enhancements

- [ ] Payment history for users
- [ ] Refund functionality
- [ ] Multiple payment methods (Flutterwave, Stripe)
- [ ] Subscription plans
- [ ] Analytics dashboard
- [ ] Email receipts
- [ ] Invoice generation
- [ ] Payment retry logic
- [ ] Fallback payment verification
- [ ] Audit logging

---

## 15. Files Summary

| File | Purpose | Status |
|------|---------|--------|
| `app/handlers/activate.py` | Activation flow handler | ✅ Created |
| `app/handlers/admin.py` | Admin control panel | ✅ Created |
| `app/handlers/start.py` | Modified for activation | ✅ Modified |
| `app/services/payments.py` | Paystack API integration | ✅ Modified |
| `app/database/queries.py` | Payment/admin queries | ✅ Modified |
| `app/webhook.py` | Paystack webhook receiver | ✅ Created |
| `app/main.py` | Handler registration | ✅ Modified |

---

## 16. Support

For issues or questions:
1. Check logs
2. Review this documentation
3. Check Paystack API docs: https://paystack.com/docs/api
4. Review telebot docs: https://pypi.org/project/python-telegram-bot/

---

**Implementation Date**: January 31, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
