# 🌐 Web UI Guide - AutoGen Web Tester

## Quick Start

1. **Start the web server:**
   ```bash
   cd autogen-web-tester
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   python web_ui.py
   ```

2. **Open your browser:**
   Navigate to **http://localhost:8080**

3. **Write test steps:**
   - Use the left panel to write your test steps in natural language
   - Click "Load Example" for pre-made templates
   - Click "Run Test" to start automation

4. **Watch the magic happen:**
   - See live browser screenshots as automation runs
   - Monitor AI agent's reasoning in the log panel
   - View test results in real-time

## Features

### ✏️ Test Editor (Left Panel)
Write test steps in plain English:

```
1. Go to https://example.com
2. Click the "Login" button
3. Fill the form with:
   - Email: test@example.com
   - Password: mypassword
4. Click "Submit"
5. Verify page shows "Welcome"
```

### 🌐 Live Browser (Top Right)
- **Real-time screenshots** after each action
- **Timestamp** showing last action
- **Status badge** (Idle/Running/Completed)
- See exactly what the agent sees!

### 📝 Agent Log (Bottom Right)
- **AI reasoning** - See how the agent interprets your instructions
- **Tool calls** - Monitor which browser tools are being used
- **Timestamps** - Track execution timeline
- **Color-coded** messages:
  - 🔵 Blue: Info
  - 🟢 Green: Success
  - 🔴 Red: Errors
  - 🟠 Orange: Agent actions

## Example Test Templates

### Sunny.com Signup
```
Complete the signup process on https://sunny.com:

1. Go to the website
2. Click the "Sign Up" button at the header
3. Fill out the signup form with:
   - Full Name: Test User
   - Email: test+{random}@example.com
4. Submit the form by clicking the "Sign Up" button
5. Verify the success page contains:
   - Heading: "Just a couple of questions to save you time"
   - 4 bedroom option cards
```

### Google Search
```
Search on Google:

1. Go to https://google.com
2. Find the search box and type "AutoGen framework"
3. Click the search button
4. Verify results page shows search results
```

### Form Testing
```
Test a contact form:

1. Navigate to https://example.com/contact
2. Fill the contact form with:
   - Name: John Doe
   - Email: john@example.com
   - Message: This is a test message
3. Click the "Send" button
4. Verify confirmation message appears
```

## Tips

### Writing Good Test Steps

**✅ Good:**
```
1. Click the "Sign Up" button
2. Fill the email field with test@example.com
3. Verify page shows "Welcome"
```

**❌ Avoid:**
```
1. Click button (too vague - which button?)
2. Fill field (which field? what value?)
3. Check if it worked (what should it show?)
```

### Be Specific
- Use exact button text: "Sign Up" not "signup button"
- Specify form fields clearly: "Email field" or "Full Name field"
- Define expected results: "page shows 'Success'" not "check if it worked"

### Natural Language
You don't need to know CSS selectors or technical details:
- ✅ "Click the red button that says 'Submit'"
- ✅ "Fill the email field with test@example.com"
- ✅ "Verify the page title is 'Welcome'"

The AI agent automatically:
- Finds correct selectors using `find_inputs`
- Waits for page loads
- Handles dynamic content
- Takes screenshots

## Troubleshooting

### Browser doesn't appear
- Check that headless mode is `False` in `web_ui.py`
- Browser appears separate from the web UI window

### Test times out
- Increase timeout in `config.py`: `TIMEOUT = 60000` (60 seconds)
- Check website is accessible
- Verify internet connection

### Screenshots not updating
- Check browser console for WebSocket errors
- Refresh the page and try again
- Ensure Flask-SocketIO is installed

### Agent can't find element
- Make your instructions more specific
- Check if element text is exactly as you wrote
- Try describing the element differently

## Advanced Usage

### Custom Examples
Add your own examples by editing `web_ui.py`:

```python
{
    'name': 'My Custom Test',
    'url': 'https://mysite.com',
    'steps': """
Your test steps here...
"""
}
```

### Adjust Max Messages
Change max conversation length in `web_ui.py`:

```python
termination = MaxMessageTermination(max_messages=30)  # Increase if needed
```

### Change Model
Edit `config.py`:

```python
MODEL_NAME = "gpt-4o-mini"  # Cheaper, faster
# or
MODEL_NAME = "gpt-4o"  # More capable
```

## Keyboard Shortcuts

- **Ctrl/Cmd + Enter** - Run test (when focused in editor)
- **Ctrl/Cmd + K** - Clear log
- **Esc** - Close modal

## Browser Requirements

- Chrome/Chromium (installed automatically with Playwright)
- Modern web browser for UI (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- WebSocket support

## Privacy & Security

- All testing runs locally on your machine
- OpenAI API calls use your API key
- No test data is stored or transmitted to third parties
- Browser automation is sandboxed to the Playwright browser

## Next Steps

1. Try the default example test
2. Load other examples from "Load Example"
3. Write your own test for your website
4. Watch the AI agent work its magic!

---

**Need help?** Check the main README.md or open an issue on GitHub.
