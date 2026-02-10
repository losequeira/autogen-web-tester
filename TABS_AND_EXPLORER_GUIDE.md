# 📂 VS Code-Style File Explorer & Tabs - User Guide

## Overview

The code editor now features a **VS Code-style interface** with:
- **File Explorer sidebar** (left) - Browse and manage saved tests
- **Tab system** (top) - Open multiple tests simultaneously
- **Resizable panels** - Customize your layout
- **Smart tracking** - Unsaved changes marked with dots

---

## 🎨 Visual Layout

```
┌────────────────────────────────────────────────────────────┐
│ 💻 Playwright Code Editor       [💬 Chat] [💾] [📋]        │
├──────────┬─────────────────────────────────────────────────┤
│ SAVED    │ 📄 Test 1 ● │ 📄 Test 2 │ 📄 Test 3 │ + │ ⊗    │
│ TESTS  + ├─────────────────────────────────────────────────┤
│ ────────││                                                  │
│ 🤖 Login │  [Code Editor Content]                          │
│ 🎥 Signup│                                                  │
│ 🤖 Form  │                                                  │
│          │                                                  │
│          │                                                  │
└──────────┴─────────────────────────────────────────────────┘
   ↑              ↑         ↑
Explorer      Active     Unsaved
Sidebar        Tab       Changes
```

---

## 📂 File Explorer (Left Sidebar)

### Features

**Header:**
- "SAVED TESTS" title
- **+ Button** - Create new blank test

**File List:**
- **🤖** icon - AI generated test
- **🎥** icon - Recorded test (codegen)
- **File name** - Click to open
- **Hover actions:**
  - **▶** - Run test
  - **🗑** - Delete test

### Actions

**Click file** → Opens in new tab (or switches if already open)
**Click ▶** → Runs the test immediately
**Click 🗑** → Deletes after confirmation
**Click +** → Creates new blank test

### Resizing

**Drag the divider** between explorer and editor:
- Min width: 150px
- Max width: 400px
- Smooth resize with blue highlight
- Cursor changes to `col-resize`

---

## 📑 Tab System (Top Bar)

### Tab Anatomy

```
┌─────────────────────┐
│ 📄 Test Name ● ×   │
└─────────────────────┘
  ↑      ↑      ↑  ↑
Icon   Name   Dirty Close
```

**Icons:**
- 📄 - File icon
- ● - Unsaved changes (blue dot)
- × - Close button

### Tab States

