# Stackaiv Payment & Activation Workflow

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM USER                              │
│                     (Alice - Registration)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    1. /start command
                             ▼
        ┌────────────────────────────────────────┐
        │  [start.py] - Level/College/Program    │
        │  User completes registration           │
        │  Program saved to DB (is_active=FALSE) │
        └────────────┬───────────────────────────┘
                     │
            2. Click "Activate Program"
                     ▼
        ┌────────────────────────────────────────┐
        │  [activate.py] - Show Activation Info  │
        │  ✅ Show: ₦3,000 fee required         │
        │  ✅ Buttons: Pay / Cancel             │
        └────────────┬───────────────────────────┘
                     │
            3. Click "Proceed with Payment"
                     ▼
        ┌────────────────────────────────────────┐
        │  [activate.py] - Initialize Payment    │
        │  • Generate unique reference           │
        │  • Call: initialize_transaction()      │
        └────────────┬───────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                  [payments.py] Service                      │
        │  • Create POST request to Paystack API                      │
        │  • URL: /transaction/initialize                             │
        │  • Amount: 300000 kobo (₦3,000)                             │
        │  • Reference: STACKAIV_U{user}_P{prog}_{time}              │
        │  • Save payment record (status="pending")                   │
        └────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                    PAYSTACK API                             │
        │  Response: {                                                │
        │    "status": true,                                          │
        │    "data": {                                                │
        │      "authorization_url": "https://checkout.paystack.com/...",
        │      "reference": "re4lyvq3s3"                              │
        │    }                                                         │
        │  }                                                           │
        └────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │  [activate.py] - Show Payment Link     │
        │  ✅ Button: "💳 Pay Now"              │
        │     → Opens authorization_url         │
        └────────────┬───────────────────────────┘
                     │
            4. User clicks payment link
                     ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                    PAYSTACK CHECKOUT                        │
        │  • Show card/bank payment options                           │
        │  • User enters payment details                              │
        │  • Paystack processes payment                               │
        │  • Status: Success ✅                                       │
        └────────────┬────────────────────────────────────────────────┘
                     │
            5. Paystack fires webhook
                     ▼
    ┌───────────────────────────────────────────────────────┐
    │                                                        │
    │  IMPORTANT: Two parallel processes happen now:        │
    │                                                        │
    │  Path A: User redirected to confirmation page         │
    │  Path B: Webhook sent to bot webhook server           │
    │                                                        │
    └───────────────────────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        │                           │
        ▼ Path A: User sees         ▼ Path B: Webhook
        "Payment Successful"        Server receives
        (Can close browser)         charge.success
        │                           │
        │                           ▼
        │          ┌───────────────────────────────────┐
        │          │ [webhook.py] - Paystack Webhook  │
        │          │ Endpoint: POST /paystack/webhook  │
        │          │                                   │
        │          │ 1. Verify HMAC-SHA512 signature  │
        │          │ 2. Extract reference & amount    │
        │          │ 3. Validate amount == 300000     │
        │          │ 4. Call: handle_payment_webhook()│
        │          └──────────────┬────────────────────┘
        │                         │
        │                         ▼
        │          ┌───────────────────────────────────┐
        │          │ [payments.py] - Process Webhook   │
        │          │                                   │
        │          │ 1. Get payment record by ref      │
        │          │ 2. Update status → "success"      │
        │          │ 3. Get program_id                 │
        │          │ 4. Call: activate_program()       │
        │          │    - UPDATE programs              │
        │          │      SET is_active = TRUE         │
        │          │    - INSERT activation record     │
        │          └──────────────┬────────────────────┘
        │                         │
        │ (They meet here)◄───────┤
        └────────────┬────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────┐
        │    Database State Updated:             │
        │    • payments.status = "success"       │
        │    • programs.is_active = TRUE         │
        │    • program_activations record added  │
        └────────────┬───────────────────────────┘
                     │
            (Bot detects activation)
                     ▼
        ┌────────────────────────────────────────┐
        │  [notes.py] - Next Screen             │
        │  ✅ "Your program is activated!"      │
        │  ✅ Button: "Add Courses"             │
        └────────────┬───────────────────────────┘
                     │
            5. Click "Add Courses"
                     ▼
        ┌────────────────────────────────────────┐
        │  [notes.py] - Course Registration      │
        │  • Enter courses: "MAT 111 | CSC 222"  │
        │  • Confirm                             │
        │  • Select resource types               │
        │  • Done!                               │
        └────────────────────────────────────────┘
