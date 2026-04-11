-- Update existing programs with a default graduation year of 2026
-- This is intended to be run after the migration_cohort.sql has added the graduation_year column

UPDATE programs 
SET graduation_year = 2026 
WHERE graduation_year IS NULL;

-- Verify the update
SELECT id, name, graduation_year FROM programs;
