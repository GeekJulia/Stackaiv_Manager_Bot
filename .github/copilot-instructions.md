# Stackaiv Bot - AI Coding Guide

## Project Overview

**Stackaiv** is a Telegram bot that manages academic resources for students organized by program, level, and course. Students register with their college and program, then share/access course notes, past questions, textbooks, and code within their program community.

**Tech Stack:** Python, Telegram Bot API (python-telegram-bot 20.3), PostgreSQL, python-dotenv

**Run Command:** `python -m app.main`

**Database Init:** `psql -U <db_user> -d <db_name> < scripts/init_db.sql`

---

## Architecture Pattern: Handlers + Services + Database

### Handler Layer (`app/handlers/`)

- **Purpose:** Telegram message/callback routing using decorators
- **Pattern:** Each handler file (start.py, notes.py, files.py, groups.py) registers callback handlers and message handlers with the bot instance
- **Session Management:** Local dicts (e.g., `notes_sessions = {}`) store per-user state keyed by `message.from_user.id`
- **Key Files:**
  - `start.py` - User onboarding: college selection (CST, COE, CLDS, CMSS) → program level (100-500) → program name
  - `notes.py` - Course registration via pipe-separated format: `"MAT 111 | CSC 111"`; resource type selection
  - `files.py` - Resource hub: upload/download resources by course + type (Notes, PQ Files, Textbooks, Extra Study Files, Code, Drawings)
  - `groups.py` - Program-based Telegram group management

### Database Layer (`app/database/`)

- **queries.py** - Direct psycopg2 connection; uses environment variables:
  - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE`, `DB_PORT`
- **Key Functions:**
  - `save_user(telegram_id, username, first_name)` - UPSERT on telegram_id
  - `save_program(level, college, program_name, user_id)` - UPSERT on created_by; one program per user
  - `get_user_program_id(telegram_id)` - Cross-table JOIN lookup
  - `save_courses(program_id, course_codes)` - Batch insert courses; returns list of course IDs
  - `get_courses_by_program(program_id)` - Returns [{id, course_code}, ...]
  - `get_resource_types()` - Returns [{id, name}] from DB
  - `save_resource(course_id, resource_type_id, file_id, file_name, uploader_id)` - Store resource metadata
  - `get_resources_by_course_and_type(course_id, resource_type_id)` - Fetch shared resources
  - `save_course_resource_types(course_id, resource_type_ids)` - Link course to resource types
  - `save_approval(resource_id, approved_by)` - Log resource approvals
  - `get_group_program_id(chat_id)` - Maps Telegram group to program_id
- **Resource Types (seeded in DB):** Notes, PQ Images, PQ Files, Textbooks, Extra Study Files, Code, Drawings

### Services Layer (`app/services/`)

- **Status:** Currently empty but structured for future business logic separation
- **Modules:** notes.py, files.py, groups.py, payments.py, storage.py
- **Future Role:** Extract queries logic, file processing, payment integration

### Data Organization

- **Program Registration:** Each user has exactly ONE program (level + college + name)
- **Courses:** Programs have many courses (e.g., CSC 101, MAT 111); stored as course_code + program_id
- **Resources:** Each resource maps to course + resource_type + uploader_id + file metadata
- **File Storage:** `data/uploads/{program_id}/{course_id}/{filename}` for user uploads; `data/temp/` for processing

---

## Critical Workflows

### User Onboarding Flow (start.py)

1. `/start` command triggers level selection (100, 200, 300, 400, 500)
2. Callback `level:{lvl}` routes to college selection (CST, COE, CLDS, CMSS)
3. College callback routes to program name input via `@bot.message_handler`
4. `save_user()` + `save_program()` writes to DB; user session stored in `user_sessions[telegram_id]`
5. `/whoami` command displays user's program info via `get_program_info(program_id)`

### Course Registration Flow (notes.py)

1. "Add Courses" callback `cmd:addcourses` sets session stage to `"awaiting_courses"`
2. User sends pipe-separated input: `"MAT 111 | CSC 111 | PHY 101"`
3. Parser: `course_codes = [c.strip().upper() for c in raw.split("|") if c.strip()]`
4. `save_courses(program_id, course_codes)` batch inserts and returns IDs
5. Session advances to `"select_resources"` stage with resource type selection via `get_resource_types()`

### Resource Hub Flow (files.py)

- `hub:courses` - Text list of all courses for user's program
- `hub:add` - Select course → select resource type → `awaiting_file` stage → file upload
- `hub:get` - Select course → select resource type → download options via `get_resources_by_course_and_type()`
- `cancel` message clears session and returns to hub

### Duplicate Prevention

- `is_file_duplicate(file_name, course_id)` checks before saving
- `save_resource()` uses `ON CONFLICT (file_id) DO NOTHING` to prevent duplicates

---

## Code Patterns & Conventions

### Session Management

```python
sessions = {}  # Global dict per handler module
sessions[user_id] = {"stage": "awaiting_input", "data": value}

