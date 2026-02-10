# Quick Start - AutoGen Web Tester

## Prerequisites

1. **Python 3.10-3.13** installed
2. **OpenAI API Key** in `.env` file

## How to Run the App

### Step 1: Navigate to Project Directory
```bash
cd /Users/losequeira/Documents/autogen-web-tester
```

### Step 2: Ensure Dependencies are Installed
```bash
pip3 install -r requirements.txt
```

### Step 3: Install Playwright Browsers
```bash
playwright install chromium
```

### Step 4: Start the Server
```bash
python3 web_ui.py
```

You should see:
```
🚀 AutoGen Web Tester UI
📱 Open your browser to: http://localhost:8080
```

### Step 5: Open Your Browser
Navigate to: **http://localhost:8080**

## What You'll See

### Main Interface Layout

**Top Row:**
- **Left Panel**: Test Steps editor (write natural language tests)
- **Right Panel**: Live browser preview + Agent logs

**Bottom Row:**
- **Left Panel**: AI Chat (generate code conversationally)
- **Right Panel**: Generated Playwright Code (editable)

## Quick Test

### Option 1: Run a Test (Traditional)
1. The test steps editor already has an example loaded
2. Click **"▶ Run Test"** (top left panel)
3. Watch the browser automation happen (top right panel)
4. See generated code appear (bottom right panel)

### Option 2: Use AI Chat (New!)
1. Look at the bottom left panel (**💬 AI Chat**)
2. Type: "Generate code to navigate to google.com and search for 'Playwright'"
3. Click **"Send"** or press **Ctrl+Enter**
4. Watch AI generate code instantly in the bottom right panel
5. Click **"💾 Save Test"** to save it
6. Run it anytime from **"📚 Saved Tests"** (no AI tokens used)

## Example AI Chat Prompts

```
"Generate code to login to example.com"
"Create a form filling test with name and email"
"Add error handling to the current code"
"Add a screenshot after clicking submit"
"Generate code to test a signup flow"
```

## Stopping the Server

Press **Ctrl+C** in the terminal where the server is running.

## Troubleshooting

### "Module not found" error
```bash
pip3 install -r requirements.txt
```

### "Playwright not found" error
```bash
playwright install chromium
```

### "OpenAI API key not found" error
Create a `.env` file in the project directory:
```
OPENAI_API_KEY=your-api-key-here
```

### Port 8080 already in use
The server will automatically use the next available port, or you can specify one:
```bash
PORT=8081 python3 web_ui.py
```

## Features to Try

✅ **AI Chat Code Generation** - Bottom left panel
✅ **Test Execution** - Write steps, click Run
✅ **Live Browser Preview** - Watch automation happen
✅ **Save Tests** - Reuse without AI tokens
✅ **Edit Code** - Directly edit generated code
✅ **Record Tests** - Use Playwright codegen (local only)

## Next Steps

1. Read **AI_CHAT_QUICK_START.md** for detailed AI Chat usage
2. Read **LAYOUT.md** for interface layout details
3. Try example tests from the "Load Example" button
4. Experiment with AI Chat prompts
5. Save your favorite tests for reuse!

---

**Need Help?** Check the documentation files:
- `AI_CHAT_QUICK_START.md` - AI Chat usage guide
- `AI_CHAT_IMPLEMENTATION.md` - Technical details
- `LAYOUT.md` - Interface layout diagram
