# Stackaiv - Academic Resource Manager Bot

Stackaiv is a comprehensive Telegram bot that manages academic resources for students organized by program, level, and course. Students register with their college and program, then share/access course materials within their program community.

##  Features

### Core Features
-  **Program Registration** - Level, College, and Program selection
-  **Course Management** - Register and manage courses
-  **Resource Sharing** - Upload and download course materials (notes, PDFs, code, etc.)
-  **Community Spaces** - Program-based Telegram groups
-  **Payment Integration** - Paystack activation fee (₦3,000)
-  **Admin Panel** - Complete management interface

### Payment & Activation (NEW)
-  **Secure Payments** - Paystack integration with webhook verification
-  **Automatic Activation** - Program activation on successful payment
-  **Transaction Tracking** - Complete payment history
-  **Admin Controls** - Manage transactions, programs, and users

### Admin Functions (NEW - `/admin7105`)
1.  List all transactions
2.  Fetch transaction details
3.  View all programs
4.  Delete programs
5.  List users
6.  Broadcast messages
7.  Stop bot

##  Quick Start

### Prerequisites
```bash
# Python 3.7+
# PostgreSQL database
# Telegram Bot Token (from @BotFather)
# Paystack Account (https://paystack.com)
```

### Installation

1. **Clone and Setup**
```bash
cd Stackaiv
pip install -r requirements.txt
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your:
# - BOT_TOKEN
# - Database credentials
# - ADMIN_ID (your Telegram ID)
# - Paystack keys
```

3. **Database Migration**
```bash
psql -U postgres -d stackaiv < scripts/init_db.sql
psql -U postgres -d stackaiv < scripts/migration_payments.sql
```

4. **Run Bot** (Terminal 1)
```bash
python -m app.main
```

Ngrok = ngrok http 5000

5. **Run Webhook** (Terminal 2)
```bash
python -m app.webhook
```

##  Documentation

### Getting Started
- [Quick Setup Guide](QUICK_SETUP.md) - 5-minute setup
- [Environment Configuration](.env.example) - Config template

### Complete Documentation
- [Implementation Guide](IMPLEMENTATION_GUIDE.md) - Full reference (16 sections)
- [Workflow Diagram](WORKFLOW_DIAGRAM.md) - Architecture & flows
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Changes overview
- [Verification Checklist](VERIFICATION_CHECKLIST.md) - Status & checklist

### Quick References
- [Index](INDEX.md) - Master index of all files
- [Database Migration](scripts/migration_payments.sql) - SQL schema

##  Payment Flow

```
User Registration
    ↓
Activate Program (₦3,000)
    ↓
Paystack Payment Link
    ↓
User Pays
    ↓
Webhook Confirmation
    ↓
Program Activated
    ↓
Add Courses & Resources
```

##  User Commands

```
/start              - Begin registration
/whoami             - Show program info
/admin7105          - Admin control panel (admin only)
/verify_payment     - Manual payment verification
```

##  Admin Commands

Send `/admin7105` to access:
-  List all transactions
-  Fetch transaction by ID
-  View all programs
-  Delete program
-  List users
-  Broadcast message
-  Stop bot

##  Architecture

### Project Structure
```
app/
├── handlers/
│   ├── start.py          - User onboarding
│   ├── notes.py          - Course registration
│   ├── files.py          - Resource hub
│   ├── groups.py         - Group management
│   ├── activate.py       - Payment & activation (NEW)
│   └── admin.py          - Admin panel (NEW)
├── services/
│   ├── payments.py       - Paystack integration (NEW)
│   └── ...
├── database/
│   └── queries.py        - Database functions (11 new)
├── webhook.py            - Paystack webhook (NEW)
└── main.py               - Bot entry point

scripts/
├── init_db.sql           - Initial schema
└── migration_payments.sql - Payment tables (NEW)
```

### Database Tables

**Core Tables**
- `users` - Telegram users
- `programs` - Academic programs
- `courses` - Courses per program
- `resources` - Shared files
- `resource_types` - File categories
- `groups` - Program group chats

**New Tables**
- `payments` - Transaction records
- `program_activations` - Activation status

##  Security Features

-  HMAC-SHA512 webhook signature verification
-  Admin ID validation
-  Payment amount validation (₦3,000)
-  Unique payment references
-  SQL injection prevention
-  Error handling & logging
-  Confirmation prompts for destructive operations

##  Testing

### Test Paystack Card
- Number: `4111 1111 1111 1111`
- Expiry: `12/25`
- CVV: `123`

### Test Amount
- ₦3,000 (exactly)

##  Tech Stack

- **Bot Framework**: python-telegram-bot 20.3
- **Backend**: Python 3.7+
- **Database**: PostgreSQL
- **API**: Paystack (Payment Gateway)
- **Webhook**: Flask
- **Deployment**: Python + Gunicorn

##  Deployment

### Development
```bash
python -m app.main      # Terminal 1
python -m app.webhook   # Terminal 2
```

### Production
```bash
# Using systemd (Linux)
sudo systemctl start stackaiv-bot.service
sudo systemctl start stackaiv-webhook.service

# Using gunicorn
gunicorn -w 1 -b 0.0.0.0:5000 app.webhook:app
```

##  Environment Variables

```env
# Telegram
BOT_TOKEN=your_telegram_bot_token

# Database
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=password
DB_DATABASE=stackaiv
DB_PORT=5432

# Admin
ADMIN_ID=your_telegram_id

# Paystack
PAYSTACK_SECRET_KEY=sk_test_xxx
PAYSTACK_PUBLIC_KEY=pk_test_xxx

# Webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_URL=https://yourdomain.com/paystack/webhook
```

##  Troubleshooting

### Common Issues

**"Admin command not responding"**
- Verify `ADMIN_ID` in .env matches your Telegram ID
- Get ID from [@userinfobot](https://t.me/userinfobot)
- Restart bot

**"Payment not activating"**
- Check webhook logs
- Verify Paystack credentials
- Ensure webhook URL is accessible
- See IMPLEMENTATION_GUIDE.md Section 13

**"Database connection error"**
- Verify PostgreSQL is running
- Check DB credentials in .env
- Confirm database exists: `psql -l`

##  Additional Resources

- [Paystack API Documentation](https://paystack.com/docs/api)
- [python-telegram-bot Documentation](https://pypi.org/project/python-telegram-bot/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Flask Documentation](https://flask.palletsprojects.com/)

##  License

This project is part of the Stackaiv ecosystem.

##  Support

For detailed documentation and troubleshooting:
1. Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
2. Check [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md)
3. Review [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)

##  Recent Updates

### Version 1.0.0 (January 31, 2026)
-  Added Paystack payment integration
-  Added program activation workflow
-  Added comprehensive admin panel
-  Added webhook server
-  Added 11 new database functions
-  Complete documentation suite

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for full details.

---

**Last Updated**: January 31, 2026  
**Status**:  Production Ready  
**Version**: 1.0.0
