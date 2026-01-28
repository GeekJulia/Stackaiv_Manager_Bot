# Stackaiv Bot - AI Coding Guide

## Project Overview
**Stackaiv** is a Telegram bot that manages academic resources for students organized by program, level, and course. Students register with their college and program, then share/access course notes, past questions, textbooks, and code within their program community.

**Tech Stack:** Python, Telegram Bot API (python-telegram-bot 20.3), PostgreSQL, python-dotenv

**Run Command:** `python -m app.main`

---

## Architecture Pattern: Handlers + Services + Database

### Handler Layer (`app/handlers/`)
- **Purpose:** Telegram message/callback routing using decorators
- **Pattern:** Each handler file (start.py, notes.py, files.py, groups.py, payments.py) registers callback handlers and message handlers with the bot instance
- **Session Management:** Local dicts (e.g., `notes_sessions = {}`) store per-user state keyed by `message.from_user.id`
- **Key Files:**
  - `start.py` - User onboarding: college selection → program level → program name
  - `notes.py` - Course registration via pipe-separated format: `"MAT 111 | CSC 111"`
  - `files.py` - Resource hub: upload/download resources by course + type (Notes, PQ Files, Textbooks, etc.)

### Database Layer (`app/database/`)
- **queries.py** - Direct psycopg2 connection pool; uses environment variables:
  - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE`, `DB_PORT`
- **Key Functions:**
  - `save_user(telegram_id, username, first_name)` - UPSERT on telegram_id
  - `save_program(level, college, program_name, user_id)` - UPSERT on created_by
  - `get_user_program_id(telegram_id)` - Cross-table JOIN lookup
  - `save_courses(program_id, course_codes)` - Batch insert with RETURNING
  - `get_resource_types()` - Returns [{id, name}] from DB
- **Resource Types:** Notes, PQ Images, PQ Files, Textbooks, Extra Study Files, Code, Drawings

### Services Layer (`app/services/`)
- **Status:** Currently empty but structured for business logic separation (notes.py, files.py, groups.py, payments.py)
- **Expected Future Role:** Extraction of queries logic, file processing, payment integration

### Data Organization
- **Program Registration:** Each user has ONE program (level + college + name)
- **Courses:** Programs have many courses (e.g., CSC 101, MAT 111)
- **Resources:** Each resource maps to course + resource_type + user
- **File Storage:** `data/uploads/` directory for user uploads

---

## Critical Workflows

### User Onboarding Flow (start.py)
1. `/start` command triggers level selection (100-500)
2. Callback routes to college selection (CST, COE, CLDS, CMSS)
3. College callback routes to program name input
4. `save_user()` + `save_program()` writes to DB
5. User session stored in `user_sessions[telegram_id]`

### Course Registration Flow (notes.py)
1. "Add Courses" callback sets session stage to `"awaiting_courses"`
2. User sends pipe-separated input: `"MAT 111 | CSC 111"`
3. Parser strips whitespace and uppercases: `course_codes = [c.strip() for c in raw_courses.split("|")]`
4. `save_courses(program_id, course_codes)` batch inserts
5. Session advances to `"select_resources"` stage

### Resource Hub Flow (files.py)
- `hub:courses` - Displays all courses for user's program
- `hub:addresource` - Courses list → select course → resource type selection → file upload
- `hub:getresource` - Courses list → select course → resource type → download options
- Resources keyed by: `get_resources_by_course_and_type(course_id, resource_type_id)`

---

## Code Patterns & Conventions

### Session Management
```python
sessions = {}  # Global dict per module
sessions[user_id] = {"stage": "awaiting_input", "data": value}

# Handler checks session stage:
@bot.message_handler(func=lambda m: sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
```

### Keyboard Building (InlineKeyboardMarkup)
```python
kb = InlineKeyboardMarkup()
for item in items:
    kb.add(InlineKeyboardButton(label, callback_data="cmd:action"))
kb.add(InlineKeyboardButton("Back", callback_data="back:start"))
```

### Database Pattern
- All queries use parameterized queries: `cursor.execute(query, (param1, param2))`
- Always call `conn.commit()` after INSERT/UPDATE
- Fetch results: `cursor.fetchone()[0]` or `cursor.fetchall()` → parse manually
- Use UPSERT (ON CONFLICT) for user/program to avoid duplicates

### Error Handling
- Currently minimal; add try-except around file uploads and DB ops
- Use bot.send_message with error context for user feedback

---

## Data Flow Example: Adding a Resource
1. User triggers `hub:addresource` → get_user_program_id(telegram_id)
2. Fetch courses via `get_courses_by_program(program_id)`
3. Display inline buttons for each course
4. User selects course → fetch resource_types via `get_resource_types()`
5. User selects type → session stage becomes `"awaiting_upload"`
6. User sends file → `save_resource(course_id, type_id, file_path, telegram_id)`
7. File saved to `data/uploads/{program_id}/{course_id}/{filename}`
8. DB stores resource metadata (id, course, type, uploader_id, created_at)

---

## Key Environment Variables
Required in `.env` for bot startup:
- `BOT_TOKEN` - Telegram bot token
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE`, `DB_PORT` - PostgreSQL connection

---

## Common Tasks & File Locations

| Task | File(s) |
|------|---------|
| Add new Telegram command | `app/handlers/*.py` - add `@bot.message_handler(commands=[...])` |
| Add DB query | `app/database/queries.py` - use `psycopg2` cursor pattern |
| Store uploaded file | `app/handlers/files.py` - save to `data/uploads/` |
| Add resource type | Insert into `resource_types` table in PostgreSQL |
| New feature module | Create handler in `app/handlers/` + queries in `database/queries.py` |
| Logging | Import `app/utils/logger.py` (basic logging utilities) |
| Input validation | Use `app/utils/validators.py` for course codes, usernames, etc. |

---

## Notes for AI Agents
- **Treat the entire codebase as living/incomplete** — service layer is empty by design; focus on handler-database integration
- **Session management is stateless per-user** — be careful with concurrent requests; consider migrating to Redis for production
- **Resource types are fixed/seeded** — adding new ones requires DB migration + code update
- **File uploads currently save to local disk** — scale with object storage (S3) later
- **No error handling framework** — wrap file ops and DB calls in try-except with user-friendly messages
