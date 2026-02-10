# AutoGen Web Tester - Layout Structure

## Current Layout (Updated)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        🤖 AutoGen Web Tester                           │
│                 Write test steps, watch AI automate                     │
└────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────┬──────────────────────────────────────┐
│  ✏️ Test Steps                  │  🌐 Live Browser                     │
│                                 │                                      │
│  [Test steps textarea]          │  [Browser screenshot]                │
│                                 │                                      │
│  🎥 Record | Load Example       │  📝 Agent Log                        │
│  ⏹ Stop | ▶ Run Test           │  [Human-Readable | Technical]        │
│                                 │  [Log messages]                      │
│  ──────────────────────────     │                                      │
│  📚 Saved Tests                 │                                      │
│  [List of saved tests]          │                                      │
│                                 │                                      │
└─────────────────────────────────┴──────────────────────────────────────┘

┌─────────────────────────────────┬──────────────────────────────────────┐
│  💬 AI Chat                     │  💻 Generated Playwright Code        │
│  ───────────────────────────    │  ─────────────────────────────────   │
│                                 │                                      │
│  [Chat messages]                │  [Editable code panel]               │
│  User: Generate code...         │  from playwright.async_api...        │
│  AI: Here's the code...         │  import asyncio                      │
│  [Code preview in chat]         │                                      │
│                                 │  async def run():                    │
│  ─────────────────────────────  │      async with...                   │
│  Ask AI to generate or modify   │      await page.goto(...)            │
│  [Input textarea]               │      ...                             │
│  [Send] [Clear]                 │                                      │
│                                 │  ✖️ Cancel | 💾 Save | 📋 Copy       │
└─────────────────────────────────┴──────────────────────────────────────┘
```

## Key Features of This Layout

### Top Section (2 columns)
- **Left**: Test Steps editor + Saved Tests list
- **Right**: Live Browser preview + Agent logs

### Bottom Section (2 columns) ⭐ NEW
- **Left**: AI Chat - Conversational code generation
- **Right**: Generated Playwright Code - Editable output

## Benefits of Side-by-Side Layout

✅ **Immediate Visual Feedback**
- Type a request in AI Chat (left)
- See code appear instantly (right)
- No tab switching needed

✅ **Easy Code Review**
- Chat conversation stays visible
- Code is always visible
- Compare multiple iterations

✅ **Natural Workflow**
- Chat drives the conversation
- Code shows the results
- Both visible at once

✅ **Efficient Iteration**
- Request changes in chat
- Watch code update in real-time
- Edit code directly if needed

## Usage Flow

1. **User types in AI Chat** (bottom left)
   ```
   "Generate code to login to example.com"
   ```

2. **AI responds in chat** (bottom left)
   ```
   AI: I'll create a login automation...
   [Shows code preview in chat]
   ```

3. **Code appears in editor** (bottom right)
   ```python
   from playwright.async_api import async_playwright
   import asyncio

   async def run():
       async with async_playwright() as p:
           browser = await p.chromium.launch(headless=False)
           page = await browser.new_page()
           await page.goto("https://example.com")
           # ... login code ...
   ```

4. **User refines** (bottom left)
   ```
   "Add error handling"
   ```

5. **Code updates** (bottom right)
   - Error handling added
   - Previous code preserved
   - Changes highlighted

6. **Save & Run**
   - Click "💾 Save Test" (bottom right)
   - Run from Saved Tests (top left)
   - No AI tokens used for reruns

## Responsive Behavior

On smaller screens (< 1200px):
- Bottom section stacks vertically
- AI Chat appears above Code panel
- Maintains full functionality

## How to Run

```bash
cd /Users/losequeira/Documents/autogen-web-tester
python3 web_ui.py
```

Then open: `http://localhost:8080`

Look at the **bottom section** - AI Chat on the left, Code on the right!
