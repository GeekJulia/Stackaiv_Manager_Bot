-- Add 'career' column to 'users' table
ALTER TABLE users ADD COLUMN IF NOT EXISTS career TEXT;
