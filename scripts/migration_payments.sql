-- Database Migration: Add Payment & Activation Features
-- Run this script to add new tables and columns
-- ========================================
-- 1. Add is_active column to programs table
-- ========================================
-- ALTER TABLE programs
-- ADD COLUMN is_active BOOLEAN DEFAULT FALSE;
-- ========================================
-- 2. Create payments table
-- ========================================
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    program_id INT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    reference TEXT UNIQUE NOT NULL,
    amount INT NOT NULL,
    status TEXT DEFAULT 'pending',
    -- pending, success, failed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_payments_program_id ON payments(program_id);
CREATE INDEX IF NOT EXISTS idx_payments_reference ON payments(reference);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
-- ========================================
-- 3. Create program_activations table
-- ========================================
CREATE TABLE IF NOT EXISTS program_activations (
    id SERIAL PRIMARY KEY,
    program_id INT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    is_paid BOOLEAN DEFAULT FALSE,
    activated_at TIMESTAMP DEFAULT NOW(),
    payment_verified_at TIMESTAMP,
    verified_by TEXT
);
-- Create indexes
CREATE INDEX IF NOT EXISTS idx_program_activations_program_id ON program_activations(program_id);
CREATE INDEX IF NOT EXISTS idx_program_activations_is_paid ON program_activations(is_paid);
-- ========================================
-- 3b. Create admin_messages table
-- ========================================
CREATE TABLE IF NOT EXISTS admin_messages (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    message_text TEXT NOT NULL,
    message_type TEXT DEFAULT 'general',
    handled BOOLEAN DEFAULT FALSE,
    handled_by TEXT,
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
-- Create indexes for admin message queries
CREATE INDEX IF NOT EXISTS idx_admin_messages_telegram_id ON admin_messages(telegram_id);
CREATE INDEX IF NOT EXISTS idx_admin_messages_handled ON admin_messages(handled);
CREATE INDEX IF NOT EXISTS idx_admin_messages_created_at ON admin_messages(created_at DESC);
COMMENT ON TABLE admin_messages IS 'Stores messages sent by users to admin for record-keeping and response tracking';
COMMENT ON COLUMN admin_messages.message_type IS 'Type of message: general, complaint, question, suggestion, bug_report';
COMMENT ON COLUMN admin_messages.handled IS 'Whether admin has responded to this message';
COMMENT ON COLUMN admin_messages.handled_by IS 'Admin username who handled this message';
-- ========================================
-- 4. Verify existing tables
-- ========================================
-- Ensure all required tables exist
-- Users table (should already exist)
-- CREATE TABLE IF NOT EXISTS users (
--     id SERIAL PRIMARY KEY,
--     telegram_id BIGINT UNIQUE NOT NULL,
--     username TEXT,
--     first_name TEXT,
--     created_at TIMESTAMP DEFAULT NOW()
-- );
-- Programs table (should already exist but we added is_active)
-- Already updated above
-- ========================================
-- 5. Create views for admin functions
-- ========================================
-- View: All transactions with program details
CREATE OR REPLACE VIEW v_transactions_detailed AS
SELECT p.id as transaction_id,
    p.program_id,
    p.reference,
    p.amount,
    p.status,
    p.created_at,
    prog.name as program_name,
    prog.level,
    prog.college,
    u.first_name as creator_name,
    u.username as creator_username,
    u.telegram_id
FROM payments p
    JOIN programs prog ON p.program_id = prog.id
    JOIN users u ON prog.created_by = u.id
ORDER BY p.created_at DESC;
-- View: Programs with activation status
CREATE OR REPLACE VIEW v_programs_with_status AS
SELECT prog.id,
    prog.name,
    prog.level,
    prog.college,
    prog.is_active,
    prog.created_at,
    u.first_name as creator_name,
    u.username as creator_username,
    u.telegram_id,
    COUNT(DISTINCT c.id) as course_count,
    COUNT(DISTINCT r.id) as resource_count
FROM programs prog
    JOIN users u ON prog.created_by = u.id
    LEFT JOIN courses c ON prog.id = c.program_id
    LEFT JOIN resources r ON c.id = r.course_id
GROUP BY prog.id,
    prog.name,
    prog.level,
    prog.college,
    prog.is_active,
    prog.created_at,
    u.first_name,
    u.username,
    u.telegram_id
ORDER BY prog.created_at DESC;
-- ========================================
-- 6. Add comments for documentation
-- ========================================
COMMENT ON TABLE payments IS 'Stores Paystack payment transactions for program activation';
COMMENT ON TABLE program_activations IS 'Tracks program activation status and payment verification';
COMMENT ON COLUMN payments.reference IS 'Unique Paystack transaction reference';
COMMENT ON COLUMN payments.amount IS 'Amount in kobo (1 NGN = 100 kobo)';
COMMENT ON COLUMN payments.status IS 'Transaction status: pending, success, failed';
COMMENT ON COLUMN programs.is_active IS 'Whether program is activated and can be used';
-- ========================================
-- 7. Verify the setup
-- ========================================
-- Run these SELECT statements to verify:
-- Count of all payments
-- SELECT COUNT(*) FROM payments;
-- Count of activated programs
-- SELECT COUNT(*) FROM programs WHERE is_active = TRUE;
-- List all programs with status
-- SELECT * FROM v_programs_with_status;
-- List all transactions
-- SELECT * FROM v_transactions_detailed;
-- ========================================
-- ROLLBACK SCRIPT (if needed)
-- ========================================
-- To revert these changes:
/*
 DROP VIEW IF EXISTS v_programs_with_status;
 DROP VIEW IF EXISTS v_transactions_detailed;
 DROP TABLE IF EXISTS program_activations;
 DROP TABLE IF EXISTS payments;
 ALTER TABLE programs DROP COLUMN IF EXISTS is_active;
 */