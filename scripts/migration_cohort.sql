-- Cohort & Monetization Schema Update

-- 1. Add Graduation Year to Programs
ALTER TABLE programs ADD COLUMN IF NOT EXISTS graduation_year INTEGER;

-- 2. Add Semester and Academic Level to Courses
ALTER TABLE courses ADD COLUMN IF NOT EXISTS semester VARCHAR(20) DEFAULT 'Alpha';
ALTER TABLE courses ADD COLUMN IF NOT EXISTS academic_level VARCHAR(20);

-- 3. Migrate existing courses to inherit their Program's current level
UPDATE courses c
SET academic_level = p.level
FROM programs p
WHERE c.program_id = p.id AND c.academic_level IS NULL;

-- 4. Create Archive Subscriptions Table
CREATE TABLE IF NOT EXISTS archive_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    access_type VARCHAR(20) NOT NULL, -- 'course', 'level', 'full'
    target_course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    target_level VARCHAR(20),
    payment_reference VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
