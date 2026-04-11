-- Add 'program_id' column to 'users' table to permanently link users to a Hub
ALTER TABLE users ADD COLUMN IF NOT EXISTS program_id INTEGER REFERENCES programs(id);