```

## Admin Command Flow

```
┌─────────────────────────────────┐
│ Admin sends: /admin7105         │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ [admin.py] - Admin Verification         │
│ • Check: user_id == ADMIN_ID            │
│ • If not admin → reject                 │
│ • If admin → show menu                  │
└────────────┬────────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │  ADMIN MENU        │
    └────────────────────┘
             │
    ┌────────┼────────┬──────────┬─────────┬──────────┐
    │        │        │          │         │          │
    ▼        ▼        ▼          ▼         ▼          ▼
   📊      🔍       🏫         🗑️        👥         📢
 Trans   Fetch    Programs   Delete    Users    Broadcast
   │      │        │         │         │        │
   ├─────┐│        │         │         │        │
   │     ││        ├─────┐   │         │        │
   │     ││        │     │   ▼         │        │
   │     │└─────┐  │     │  Confirm?   │        │
   │     │      │  │     │   Yes/No    │        │
   ▼     ▼      ▼  ▼     ▼             ▼        ▼
  List  Get   List Delete        List      Compose
  All  One   All  One           All      Message
  Trans Trans Prog Prog        Users         │
        (by ID)      (cascade)            │
                                    Get all users
                                          │
                                    Send to each
                                          │
                                    Report: Sent/Failed
```

## Database Relationships

```
┌──────────────────┐
│     USERS        │
├──────────────────┤
│ id (PK)          │
│ telegram_id      │
│ username         │
│ first_name       │
│ created_at       │
└────────┬─────────┘
         │
         │ created_by (FK)
         ▼
┌──────────────────────────────────────┐
│         PROGRAMS                     │
├──────────────────────────────────────┤
│ id (PK)                              │
│ level, college, name                 │
│ created_by (FK to users)             │
│ is_active ← [NEW] activation status  │
│ created_at                           │
└────────┬──────────────┬──────────────┘
         │              │
         │              └─────────────────┐
         │                                │
         │ program_id (FK)                │ program_id (FK)
         ▼                                ▼
┌──────────────────┐      ┌────────────────────────────────┐
│    COURSES       │      │  PROGRAM_ACTIVATIONS [NEW]     │
├──────────────────┤      ├────────────────────────────────┤
│ id (PK)          │      │ id (PK)                        │
│ program_id (FK)  │      │ program_id (FK to programs)    │
│ course_code      │      │ is_paid                        │
│ created_at       │      │ activated_at                   │
└────────┬─────────┘      │ payment_verified_at            │
         │                │ verified_by                    │
         │ course_id (FK) └────────────────────────────────┘
         ▼
┌──────────────────────────────────────┐      ┌──────────────────────────────┐
│  COURSE_RESOURCE_TYPES               │      │   PAYMENTS [NEW]             │
├──────────────────────────────────────┤      ├──────────────────────────────┤
│ course_id (FK/PK)                    │      │ id (PK)                      │
│ resource_type_id (FK/PK)             │      │ program_id (FK to programs)  │
└──────────────────────────────────────┘      │ reference (UNIQUE)           │
                                              │ amount (in kobo)             │
         ┌──────────────────────────┐         │ status (pending/success)     │
         │                          │         │ created_at                   │
         │ resource_type_id (FK)    │         └──────────────────────────────┘
         ▼                          │
┌────────────────────┐     ┌────────────────────┐
│  RESOURCE_TYPES    │     │   RESOURCES        │
├────────────────────┤     ├────────────────────┤
│ id (PK)            │     │ id (PK)            │
│ name               │     │ course_id (FK)     │
└────────────────────┘     │ resource_type     │
                           │ file_id (UNIQUE)  │
                           │ file_name         │
                           │ uploader_id (FK)  │
                           │ created_at        │
                           └────────────────────┘
