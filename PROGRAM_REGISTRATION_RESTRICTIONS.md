# Program Registration Restrictions Implementation

## Overview
Implemented restrictions to prevent users from registering multiple programs and to handle cases where programs already exist.

## Changes Made

### 1. Database Functions (`app/database/queries.py`)

#### Updated `get_user_program_id()`
- Now returns `None` instead of raising an exception when user has no program
- Makes it safer to check if a user has a program

#### New Functions Added:
- `user_has_program(telegram_id)` - Quick check if user already has a program
- `get_user_program_info(telegram_id)` - Get full program info for a user

### 2. Registration Flow Restrictions (`app/handlers/start.py`)

#### A. Block Users with Existing Programs from Starting Registration
**Location:** `onboard_new_program()` handler

**Behavior:**
- When user clicks "Onboard a New Program", system checks if they already have a program
- If yes, shows their existing program info (name, level, college, Program ID)
- Prevents them from starting the registration process
- Provides option to go to Program Space or re-register

**Message Shown:**
```
⚠️ You Already Have a Registered Program

📘 Program: [Program Name]
🏫 College: [College]
📊 Level: [Level]
🆔 Program ID: [ID]

You can only register one program per account.
```

#### B. Safety Check During Level Selection
**Location:** `handle_level()` handler

**Behavior:**
- Additional safety check when user selects a level
- If user somehow got past the initial check and already has a program, blocks them here
- Shows same message as above

#### C. Final Safety Check Before Program Creation
**Location:** `handle_program()` handler

**Behavior:**
- Final check before creating a program
- If user already has a program, shows their program info and blocks creation

#### D. Handle Existing Programs Created by Others
**Location:** `handle_program()` handler

**Behavior:**
When a program already exists (same level, college, program name):

1. **If created by the same user:**
   - Shows message that this is their program
   - Provides option to go to Program Space or re-register
   - This shouldn't happen normally (blocked earlier), but handles edge cases

2. **If created by a different user:**
   - Shows message that program is already registered
   - Tells them to ask course representative for Program ID
   - Shows who created the program
   - Provides option to go to Program Space or back to start

**Message Shown:**
```
ℹ️ Program Already Registered

📘 Program: [Program Name]
🏫 College: [College]
📊 Level: [Level]

This program has already been registered by someone else.

💡 What to do:
Ask your course representative or classmate for the Program ID.
Then use that Program ID to access the program space.

👤 Program created by: @[username]
```

### 3. Enhanced `/whoami` Command
**Location:** `whoami()` handler

**Improvements:**
- Now shows full program information (name, college, level) in addition to Program ID
- Better formatted output
- Handles case where user has no program gracefully

## Edge Cases Handled

### Case 1: User with Program Tries to Register Different Program
**Scenario:** User A has Program X, tries to register Program Y

**Handling:**
- Blocked at "Onboard New Program" step
- Shows their existing Program X info
- Cannot proceed to register Program Y

### Case 2: Different User Tries to Register Existing Program
**Scenario:** User A has Program X, User B tries to register Program X

**Handling:**
- User B goes through registration flow
- At program selection, system detects Program X already exists
- Shows message to ask course rep for Program ID
- Cannot create duplicate program

### Case 3: User Tries to Register Their Own Program Again
**Scenario:** User A has Program X, somehow tries to register Program X again

**Handling:**
- Blocked at "Onboard New Program" step (primary defense)
- If they somehow get past, blocked at level selection (secondary defense)
- If they somehow get past, blocked at program selection (tertiary defense)
- Shows their existing program info

### Case 4: User Without Program Tries to Register Existing Program
**Scenario:** User A has no program, tries to register Program X (created by User B)

**Handling:**
- User A goes through registration flow normally
- At program selection, system detects Program X exists
- Shows message to ask course rep for Program ID
- Cannot create duplicate program

## Security & Data Integrity

### Multiple Layers of Protection
1. **Primary Check:** At "Onboard New Program" button click
2. **Secondary Check:** At level selection
3. **Tertiary Check:** At program selection (before creation)

### Database Constraints
- `save_program()` uses `ON CONFLICT (created_by) DO UPDATE`
- This ensures one program per user at database level
- However, we prevent conflicts at application level for better UX

## User Experience Flow

### For Users with Existing Programs:
```
Click "Onboard New Program"
  ↓
⚠️ "You Already Have a Registered Program"
  ↓
Options: [Go to Program Space] [Re-register]
```

### For Users Registering Existing Programs:
```
Select Level → Select College → Select Program
  ↓
ℹ️ "Program Already Registered"
  ↓
Message: "Ask course rep for Program ID"
  ↓
Options: [Go to Program Space] [Back to Start]
```

### For Users Successfully Registering New Programs:
```
Select Level → Select College → Select Program
  ↓
✅ "Registration Complete"
  ↓
Continue to activation flow
```

## Testing Recommendations

1. **Test User with Program:**
   - User with existing program tries to click "Onboard New Program"
   - Should be blocked and shown their program info

2. **Test Duplicate Program Registration:**
   - User A creates Program X
   - User B tries to create Program X
   - User B should be told to ask for Program ID

3. **Test Normal Registration:**
   - New user registers new program
   - Should work normally

4. **Test Edge Cases:**
   - User with program somehow gets past initial checks
   - Should be caught at subsequent checkpoints

## Files Modified

1. `app/database/queries.py`
   - Updated `get_user_program_id()` to return None safely
   - Added `user_has_program()` function
   - Added `get_user_program_info()` function

2. `app/handlers/start.py`
   - Updated `onboard_new_program()` to check for existing programs
   - Updated `handle_level()` to add safety check
   - Updated `handle_program()` to handle existing programs properly
   - Updated `whoami()` to show full program info

## Notes

- All changes maintain backward compatibility
- No breaking changes to existing functionality
- Improved error messages and user guidance
- Multiple safety checks prevent edge cases

