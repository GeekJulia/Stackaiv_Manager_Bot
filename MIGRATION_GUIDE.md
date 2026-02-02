# Database Migration: Admin Messages

## Quick Setup

### Step 1: Apply Migration
Run this command to create the `admin_messages` table:

```bash
psql -U <your_db_user> -d <your_db_name> < scripts/migration_payments.sql
```

Replace `<your_db_user>` and `<your_db_name>` with your actual PostgreSQL credentials.

### Step 2: Verify Table Creation
```sql
-- Check if table exists
\dt admin_messages

-- View table structure
\d admin_messages

-- Check indexes
\di admin_messages*
```

### Step 3: Restart Bot
```bash
python -m app.main
```

---

## What Gets Created

### admin_messages Table
- **Purpose:** Stores all messages sent by users to the admin panel
- **Columns:**
  - `id` (SERIAL PRIMARY KEY) - Unique message ID
  - `user_id` (INT FK) - Reference to users table
  - `telegram_id` (BIGINT) - Telegram user ID
  - `username` (TEXT) - User's Telegram username
  - `first_name` (TEXT) - User's first name
  - `message_text` (TEXT) - The actual message content
  - `message_type` (TEXT) - Type: general, complaint, question, suggestion, bug_report
  - `handled` (BOOLEAN) - Whether admin has responded
  - `handled_by` (TEXT) - Admin username who handled it
  - `handled_at` (TIMESTAMP) - When it was marked as handled
  - `created_at` (TIMESTAMP) - When message was received

### Indexes Created
1. `idx_admin_messages_telegram_id` - Fast user message lookups
2. `idx_admin_messages_handled` - Fast filtering of unhandled messages
3. `idx_admin_messages_created_at` - Fast date-based sorting

---

## Admin Panel Usage

### View All User Messages
1. Command: `/admin7105`
2. Click: 💬 User Messages
3. Bot displays:
   - Total message count
   - Unhandled message count
   - Recent messages with status, user, preview, and date

### Message Status
- **🔴 NEW** - Message not yet responded to
- **✅ Handled** - Admin has responded to this message

### Features
- Shows up to 200 most recent messages
- Automatically chunks output to avoid message size limits
- Displays message previews (first 100 characters)
- Clear user identification (@username or ID)
- Date-based organization

---

## Rollback (If Needed)

If you need to remove these changes:

```sql
-- Drop the table and indexes
DROP TABLE IF EXISTS admin_messages CASCADE;
```

---

## Important Notes

⚠️ **Before Deployment:**
- Ensure PostgreSQL is running and accessible
- Verify database user has CREATE TABLE permissions
- Back up your database before running migration
- Test in development environment first

✅ **After Deployment:**
- Verify table creation with `\dt admin_messages`
- Test admin panel "User Messages" button
- Monitor for any errors in bot logs
- Confirm proper message chunking in Telegram

---

## Troubleshooting

### Migration Fails - "Permission Denied"
```
Error: permission denied for schema public
Solution: Database user needs CREATE TABLE permission
psql -U postgres -d <db_name> -c "GRANT CREATE ON SCHEMA public TO <your_user>;"
```

### Table Already Exists
```
Error: relation "admin_messages" already exists
Solution: This is normal if re-running migration. Script uses "IF NOT EXISTS"
No action needed - just confirms table is ready
```

### Indexes Not Created
```sql
-- Manually create if needed
CREATE INDEX IF NOT EXISTS idx_admin_messages_telegram_id ON admin_messages(telegram_id);
CREATE INDEX IF NOT EXISTS idx_admin_messages_handled ON admin_messages(handled);
CREATE INDEX IF NOT EXISTS idx_admin_messages_created_at ON admin_messages(created_at DESC);
```

---

## Testing the Feature

```python
# Test from Python shell
from app.database.queries import (
    save_admin_message,
    get_all_admin_messages,
    get_admin_messages_count
)

# Save a test message
save_admin_message(123456789, "testuser", "Test", "This is a test message")

# Get all messages
messages = get_all_admin_messages(limit=10)
print(f"Total messages: {len(messages)}")

# Get unhandled count
count = get_admin_messages_count()
print(f"Unhandled: {count}")
```

---

## Admin Panel Commands Updated

- `/admin7105` - Opens admin panel
- New button: **💬 User Messages** - View all stored messages
- Messages include status, user info, content preview, and date
- Automatic chunking handles large message lists

---

## Performance Notes

The table uses proper indexes:
- **telegram_id index** - Lookups by user (O(log n))
- **handled index** - Filtering unhandled messages (O(log n))
- **created_at index** - Sorted by date (O(log n))

This ensures admin queries remain fast even with thousands of messages.
