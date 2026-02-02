# Quick Setup Guide - Payment & Admin Features

## Step 1: Update Requirements

Add these packages to `requirements.txt`:

```
requests==2.31.0
flask==3.0.0
gunicorn==21.2.0
python-telegram-bot==20.3
psycopg2-binary==2.9.9
python-dotenv==1.0.0
```

Install:
```bash
pip install -r requirements.txt
```

## Step 2: Database Setup

Update your `.env` file with:

```env
# Existing
BOT_TOKEN=your_telegram_bot_token
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=your_password
DB_DATABASE=stackaiv
DB_PORT=5432

# New - Admin
ADMIN_ID=123456789

# New - Paystack
PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxx

# New - Webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_URL=https://yourdomain.com/paystack/webhook
```

## Step 3: Get Your Admin ID

1. Open Telegram
2. Send any message to [@userinfobot](https://t.me/userinfobot)
3. Copy the `id` value
4. Add to `.env`: `ADMIN_ID=your_id`

## Step 4: Get Paystack Keys

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Sign up or login
3. Go to Settings → API Keys & Webhooks
4. Copy **Secret Key** and **Public Key**
5. Add to `.env`:
   ```env
   PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxx
   PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxx
   ```

## Step 5: Configure Paystack Webhook

1. In Paystack Dashboard, go to Settings → API Keys & Webhooks
2. Find "Webhook" section
3. Enter your webhook URL: `https://yourdomain.com/paystack/webhook`
   - For testing use: `http://localhost:5000/paystack/webhook`
4. Subscribe to events:
   - ✅ charge.success
   - ✅ charge.failure
   - ✅ charge.abandon
5. Save

## Step 6: Run the Bot and Webhook

### Terminal 1 - Main Bot
```bash
python -m app.main
```

### Terminal 2 - Webhook Server
```bash
python -m app.webhook
```

## Step 7: Test Payment Flow

1. Start the bot: `/start`
2. Register a new program
3. Click "💳 Activate Program & Continue"
4. Click "💳 Pay Now"
5. Use test card:
   - **Card Number**: 4111 1111 1111 1111
   - **Expiry**: 12/25
   - **CVV**: 123
6. Complete payment
7. Check if program is marked as active

## Step 8: Test Admin Commands

1. Send `/admin7105` to your bot
2. You should see admin control panel
3. Try each function

## Troubleshooting

### "Webhook not accessible"
- Use ngrok for local testing:
  ```bash
  ngrok http 5000
  ```
- Update webhook URL in Paystack with ngrok URL

### "Admin command not working"
- Verify ADMIN_ID in `.env`
- Restart bot: `Ctrl+C` then run again

### "Payment not processing"
- Check webhook server logs for errors
- Verify Paystack keys are correct
- Ensure webhook URL is accessible

## Next Steps

1. Update your main bot start command to include activation
2. Configure email notifications (optional)
3. Set up monitoring for webhook health
4. Deploy to production server

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for full documentation.