```

## Payment State Transitions

```
User Registration
      │
      ▼
   [NOT ACTIVE]
      │
      │ Click "Activate Program"
      ▼
[AWAITING PAYMENT]
      │
      ├─ Payment Initialized
      │  │
      │  ├─ User opens Paystack link
      │  │  │
      │  │  ├─ Payment Successful ──────────┐
      │  │  │                               │
      │  │  ├─ Payment Failed               │
      │  │  │  └─ User can retry           │
      │  │  │                               │
      │  │  └─ User abandons payment        │
      │  │     └─ User can retry           │
      │  │                                 │
      │  └─ Webhook received                │
      │     (charge.success event)          │
      │                                 ◄──┘
      │     Verify payment
      │     │
      │     ├─ Valid ✅
      │     │  └─ Update: is_active = TRUE
      │     │     └─ [ACTIVATED] ✅✅✅
      │     │
      │     └─ Invalid ❌
      │        └─ Manual retry needed
      │
      └─ User clicks Cancel
         └─ [CANCELLED] → Return to /start
```

## API Endpoints

### Paystack APIs Used

```
1. Initialize Transaction
   POST https://api.paystack.co/transaction/initialize
   Headers:
     Authorization: Bearer {PAYSTACK_SECRET_KEY}
     Content-Type: application/json
   Body:
     {
       "email": "user@example.com",
       "amount": 300000,           // ₦3,000 in kobo
       "reference": "unique_ref",
       "currency": "NGN",
       "channels": ["card", "bank", "bank_transfer"]
     }
   Response:
     {
       "status": true,
       "data": {
         "authorization_url": "https://checkout.paystack.com/...",
         "access_code": "code123",
         "reference": "ref123"
       }
     }

2. Verify Transaction
   GET https://api.paystack.co/transaction/verify/{reference}
   Headers:
     Authorization: Bearer {PAYSTACK_SECRET_KEY}
   Response:
     {
       "status": true,
       "data": {
         "reference": "ref123",
         "amount": 300000,
         "status": "success",
         "customer": {...}
       }
     }

3. Webhook (Paystack → Your Server)
   POST https://yourdomain.com/paystack/webhook
   Headers:
     X-Paystack-Signature: {hmac-sha512-signature}
   Body:
     {
       "event": "charge.success",
       "data": {
         "reference": "ref123",
         "amount": 300000,
         "status": "success"
       }
     }
```

### Bot API Endpoints

```
Internal Telegram Bot API calls:
  bot.send_message()
  bot.edit_message_text()
  bot.answer_callback_query()
  bot.stop_polling()
```

## Message Flow Sequence

```
Time │ User              │ Bot               │ Database    │ Paystack     │ Webhook
─────┼──────────────────┼───────────────────┼─────────────┼──────────────┼─────────
T0   │ /start           │                   │             │              │
     │                  │ → Level selector  │             │              │
T1   │ Select level     │                   │             │              │
     │                  │ → College selector│             │              │
T2   │ Select college   │                   │             │              │
     │                  │ → Program name    │             │              │
T3   │ Send program     │                   │             │              │
     │                  │ Save user+program │ INSERT      │              │
     │                  │ → Activate button │ (is_active) │              │
T4   │ Click Activate   │                   │             │              │
     │                  │ Show fee screen   │             │              │
T5   │ Click Pay        │ Gen reference     │             │              │
     │                  │ Send to Paystack  │ → /init     │              │
T6   │                  │ Paystack responds │             │ ← success    │
     │                  │ → Payment link    │             │              │
T7   │ Click link       │                   │             │ User pays... │
T8   │ Payment success  │                   │             │ Success ✅  │
T9   │                  │                   │             │ → Webhook   │
     │                  │                   │             │   fires     │
T10  │                  │ ← Webhook POST    │             │ (async)     │
     │                  │ Verify signature  │             │             │
     │                  │ Update payment    │ UPDATE      │             │
     │                  │ Activate program  │ UPDATE      │             │
     │                  │ Send confirmation │             │             │
T11  │ Get "Activated!" │                   │             │             │
     │                  │ → "Add Courses"   │             │             │
```

---

This diagram shows the complete flow of how the payment and activation system works!
