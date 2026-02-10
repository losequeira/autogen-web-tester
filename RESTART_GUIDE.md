# 🔄 Restart Guide - Fix Current Issues

## Current Situation

You're seeing JavaScript errors because:
1. **Old JavaScript loaded** - Browser cached old version
2. **Server needs restart** - HTML changes need reload
3. **WebSocket mismatch** - Connection on wrong port

---

## ✅ Quick Fix (3 Steps)

### Step 1: Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

### Step 2: Clear Browser Cache

**Option A: Hard Refresh**
- **Chrome/Edge**: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- **Firefox**: `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)
- **Safari**: `Cmd+Option+R` (Mac)

**Option B: Clear Cache**
1. Open DevTools (`F12`)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

### Step 3: Restart the Server

```bash
cd /Users/losequeira/Documents/autogen-web-tester
python3 web_ui.py
```

**Watch for the correct port:**
```
🚀 AutoGen Web Tester UI
📱 Open your browser to: http://localhost:8080
```

Then open: **http://localhost:8080**

---

## 🎯 What You Should See

### After Restart:

**Bottom Panel:**
```
┌──────────────────────────────────────────────┐
│ 💻 Playwright Code Editor   [💬] [💾] [📋]   │
├─────────┬────────────────────────────────────┤
│ SAVED + │ (tabs will appear here)            │
│ TESTS   ├────────────────────────────────────┤
│ ───────││                                     │
│         │  No file open                      │
│         │  Open a file from the explorer     │
│         │  or use AI Chat to generate code   │
│         │                                     │
└─────────┴────────────────────────────────────┘
```

**File Explorer (Left):**
- Shows "SAVED TESTS" header
- + button to create new test
- Lists your saved tests (if any)

**AI Chat:**
- Click "💬 Chat" button
- Sidebar slides in from right
- Can drag & drop images
- Generate code conversationally

---

## 🔍 Troubleshooting

### Issue: Still seeing errors

**Solution:**
1. Close **all** browser tabs for localhost:8080
2. Clear browser cache completely:
   - Chrome: Settings → Privacy → Clear browsing data
   - Select "Cached images and files"
   - Time range: "All time"
   - Click "Clear data"
3. Restart browser
4. Open localhost:8080 in new tab

### Issue: WebSocket connection failed

**Check the port:**
- Server says: `http://localhost:8080`
- Browser goes to: `http://localhost:8080`
- They must match!

**If port is different:**
```bash
# Stop server (Ctrl+C)
# Restart without PORT env var
python3 web_ui.py
```

### Issue: No saved tests showing

**That's OK if:**
- Fresh installation
- Haven't saved any tests yet

**To create your first test:**
1. Click "💬 Chat" button
2. Type: "Generate a simple test to navigate to google.com"
3. Click "Send"
4. AI generates code
5. Click "💾 Save"
6. Enter name: "Google Test"
7. Now it appears in explorer!

### Issue: Can't create new test

**Make sure:**
1. Server is running
2. Browser cache cleared
3. No JavaScript errors in console

**To check:**
1. Press `F12` (open DevTools)
2. Go to "Console" tab
3. Should see: "Connected to server"
4. No red errors

---

## 🧪 Test the Features

### Test 1: File Explorer
```
1. Look at bottom panel
2. See "SAVED TESTS" on left
3. Click + button
4. Enter name
5. New tab opens
```

### Test 2: AI Chat
```
1. Click "💬 Chat" button
2. Sidebar slides in from right
3. Type: "Generate hello world test"
4. Click "Send"
5. Code appears in editor
```

### Test 3: Tabs
```
1. Click + to create test
2. Create another test
3. See 2 tabs open
4. Click between them
5. Tabs switch
```

### Test 4: Drag & Drop
```
1. Take a screenshot
2. Open AI Chat
3. Drag screenshot to input
4. See preview appear
5. Type: "Generate code for this"
6. Send
```

---

## 📊 Verify Everything Works

**Checklist:**
- [ ] Server starts without errors
- [ ] Browser opens to localhost:8080
- [ ] No red errors in console
- [ ] "Connected to server" message
- [ ] File explorer visible (left side)
- [ ] Click "💬 Chat" → Sidebar opens
- [ ] Can type in chat input
- [ ] Can click + to create new test
- [ ] Tabs appear when opening files

**If all checked ✅ → Everything works!**

---

## 🚀 Quick Start Fresh

**Complete reset:**

```bash
# 1. Stop server
Ctrl+C

# 2. Restart server
python3 web_ui.py

# 3. Copy the URL shown
📱 Open your browser to: http://localhost:8080

# 4. Open in NEW incognito/private window
Ctrl+Shift+N (Chrome) or Ctrl+Shift+P (Firefox)

# 5. Paste the URL
# 6. Everything should work!
```

---

## 💡 Pro Tips

**Tip 1: Use Incognito**
- No cache issues
- Fresh start every time
- Perfect for testing

**Tip 2: Keep DevTools Open**
- Press F12
- Watch for errors
- See network requests

**Tip 3: Check Server Logs**
- Watch terminal
- See API calls
- Spot issues quickly

**Tip 4: Hard Refresh Often**
- After code changes
- `Ctrl+Shift+R`
- Ensures latest version

---

## 🎯 Expected Behavior

### When Server Starts:
```
🚀 AutoGen Web Tester UI
📱 Open your browser to: http://localhost:8080
```

### When Page Loads:
```
Console:
✓ Connected to server
✓ 👋 Welcome to AutoGen Web Tester!
✓ No JavaScript errors
```

### When You Click Around:
```
✓ "💬 Chat" → Sidebar opens
✓ "+" → Prompts for name
✓ File in explorer → Opens in tab
✓ Everything smooth and responsive
```

---

## ❌ Common Mistakes

**Don't:**
- ❌ Use old browser tab
- ❌ Skip cache clearing
- ❌ Forget to restart server
- ❌ Ignore console errors

**Do:**
- ✅ Hard refresh after changes
- ✅ Check console for errors
- ✅ Restart server when needed
- ✅ Use incognito for testing

---

## 🎉 Success!

**You'll know it's working when:**
1. No errors in console
2. File explorer on left
3. AI Chat opens on right
4. Tabs work properly
5. Can create/open files

**Enjoy your VS Code-style editor!** 💻✨

---

**Need help?** Check the console for specific error messages and look for them in the troubleshooting section above.
