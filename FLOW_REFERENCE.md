# Stackaiv Bot - Updated Flow Quick Reference

## 🚀 Complete User Journey

### PHASE 1: Initial Onboarding
```
/start
  ↓
Level Selection (100, 200, 300, 400, 500)
  ↓
College Selection (CST, COE, CLDS, CMSS)
  ↓
Program Name Input
  ↓
✅ Program Registered
  ↓
Activation Screen
```

### PHASE 2A: Activation (If Payment Required)
```
Payment Screen
  ↓
"💳 Proceed with Payment"
  ↓
Email Input (validated)
  ↓
⏳ Processing payment...
  ↓
"💳 Pay Now" (Paystack link)
  ↓
"✅ Payment Complete?" (Verify)
  ↓
⏳ Verifying payment...
  ↓
✅ "Payment Verified!"
  ↓
Display course list (if any)
  ↓
➕ Add Courses | 📚 Resource Hub
```

### PHASE 2B: Activation (If Already Active)
```
Activation Screen
  ↓
✅ "Your program space is activated!"
  ↓
📚 Display registered courses:
   • MAT 111
   • CSC 111
   • PHY 101
  ↓
➕ Add Courses | 📚 Resource Hub
```

### PHASE 3: Add Courses
```
"Add Courses" button
  ↓
Send courses (comma-separated):
Format: MAT 111, CSC 111, PHY 101
  ↓
⏳ Confirming...
  ↓
"Confirm Your Courses"
Display checklist:
☐ MAT 111
☐ CSC 111
☐ PHY 101
  ↓
✅ Correct | ❌ Wrong
  ↓
⏳ Saving courses...
  ↓
Select Resource Types (checkboxes):
☐ Notes
☐ PQ Images
☐ PQ Files
☐ Textbooks
☐ Extra Study Files
☐ Code
☐ Drawings
☐ Video Files
  ↓
"✅ Done Selecting"
  ↓
"Confirm Resource Types"
Display selections:
• Notes
• Textbooks
• Code
  ↓
"✅ Yes, Proceed" | "❌ No, Change"
  ↓
⏳ Processing...
  ↓
🎉 "Setup Complete!"
Display all courses
  ↓
📚 View All | ➕ Add Resources | 📥 Get Resources | ❓ Help
```

### PHASE 4: Resource Hub (After Initial Setup)
```
Program Space Entry
  ↓
📚 *Welcome back, you are now in [Program Name] Digital Central Hub*
  ↓
Options:
  📚 View All Courses
  ➕ Add Resource
  📥 Get Resource
  ❓ Help
  ⬅️ Back
```

### PHASE 4A: Add Resource
```
"Add Resource"
  ↓
Select course:
[Course list as buttons]
  ↓
Select resource type:
Notes | PQ Images | PQ Files | Textbooks | etc.
  ↓
"📎 Send the file now"
  ↓
⏳ Uploading resource...
  ↓
[Check duplicate per resource type]
  ↓
IF Duplicate Found:
   ⚠️ "Duplicate File - file_name already exists"
   → Try again with renamed file
ELSE:
   ✅ "Resource uploaded successfully!"
```

### PHASE 4B: Get Resource
```
"Get Resource"
  ↓
Select course:
[Course list as buttons]
  ↓
Select resource type:
Notes | PQ Images | PQ Files | etc.
  ↓
📁 Available Resources displayed:
Slot 1 | file1.pdf
Slot 2 | file2.pdf
Slot 3 | file3.pdf
  ↓
"Send: Slot 1 or Slot 1, Slot 2, Slot 3 or All"
  ↓
⏳ Downloading all resources...
  ↓
✅ Documents sent
```

### PHASE 4C: Help & Support
```
"Help Info"
  ↓
📚 Display instructions
Format guidelines
  ↓
"📧 Contact Admin"
  ↓
"Describe your issue:"
  ↓
User sends message
  ↓
✅ "Message Received!"
"Admin team will review shortly"
```

---

## 📋 Input Formats

### Courses (Normalized to UPPERCASE)
```
Input: "mat 111, csc 111 | phy 101"
Output: ["MAT 111", "CSC 111", "PHY 101"]
```

### Resource Slots
```
Valid:
✅ Slot 1
✅ Slot 1, Slot 2, Slot 3
✅ Slot 1, Slot 3, Slot 5
✅ All

Invalid:
❌ Slot 1 | Slot 2 (pipe still works but comma preferred)
❌ slot 1 (case-insensitive, auto-converted)
```

---

## 🔍 Duplicate Checking Rules

### Resource Types WITH Duplicate Check:
✅ **Notes** - Prevents duplicate PDF/DOCX/PPT files
✅ **Textbooks** - Prevents duplicate PDF/DOCX files
✅ **Video Files** - Prevents duplicate video files

### Resource Types WITHOUT Duplicate Check:
❌ **PQ Images** - Allows duplicate image names
❌ **PQ Files** - Allows duplicate document names
❌ **Extra Study Files** - Allows duplicate file names
❌ **Code** - Allows duplicate code file names
❌ **Drawings** - Allows duplicate drawing names

---

## ⏳ Loading Indicators

Appear in:
- ⏳ Verifying payment...
- ⏳ Loading your courses...
- ⏳ Saving courses...
- ⏳ Processing... (saving resource types)
- ⏳ Uploading resource...
- ⏳ Downloading all resources...

---

## 🔘 Always Available Buttons

### Throughout Hub:
- ⬅️ Back (to previous screen)
- ❓ Help (access help info)
- 📧 Contact Admin (report issues)

### Cancel Option:
- Type "cancel" at any time to abort operation

---

## 🎯 Key Improvements

1. **Timeout Fixed** - No more timeout errors
2. **Loading Feedback** - Users see progress
3. **Smart Duplicates** - Per-type rules
4. **Better Navigation** - Back buttons everywhere
5. **Clean Messages** - Automatic cleanup
6. **Admin Support** - Direct contact option
7. **Format Flexibility** - Comma/pipe support
8. **Text Normalization** - Auto-uppercase courses

---

## 📱 Commands

```
/start          - Begin onboarding
/verify_payment - Manual payment verification
/cancel         - Cancel current operation
```

---

## 🔐 Session Management

Sessions auto-clear after:
- ✅ Successful completion
- ❌ Error occurrence
- 🚫 User cancellation
- ⏰ 30 minutes of inactivity (timeout)

---

## 🚨 Error Handling

### Common Errors:
```
❌ Invalid email format
   → Provide valid email (user@example.com)

❌ Duplicate File
   → Rename file for Notes/Textbooks/Videos

❌ Invalid course format
   → Use: MAT 111, CSC 111, PHY 101

❌ Invalid slot format
   → Use: Slot 1, Slot 2, Slot 3 or All

⏳ Payment Still Processing
   → Wait 1-2 minutes and verify again
```

---

**Last Updated:** February 2026
**Version:** 2.0 - Complete Flow Refactoring
