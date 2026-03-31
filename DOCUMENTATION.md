# Stackaiv - Complete Documentation

**Status**: Production Ready | **Version**: 1.0.0 | **Last Updated**: March 31, 2026

---
#stackaiv1234
## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Architecture](#architecture)
5. [Implementation Details](#implementation-details)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Admin Commands](#admin-commands)
9. [User Flows](#user-flows)
10. [Security](#security)
11. [Deployment](#deployment)
12. [Troubleshooting](#troubleshooting)
13. [File Structure](#file-structure)
14. [Testing](#testing)
15. [Maintenance](#maintenance)

---

## Overview

Stackaiv is a comprehensive Telegram bot that manages academic resources for students organized by program, level, and course. Students register with their college and program, then share/access course materials within their program community.

**Tech Stack:**
- Python 3.7+
- Telegram Bot API (python-telegram-bot 20.3)
- PostgreSQL Database
- Flask Webhook Server
- Paystack Payment Integration

**Run Commands:**
```bash
# Terminal 1: Start Bot
python -m app.main

# Terminal 2: Start Webhook Server
python -m app.webhook
```

---

## Features

### Core Features
- **Program Registration** - Level, College, and Program selection
- **Course Management** - Register and manage courses for programs
- **Resource Sharing** - Upload and download course materials (notes, PDFs, code, drawings, etc.)
- **Community Spaces** - Program-based Telegram groups for collaboration
- **Payment Integration** - Paystack activation fee (₦3,000 per program)
- **Admin Panel** - Complete management interface

### Payment & Activation
- **Secure Payments** - HMAC-SHA512 Paystack integration with webhook verification
- **Automatic Activation** - Program activation on successful payment
- **Transaction Tracking** - Complete payment history with status
- **Admin Controls** - Manage transactions, programs, and users

### Admin Functions (Command: `/admin7105`)
1. List all transactions with pagination
2. Fetch transaction details by ID
3. View all programs with status
4. Delete programs (with confirmation)
5. List all users
6. Broadcast messages to all users
7. Stop bot gracefully

### Resource Type Support
- Notes (PDF, DOCX, PPT format)
- Past Questions (Images, Files)
- Textbooks (PDF, DOCX)
- Extra Study Files
- Code Snippets
- Drawings

---

## Quick Start

### Prerequisites
```
Python 3.7+
PostgreSQL 12+
Telegram Bot Token (from @BotFather)
Paystack Account (https://paystack.com)
```

### Installation (5 minutes)

**Step 1: Clone and Setup**
```bash
cd Stackaiv
pip install -r requirements.txt
```

**Step 2: Configure Environment**
```bash
cp .env.example .env
# Edit .env with:
# - BOT_TOKEN (from @BotFather)
# - DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_PORT
# - ADMIN_ID (your Telegram ID)
# - PAYSTACK_SECRET_KEY and PAYSTACK_PUBLIC_KEY
# - WEBHOOK_URL (ngrok URL or production domain)
```

**Step 3: Database Setup**
```bash
# Create database
createdb Stackaiv

# Run migrations
psql -U <db_user> -d Stackaiv < scripts/init_db.sql
psql -U <db_user> -d Stackaiv < scripts/migration_payments.sql
```

**Step 4: Start Services**
```bash
# Terminal 1: Bot
python -m app.main

# Terminal 2: Webhook (for local testing with ngrok)
ngrok http 5000
python -m app.webhook
```

**Step 5: Configure Paystack Webhook**
- Go to Paystack Dashboard → Settings → Webhooks
- URL: `https://yourdomain.com/paystack/webhook`
- Test with Paystack test card: 4111 1111 1111 1111

---

## Architecture

### System Diagram

```
User (Telegram)
    ↓
Bot Handler (python-telegram-bot)
    ├── start.py (Onboarding)
    ├── notes.py (Courses)
    ├── files.py (Resources)
    ├── groups.py (Group management)
    ├── activate.py (Payment flow)
    └── admin.py (Admin panel)
    ↓
Database (PostgreSQL)
    ├── Users
    ├── Programs
    ├── Courses
    ├── Resources
    ├── Payments
    └── Admin Messages
    ↓
External Services
    ├── Telegram API
    └── Paystack API
```

### Handler Layer Pattern

**Session Management:**
- Local dictionaries store per-user state (keyed by `telegram_id`)
- Sessions track user progress through multi-step flows
- Example: `user_sessions[user_id] = {"stage": "awaiting_courses", "data": value}`

**Callback Data Format:**
- Colon-delimited: `action:param1:param2`
- Examples: `level:100`, `add:course:5`, `activate:pay`
- Limited to 64 bytes per Telegram constraint

**Error Handling:**
- `DatabaseTimeoutError` - Database operations taking too long
- `safe_db_operation()` wrapper with fallback values
- User-friendly error messages with retry options

---

## Implementation Details

### Payment Flow

```
1. User completes program registration
   ↓
2. System displays activation screen
   - Shows: Program name, level, college
   - Shows: ₦3,000 fee
   - Buttons: "Pay Now" or "Cancel"
   ↓
3. User clicks "Pay Now"
   ↓
4. Bot calls Paystack API (initialize_transaction)
   - Returns: authorization URL and reference
   ↓
5. Bot sends Paystack payment link to user
   ↓
6. User completes payment on Paystack
   ↓
7. Paystack sends webhook: charge.success
   ↓
8. Webhook Handler:
   - Verifies HMAC-SHA512 signature
   - Confirms amount == ₦3,000
   - Updates payment status
   - Activates program
   - Notifies user
   ↓
9. User can now add courses and resources
```

### Course Registration Flow

```
1. User selects "Add Courses"
2. Enters courses: "MAT 111, CSC 111, PHY 101"
3. System normalizes: "MAT 111, CSC 111, PHY 101"
4. User confirms
5. System saves to database
6. System displays resource type selection
7. User selects resource types
8. System saves associations
9. User can now upload/download resources
```

### Resource Management

**Upload Flow:**
- User selects course → select resource type → send file
- System checks for duplicates (configurable by type)
- System saves file metadata with uploader ID
- File stored as Telegram file_id (not local disk)

**Download Flow:**
- User selects course → select resource type
- System lists all resources (slot-based)
- User selects by slot number (e.g., "Slot 1, 3, 5")
- System sends files as documents

**Duplicate Prevention:**
- Notes/Textbooks: Prevent duplicate filenames
- Images/Code: Allow duplicates
- Configurable per resource type

---

## Database Schema

### Core Tables

**users**
```sql
id: SERIAL PRIMARY KEY
telegram_id: BIGINT UNIQUE NOT NULL
username: TEXT
first_name: TEXT
created_at: TIMESTAMP DEFAULT NOW()
```

**programs**
```sql
id: SERIAL PRIMARY KEY
level: TEXT (100-500)
college: TEXT (CST, COE, CLDS, CMSS)
name: TEXT
created_by: INTEGER REFERENCES users(id)
is_active: BOOLEAN DEFAULT FALSE
created_at: TIMESTAMP DEFAULT NOW()
```

**courses**
```sql
id: SERIAL PRIMARY KEY
program_id: INTEGER REFERENCES programs(id)
course_code: TEXT
created_at: TIMESTAMP DEFAULT NOW()
```

**resources**
```sql
id: SERIAL PRIMARY KEY
course_id: INTEGER REFERENCES courses(id)
resource_type_id: INTEGER REFERENCES resource_types(id)
file_id: TEXT
file_name: TEXT
uploader_id: INTEGER REFERENCES users(id)
created_at: TIMESTAMP DEFAULT NOW()
```

**payments**
```sql
id: SERIAL PRIMARY KEY
program_id: INTEGER REFERENCES programs(id)
reference: TEXT UNIQUE
amount: INTEGER
status: TEXT (pending, success, failed)
created_at: TIMESTAMP DEFAULT NOW()
```

**resource_types** (Seeded)
```
1. Notes
2. Past Questions (Images)
3. Past Questions (Files)
4. Textbooks
5. Extra Study Files
6. Code
7. Drawings
```

### Views

**v_transactions_detailed:**
```sql
SELECT p.id, p.reference, p.amount, p.status, p.created_at,
       pr.name as program_name, u.first_name, u.username
FROM payments p
JOIN programs pr ON p.program_id = pr.id
JOIN users u ON pr.created_by = u.id
```

**v_programs_with_status:**
```sql
SELECT p.*, COUNT(c.id) as course_count, MAX(r.created_at) as last_resource
FROM programs p
LEFT JOIN courses c ON p.id = c.program_id
LEFT JOIN resources r ON c.id = r.course_id
GROUP BY p.id
```

---

## API Endpoints

### Telegram Handlers

**Bot Commands:**
- `/start` - Onboarding or access existing program
- `/whoami` - View your program info
- `/admin7105` - Admin control panel
- `/setupgroup` - Setup group for program

**Callbacks (inline buttons):**
- `level:{level}` - Select program level
- `college:{college}` - Select college
- `add:course:{course_id}` - Add resource to course
- `hub:get` - Download resources
- `activate:pay` - Initiate payment
- `admin:list_transactions` - View transactions

### Webhook Endpoints

**POST /paystack/webhook**
- Receives: charge.success, charge.failure, charge.abandon events
- Validates: HMAC-SHA512 signature
- Actions: Updates payment, activates program, notifies user

**GET /paystack/health**
- Returns: {"status": "ok", "service": "paystack-webhook"}

**GET /telegram/health**
- Returns: Bot initialization and DB connection status

**POST /telegram/webhook**
- Receives: Telegram bot updates
- Processes: Messages, callbacks, commands

---

## Admin Commands

### Transaction Management

**List Transactions**
- Shows paginated list of all payments
- Displays: ID, Reference, Amount, Status, Date
- Pagination: 10 per page

**Fetch Transaction**
- Enter transaction ID
- Shows full details: Reference, Amount, Status, Program, User, Date

### Program Management

**List Programs**
- Shows all registered programs
- Displays: ID, Name, Level, College, Creator, Status
- Pagination: 5 per page
- Sorted: Most recent first

**Delete Program**
- Requires confirmation
- Cascade deletes: Courses, Resources, Payments, Activations
- Logs action with admin details

### User Management

**List Users**
- Shows all registered users
- Displays: ID, Telegram ID, Name, Username
- Pagination: 10 per page
- Shows total user count

**View Messages**
- Shows unhandled user messages
- Displays: Status (NEW/Handled), User, Message preview, Date
- Can see full message content

### Broadcast

**Send Message**
- Enter message text (supports Markdown)
- Shows confirmation with recipient count
- Sends to all users with retry logic
- Shows success/failure count

**Stop Bot**
- Confirmation required
- Stops bot polling gracefully
- Useful for maintenance or updates

---

## User Flows

### Onboarding Flow (New User)

```
/start (private chat)
    ↓
"Go to Program Space" or "Onboard New Program"
    ↓
[IF NEW PROGRAM]
    ↓
    Select Level (100, 200, 300, 400, 500)
        ↓
    Select College (CST, COE, CLDS, CMSS)
        ↓
    Select Program (e.g., Computer Science)
        ↓
    Confirm Details
        ↓
    [PROGRAM REGISTERED]
        ↓
    Add Courses? → "MAT 111, CSC 111, PHY 101"
        ↓
    Confirm Courses
        ↓
    Select Resource Types (Multi-select)
        ↓
    Activation Screen (₦3,000 fee)
        ↓
    [Payment Flow]
        ↓
    [PROGRAM ACTIVATED]
        ↓
    Resource Hub Access
```

### Resource Upload Flow

```
Hub → "Add Resource"
    ↓
Select Course
    ↓
Select Resource Type
    ↓
Send File(s)
    ↓
[BATCH PROCESSING: 2-second window]
    ↓
Confirm Upload Details
    ↓
Process All
    ↓
[FILES SAVED]
    ↓
Success Message with Count
```

### Resource Download Flow

```
Hub → "Get Resource"
    ↓
Select Course
    ↓
Select Resource Type
    ↓
Display Available Resources (Slot-based)
    ↓
User sends: "Slot 1" or "Slot 1, 3, 5" or "All"
    ↓
[FILES SENT]
    ↓
Session Cleared
```

### Payment Flow

```
Program Registered
    ↓
Activation Screen
    ↓
"Proceed with Payment"
    ↓
Enter Email (for Paystack)
    ↓
Paystack Link Sent
    ↓
User Opens Link
    ↓
[USER COMPLETES PAYMENT]
    ↓
Paystack Webhook: charge.success
    ↓
Server Verifies:
    - Signature valid
    - Amount == ₦3,000
    - Reference unique
    ↓
Program Marked Active
    ↓
Notification to User
    ↓
[PROGRAM ACTIVATED]
```

---

## Security

### Authentication & Authorization

**User Authentication:**
- Telegram ID as unique identifier
- No additional login required (bot DM is private)

**Admin Authentication:**
- Admin ID check from environment variable
- Command: `/admin7105` (hidden numeric code)
- No user is told about admin access

**Session Management:**
- Per-user dictionaries with stage tracking
- Automatic clearing on completion or timeout
- No sensitive data in session (IDs, not tokens)

### Payment Security

**Webhook Verification:**
- HMAC-SHA512 signature validation
- Compares X-Paystack-Signature header with computed hash
- Rejects unsigned or tampered requests

**Amount Validation:**
- Verifies amount == ₦3,000 (fixed fee)
- Rejects mismatched amounts
- Logs mismatches for investigation

**Reference Uniqueness:**
- Each transaction has unique reference
- Prevents duplicate activations
- Database UNIQUE constraint enforced

### Data Protection

**Sensitive Variables:**
- All secrets in `.env` file
- Never hardcoded in source
- Git ignores `.env`

**Error Handling:**
- No stack traces sent to users
- Errors logged server-side only
- User sees: "An error occurred. Try again."

**SQL Injection Prevention:**
- All queries use parameterized statements
- psycopg2 cursor.execute(query, params)
- No string concatenation in queries

**File Storage:**
- Uses Telegram file_id (not local disk)
- Scalable to cloud storage later (S3, GCS)
- No sensitive file metadata exposed

---

## Deployment

### Local Development

```bash
# 1. Setup database
createdb Stackaiv
psql -U postgres -d Stackaiv < scripts/init_db.sql
psql -U postgres -d Stackaiv < scripts/migration_payments.sql

# 2. Create .env from template
cp .env.example .env

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run bot (Terminal 1)
python -m app.main

# 5. Setup ngrok (Terminal 2)
ngrok http 5000

# 6. Update .env with ngrok URL
# WEBHOOK_URL=https://xxxx-xxxx-xxxx.ngrok-free.app/paystack/webhook

# 7. Run webhook server (Terminal 3)
python -m app.webhook
```

### Production Deployment (Render/Heroku)

**Step 1: Push to Git**
```bash
git add .
git commit -m "Deploy Stackaiv"
git push origin master
```

**Step 2: Create Render Service**
- Framework: Python
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m app.main`

**Step 3: Create Flask App Service**
- Start Command: `gunicorn --bind 0.0.0.0:5000 app.webhook:app`
- Add Render PostgreSQL database
- Copy environment variables to Render dashboard

**Step 4: Configure Telegram Webhook**
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://stackaiv-manager-bot.onrender.com/telegram/webhook"}'
```

**Step 5: Configure Paystack Webhook**
- Paystack Dashboard → Settings → Webhooks
- URL: `https://stackaiv-manager-bot.onrender.com/paystack/webhook`

**Production Checklist:**
- [ ] Database migrations applied
- [ ] Environment variables set (all required vars)
- [ ] Telegram webhook configured
- [ ] Paystack webhook configured
- [ ] Admin ID set
- [ ] Paystack live keys configured (not test keys)
- [ ] Error logging enabled
- [ ] Database backups scheduled

---

## Troubleshooting

### Common Issues

**"Bot not responding"**
- Check: BOT_TOKEN is correct
- Check: Bot polling is running (`python -m app.main`)
- Fix: Restart bot process

**"Payment webhook not received"**
- Check: Webhook URL is correct in Paystack dashboard
- Check: Webhook server is running (`python -m app.webhook`)
- Check: Firewall allows incoming requests
- Test: Use Paystack Dashboard → Test Webhook

**"Database connection failed"**
- Check: PostgreSQL is running
- Check: Database credentials in `.env`
- Check: Database exists: `psql -U postgres -l | grep Stackaiv`
- Fix: Run migrations if DB is empty

**"User sees 'System is busy'"**
- Cause: Database timeout (30-second limit)
- Fix: Optimize slow queries or increase pool
- Monitor: Check database logs for slow queries

**"Transaction not completing"**
- Check: Paystack test card used in sandbox
- Check: Amount is exactly ₦3,000
- Fix: Wait for webhook to process (can take a few seconds)
- Test: Manual verification with `/verify <reference>`

**"Admin access denied"**
- Check: ADMIN_ID matches your Telegram ID
- Find: Send `/whoami` to see your ID
- Fix: Update `.env` with correct ADMIN_ID

### Debug Mode

```python
# In app/main.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)

# Check logs for detailed information
```

### Database Maintenance

**Check Database Health:**
```sql
-- Show all programs
SELECT * FROM programs;

-- Show all users
SELECT * FROM users;

-- Show pending payments
SELECT * FROM payments WHERE status = 'pending';

-- Show recent resources
SELECT * FROM resources ORDER BY created_at DESC LIMIT 10;
```

**Backup Database:**
```bash
pg_dump Stackaiv > stackaiv_backup.sql

# Restore from backup
psql Stackaiv < stackaiv_backup.sql
```

---

## File Structure

```
Stackaiv/
├── README.md (Main entry point)
├── DOCUMENTATION.md (This file)
├── .env (Environment secrets - gitignored)
├── .env.example (Template for .env)
├── requirements.txt (Python dependencies)
│
├── app/
│   ├── main.py (Bot initialization)
│   ├── webhook.py (Flask webhook server)
│   ├── config.py (Configuration - currently empty)
│   │
│   ├── handlers/
│   │   ├── start.py (Onboarding flow)
│   │   ├── notes.py (Course registration)
│   │   ├── files.py (Resource hub)
│   │   ├── groups.py (Group management)
│   │   ├── activate.py (Payment flow)
│   │   └── admin.py (Admin panel)
│   │
│   ├── database/
│   │   ├── clients.py (Connection pool)
│   │   ├── queries.py (All database functions)
│   │   └── models.sql (Schema definitions)
│   │
│   ├── services/
│   │   ├── payments.py (Paystack integration)
│   │   ├── groups.py (Group logic)
│   │   └── storage.py (File storage)
│   │
│   ├── utils/
│   │   ├── keyboards.py (Inline keyboard builders)
│   │   ├── messages.py (Message templates)
│   │   ├── validators.py (Input validation)
│   │   ├── db_operations.py (DB safety wrapper)
│   │   ├── pagination.py (Pagination helper)
│   │   └── logger.py (Logging setup)
│   │
│   └── keyboards/
│       ├── menus.py (Menu builders)
│       └── confirm.py (Confirmation dialogs)
│
├── scripts/
│   ├── init_db.sql (Initial schema)
│   ├── migration_payments.sql (Payment tables)
│   └── cleanup.py (Utility scripts)
│
├── tests/
│   ├── test_db.py (Database tests)
│   └── test_transaction_fix.py (Payment flow tests)
│
├── data/
│   ├── uploads/ (Local file backups)
│   └── temp/ (Temporary processing)
│
└── venv/ (Python virtual environment - gitignored)
```

---

## Testing

### Manual Testing Checklist

**User Flows:**
- [ ] Complete user onboarding
- [ ] Register courses
- [ ] Select resource types
- [ ] Add resources
- [ ] Download resources
- [ ] Delete and re-register program

**Payment Flow:**
- [ ] Initiate payment
- [ ] Complete Paystack test payment
- [ ] Verify program activation
- [ ] Check transaction in admin panel
- [ ] Manual verification command works

**Admin Commands:**
- [ ] Access admin panel (`/admin7105`)
- [ ] List transactions
- [ ] Fetch transaction details
- [ ] List programs
- [ ] Delete program (with cascade)
- [ ] List users
- [ ] Send broadcast message
- [ ] Stop bot

**Error Handling:**
- [ ] Invalid program ID shown
- [ ] Wrong amount shows error
- [ ] Database timeout handled
- [ ] Invalid inputs rejected
- [ ] Session expiration handled

### Test Paystack Card

```
Number: 4111 1111 1111 1111
Expiry: 12/25
CVV: 123
Amount: 3000
```

### Unit Test Templates

```python
def test_user_registration():
    # Create test user
    user_id = save_user(123456789, "testuser", "Test")
    assert user_id is not None

def test_program_creation():
    # Add user then program
    user_id = save_user(123456789, "testuser", "Test")
    program_id = save_program(100, "CST", "Computer Science", user_id)
    assert program_id is not None

def test_payment_verification():
    # Simulate webhook payload
    payload = {
        "reference": "ref_123456",
        "amount": 300000,  # 3000 naira in kobo
        "status": "success"
    }
    result = verify_transaction(payload)
    assert result["status"] == "success"
```

---

## Maintenance

### Regular Tasks

**Weekly:**
- [ ] Check error logs
- [ ] Monitor Paystack transactions
- [ ] Verify webhook delivery

**Monthly:**
- [ ] Database backup
- [ ] Analyze slow queries
- [ ] Review admin logs
- [ ] Update dependencies

**Quarterly:**
- [ ] Security audit
- [ ] Performance review
- [ ] User feedback analysis
- [ ] Plan improvements

### Monitoring

**Key Metrics:**
- Successful vs failed payments
- Average response time
- Database query performance
- User registration rate
- Resource upload rate

**Alerts to Setup:**
- Payment webhook failures
- Database connection errors
- Admin access attempts
- High error rates

### Version Control

**Commit Message Format:**
```
[component] brief description

Optional longer description explaining why

Feature: Add new feature
Fix: Fix bug in component
Docs: Update documentation
Refactor: Improve code structure
```

**Branches:**
- `main` - Production code
- `develop` - Development branch
- `feature/*` - Feature branches

---

## Glossary

| Term | Definition |
|------|-----------|
| **Program** | Academic program (e.g., Computer Science, 100 Level, CST) |
| **Course** | Individual course in a program (e.g., MAT 111) |
| **Resource** | Uploaded material (notes, PDF, code, etc.) |
| **College** | Faculty/College (CST, COE, CLDS, CMSS) |
| **Level** | Year of study (100, 200, 300, 400, 500) |
| **Telegram ID** | Unique ID for each Telegram user |
| **File ID** | Telegram's unique identifier for uploaded files |
| **Reference** | Unique transaction ID from Paystack |
| **Webhook** | HTTP callback from Paystack for payment events |
| **Payload** | Data sent in webhook request |
| **Session** | Temporary storage for user's multi-step flow data |

---

## Support & Resources

### Internal Documentation
- README.md - Quick introduction
- .env.example - Configuration template
- scripts/init_db.sql - Database initialization
- scripts/migration_payments.sql - Payment schema

### External Resources
- [Paystack API Docs](https://paystack.com/docs/api)
- [python-telegram-bot Docs](https://pypi.org/project/python-telegram-bot/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Contact
- **Issues**: Create GitHub issue with details
- **Questions**: Add to documentation
- **Bugs**: Include error logs and reproduction steps

---

## License & Credits

Built with ❤️ for Stackaiv  
Python 3.7+ | Telegram Bot API | PostgreSQL | Paystack

---

**Last Updated**: March 31, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
