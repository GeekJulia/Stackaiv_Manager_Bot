# Codebase Analysis Report
## Unnecessary Repetitions, Redundancy, and Issues

### 🔴 Critical Issues

#### 1. **Duplicate Functions: `get_program_info` and `get_program_by_id`**
**Location:** `app/database/queries.py` (lines 181-198 and 231-247)

**Issue:** Two nearly identical functions that do the same thing:
- `get_program_info(program_id)` - Returns: `id, level, college, program_name, user_id`
- `get_program_by_id(program_id)` - Returns: `id, level, college, name`

**Problems:**
- Inconsistent field naming: `program_name` vs `name` for the same field
- Redundant code - both query the same table with almost identical SQL
- `get_program_by_id` doesn't return `user_id` which might be needed

**Recommendation:** 
- Merge into a single function `get_program_info(program_id, include_user_id=False)`
- Standardize field name to `name` or `program_name` consistently
- Update all callers to use the unified function

**Usage:**
- `get_program_info` used in: `start.py`, `activate.py`
- `get_program_by_id` used in: `groups.py`

---

#### 2. **Empty Service Files (Unused Code)**
**Location:** 
- `app/services/files.py` (empty)
- `app/services/groups.py` (empty)
- `app/services/notes.py` (empty)

**Issue:** These files exist but are completely empty. They're not imported anywhere, suggesting they were planned but never implemented.

**Recommendation:**
- Either implement the service layer logic (recommended for better separation of concerns)
- Or delete these files if not needed

---

#### 3. **Unused Function: `start_new_registration`**
**Location:** `app/handlers/start.py` (lines 236-252)

**Issue:** Function is defined but never called anywhere in the codebase.

**Recommendation:** Remove this function as it's dead code.

---

#### 4. **Unused Helper Functions in `groups.py`**
**Location:** `app/handlers/groups.py` (lines 212-218)

**Issue:** 
- `normalize_course_code(code)` - Used only internally
- `courses_match(code1, code2)` - **Never used anywhere**

**Recommendation:** 
- Remove `courses_match` if not needed
- Consider moving `normalize_course_code` to a utility module if it's useful elsewhere

---

### 🟡 Redundancy Issues

#### 5. **Duplicate Batch Processing Logic**
**Location:** 
- `app/handlers/files.py` (lines 16-19, 254-307, 472-554)
- `app/handlers/groups.py` (lines 18-21, 270-277, 384-682)

**Issue:** Very similar batch upload logic duplicated in two files:
- Both use `batch_queues`, `batch_timers`, `batch_messages` dictionaries
- Both have similar `display_batch_prompt` functions
- Both have similar `process_all` and `cancel` handlers

**Recommendation:**
- Extract common batch processing logic to a shared utility module
- Create a reusable `BatchProcessor` class or module
- Both handlers can use the shared implementation

---

#### 6. **Repeated Course Selection Keyboard Building**
**Location:** Multiple files

**Issue:** Similar keyboard building patterns repeated in:
- `app/handlers/files.py` (lines 152-171, 311-330)
- `app/handlers/groups.py` (lines 315-332, 440-462)
- `app/handlers/notes.py` (implicit in course management)

**Recommendation:**
- Create a utility function: `build_course_keyboard(courses, callback_prefix)`
- Create a utility function: `build_resource_type_keyboard(resource_types, callback_prefix)`

---

#### 7. **Duplicate Error Handling Patterns**
**Location:** Throughout handlers

**Issue:** Repeated try/except patterns for `bot.edit_message_text` with fallback to `bot.send_message`:
```python
try:
    bot.edit_message_text(...)
except:
    bot.send_message(...)
```

**Recommendation:**
- Create a utility function: `safe_edit_or_send(bot, chat_id, message_id, text, **kwargs)`
- This pattern appears in: `files.py`, `groups.py`, `notes.py`, `activate.py`, `start.py`

---

#### 8. **Similar Duplicate Checking Logic**
**Location:** `app/database/queries.py`

**Issue:** 
- `check_duplicate_resource` (line 274) - checks duplicates for all resource types
- `check_duplicate_resource_by_type` (line 569) - checks duplicates based on type rules

**Note:** These serve different purposes, but there's some overlap. The logic could be consolidated.

**Recommendation:**
- Consider making `check_duplicate_resource` call `check_duplicate_resource_by_type` internally
- Or refactor to have a single entry point that routes to the appropriate check

---

### 🟢 Minor Issues

#### 9. **Inconsistent Field Naming**
**Location:** `app/database/queries.py`

**Issue:** 
- `get_program_info` returns `program_name`
- `get_program_by_id` returns `name`
- Both refer to the same database field

**Recommendation:** Standardize to one naming convention.

---

#### 10. **Commented Out Code**
**Location:** `app/main.py` (lines 33-35)

**Issue:** Commented out polling code that should be removed or documented.

**Recommendation:** Remove if not needed, or add a comment explaining why it's commented.

---

#### 11. **Redundant Session Cleanup**
**Location:** Multiple handlers

**Issue:** Similar session cleanup patterns repeated:
```python
file_sessions.pop(user_id, None)
file_batch_queues.pop(user_id, None)
file_batch_messages.pop(user_id, None)
```

**Recommendation:** Create a cleanup utility function for each session type.

---

### 📊 Summary Statistics

- **Duplicate Functions:** 2 major duplicates
- **Unused Code:** 3 empty files, 1 unused function, 1 unused helper
- **Redundant Patterns:** 5 major areas of repetition
- **Total Issues Found:** 11

### 🎯 Priority Recommendations

1. **High Priority:**
   - Merge `get_program_info` and `get_program_by_id`
   - Remove unused `start_new_registration` function
   - Remove or implement empty service files

2. **Medium Priority:**
   - Extract batch processing logic to shared module
   - Create keyboard building utilities
   - Create safe message editing utility

3. **Low Priority:**
   - Standardize field naming
   - Remove unused helper functions
   - Clean up commented code

---

### ✅ Positive Notes

- Good separation of concerns with handlers, services, and database layers
- Consistent use of sessions for state management
- Proper error handling in most places
- Good use of callback query handlers for interactive flows