# Handler checks session stage:
@bot.message_handler(func=lambda m: sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
def receive_courses(message):
    # process message
```

### Keyboard Building (InlineKeyboardMarkup)

```python
kb = InlineKeyboardMarkup()
for item in items:
    kb.add(InlineKeyboardButton(label, callback_data="cmd:action"))
kb.add(InlineKeyboardButton("Back", callback_data="back:start"))
bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
```

### Database Pattern

- All queries use parameterized queries: `cursor.execute(query, (param1, param2))`
- Always call `conn.commit()` after INSERT/UPDATE/DELETE
- Fetch results: `cursor.fetchone()[0]` for single value or `cursor.fetchall()` for lists → parse manually to dicts
- Use UPSERT (ON CONFLICT) for user/program to avoid duplicates: `ON CONFLICT (column) DO UPDATE SET ...`
- Context manager pattern: `with conn.cursor() as cursor:`

### Callback Data Convention

- Format: `{action}:{param1}:{param2}` (colon-delimited)
- Examples: `level:100`, `add:course:5`, `res:3`, `hub:add`
- Parse: `call.data.split(":")`

### Error Handling

- Currently minimal; wrap file operations and DB calls in try-except for production
- Use `bot.send_message(chat_id, "Error message")` for user feedback
- Log errors to `app/utils/logger.py` if needed

---

## Data Flow Example: Adding a Resource

1. User triggers `hub:add` → `get_user_program_id(telegram_id)` → `get_courses_by_program(program_id)`
2. Display inline buttons for each course; user selects → callback `add:course:{course_id}`
3. Fetch `get_resource_types()`; display selection; session sets `"awaiting_file"` stage
4. User sends file → `save_resource(course_id, type_id, file_id, file_name, telegram_id)`
5. `is_file_duplicate()` checks before save
6. File saved to `data/uploads/{program_id}/{course_id}/{filename}`
7. DB stores resource metadata (course_id, resource_type_id, file_id, file_name, uploader_id, created_at)

---

## Key Environment Variables

Required in `.env` for bot startup:

- `BOT_TOKEN` - Telegram bot token (get from @BotFather)
- `DB_HOST` - PostgreSQL hostname (default: localhost)
- `DB_USER` - PostgreSQL user
- `DB_PASSWORD` - PostgreSQL password
- `DB_DATABASE` - PostgreSQL database name
- `DB_PORT` - PostgreSQL port (default: 5432)

---

## Common Tasks & File Locations

| Task                     | File(s)                                                                                                        |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Add new Telegram command | `app/handlers/*.py` - add `@bot.message_handler(commands=[...])`                                               |
| Add DB query             | `app/database/queries.py` - follow psycopg2 cursor pattern with parameterized queries                          |
| Store uploaded file      | `app/handlers/files.py` - save to `data/uploads/{program_id}/{course_id}/`                                     |
| Add resource type        | Update `scripts/init_db.sql` + insert into `resource_types` table                                              |
| New feature module       | Create handler in `app/handlers/` + queries in `app/database/queries.py` + optional service in `app/services/` |
| Input validation         | Use `app/utils/validators.py` for course codes, usernames, etc.                                                |
| Logging                  | Import `app/utils/logger.py` for structured logging                                                            |

---

## Development Notes for AI Agents

- **Single connection pattern:** `app/database/queries.py` uses one global psycopg2 connection object; safe for single-threaded Telegram polling
- **Session state is per-user dictionary:** Be aware of concurrent requests; consider Redis migration for production
- **Colleges are hardcoded:** CST, COE, CLDS, CMSS in `start.py`; update there if colleges change
- **Resource types are seeded:** Adding new types requires `scripts/init_db.sql` migration + DB update + code reference
- **File uploads are local disk:** Scale with object storage (S3/GCS) later; currently saves to `data/uploads/`
- **Callback data has 64-byte limit:** Keep `callback_data` strings short; use numeric IDs instead of full names
- **On-conflict strategies vary:** Check each query for appropriate ON CONFLICT handling (UPSERT vs DO NOTHING)
- **No approval flow yet:** `save_approval()` exists but not integrated into workflows
- **Group management incomplete:** `groups.py` handler exists but full integration pending