**Active Tab:**
- White background (#1e1e1e)
- White text (#ffffff)
- Blue underline (2px #007acc)

**Inactive Tab:**
- Dark background (transparent)
- Gray text (#858585)
- Hover → Lighter background

**Dirty Tab:**
- Blue dot after name
- Indicates unsaved changes

### Actions

**Click tab** → Switch to that file
**Click ×** → Close tab (confirms if unsaved)
**Click ⊗** → Close all tabs (top right)

### Opening Tabs

**From File Explorer:**
- Click any file → Opens in new tab
- Already open? → Switches to existing tab

**From AI Chat:**
- Generate code → Opens as new tab
- Named "AI Generated"
- Marked as unsaved (●)

**From Test Execution:**
- Run test → Opens as "Generated Test"
- Marked as unsaved (●)

**New Blank:**
- Click + in explorer → Opens blank template
- Prompts for name
- Marked as unsaved (●)

---

## 💾 Saving & Managing Files

### Save Workflow

**New File:**
1. Make changes in editor
2. Click "💾 Save"
3. Enter name in prompt
4. File saved to disk
5. Tab updates with real filename
6. Appears in file explorer
7. Blue dot (●) disappears

**Existing File:**
1. Make changes
2. Blue dot (●) appears
3. Click "💾 Save"
4. Confirms save
5. Updates file on disk
6. Blue dot disappears

**Unsaved Changes Protection:**
- Closing tab → "You have unsaved changes"
- Close all → "You have N unsaved change(s)"
- Can cancel to keep editing

### Auto-Tracking

**Changes Detection:**
- Every keystroke tracked
- Current code vs. last saved code
- Automatically marks tab as dirty
- No manual "mark as changed" needed

---

## 🔄 Workflow Examples

### Example 1: Open Multiple Tests

```
1. Click "Login Test" in explorer
   → Opens in Tab 1

2. Click "Signup Test" in explorer
   → Opens in Tab 2

3. Click "Form Test" in explorer
   → Opens in Tab 3

4. Switch between tabs to compare code
```

### Example 2: Edit and Save

```
1. Click file in explorer
2. Edit code in editor
3. Notice blue dot (●) appears in tab
4. Click "💾 Save"
5. Blue dot disappears
6. Changes persisted to disk
```

### Example 3: AI Chat Workflow

```
1. Click "💬 Chat"
2. Type: "Generate login test code"
3. AI generates code
4. New tab opens: "AI Generated ●"
5. Review code
6. Click "💾 Save"
7. Enter name: "Login Test"
8. File saved, appears in explorer
9. Tab renamed to "Login Test"
```

### Example 4: Multiple Iterations

```
1. Open "Form Test" tab
2. Click "💬 Chat"
3. Type: "Add validation"
4. Code updates in same tab
5. Tab marked dirty (●)
6. Continue editing
7. Save when ready
```

### Example 5: Compare Tests

```
1. Open "Test A" tab
2. Open "Test B" tab
3. Open "Test C" tab
4. Click between tabs to compare
5. Copy sections between files
6. Save all when done
```

---

## ⌨️ Keyboard Shortcuts

**Tab Management:**
- No built-in shortcuts yet (future enhancement)

**Planned:**
- `Ctrl+W` - Close active tab
- `Ctrl+Tab` - Next tab
- `Ctrl+Shift+Tab` - Previous tab
- `Ctrl+S` - Save active file
- `Ctrl+N` - New file

---

## 🎯 Smart Features

### 1. **Deduplication**
Click same file twice → Switches to existing tab (no duplicate)

### 2. **Dirty Tracking**
Real-time change detection, automatic ● indicator

### 3. **Confirmation Dialogs**
- Close unsaved → Confirms
- Delete file → Confirms
- Close all → Shows count of unsaved

### 4. **Auto-Update**
- Save file → Explorer refreshes
- Delete file → Tab closes + explorer updates
- Create file → Appears in explorer

### 5. **Empty State**
No tabs open → Shows helpful message:
```
No file open
Open a file from the explorer or use AI Chat to generate code
```

---

## 🎨 VS Code Similarities

| Feature | VS Code | This Editor |
|---------|---------|-------------|
| **File Explorer** | ✅ Yes | ✅ Yes |
| **Tabs** | ✅ Yes | ✅ Yes |
| **Dirty Indicator** | ✅ Dot | ✅ Dot |
| **Resizable Sidebar** | ✅ Yes | ✅ Yes |
| **Close Button** | ✅ × | ✅ × |
| **Active Underline** | ✅ Color | ✅ Blue |
| **Icons** | ✅ File type | ✅ Source type |
| **Hover Actions** | ✅ Yes | ✅ Yes |
| **Multiple Tabs** | ✅ Yes | ✅ Yes |

---

## 📱 Responsive Design

**Desktop (> 1200px):**
- Full 3-panel layout: Explorer | Editor | Chat
- All features available

**Tablet/Mobile (< 1200px):**
- Explorer collapses
- Tabs still work
- Chat overlays full screen

---

## 🚀 Usage Tips

### Tip 1: Organize Your Tests
```
Keep related tests open in tabs:
- Tab 1: Login
- Tab 2: Signup
- Tab 3: Logout

Easy to switch and compare!
```

### Tip 2: AI Iteration
```
Open a test → Ask AI to modify it
Changes apply to current tab
Save when satisfied
```

### Tip 3: Quick Run
```
Hover over file in explorer
Click ▶ to run immediately
No need to open tab first!
```

### Tip 4: Resize for Focus
```
Drag explorer to minimum (150px)
More space for code editing
Drag back when browsing files
```

### Tip 5: Close All When Done
```
Click ⊗ (Close All)
Confirms unsaved changes
Clean slate for next session
```

---

## 🔧 Technical Details

### Data Structure

```javascript
openTabs = [
    {
        id: 'test_file.json',      // Filename or temp ID
        name: 'Test Name',          // Display name
        code: 'from playwright...', // Code content
        isDirty: false              // Unsaved changes?
    }
]

activeTabId = 'test_file.json';     // Currently active tab
```

### Temporary IDs

**Patterns:**
- `new_1234567890` - New blank test
- `generated_1234567890` - From test execution
- `chat_1234567890` - From AI chat

**Behavior:**
- Marked as dirty by default
- Prompt for name on save
- Convert to real filename after save

### File Operations

**Load:**
```javascript
fetch('/api/saved-tests/filename.json')
  → Returns {name, code, created, source}
  → Opens in new tab
```

**Save:**
```javascript
fetch('/api/save-test', {code, name, source})
  → Saves to disk
  → Returns {filename}
  → Updates tab ID
```

**Delete:**
```javascript
fetch('/api/saved-tests/filename.json', {DELETE})
  → Removes from disk
  → Closes tab if open
  → Updates explorer
```

---

## 🎉 Summary

**What You Get:**
✅ VS Code-style file explorer
✅ Multiple tabs for parallel editing
✅ Unsaved changes tracking
✅ Resizable panels
✅ Quick actions (run, delete)
✅ Smart deduplication
✅ Integrated with AI Chat

**Perfect For:**
- Managing multiple test files
- Comparing different tests
- Iterative AI-powered editing
- Organizing your test suite
- Quick access to saved tests

**Try It Now!**
```bash
cd /Users/losequeira/Documents/autogen-web-tester
python3 web_ui.py
```

Open http://localhost:8080 and see the new VS Code-style interface! 🚀

---

## 📚 Related Docs

- **VSCODE_DESIGN.md** - Overall design system
- **IMAGE_UPLOAD_GUIDE.md** - Drag & drop images
- **WHATS_NEW.md** - Latest features
- **START.md** - Getting started

---

**Enjoy your professional code editing experience!** 💻✨
