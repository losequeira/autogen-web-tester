# AI Chat Panel - Quick Start Guide

## Overview
The AI Chat Panel allows you to generate and modify Playwright test code through conversational AI, without needing to run full tests.

## How to Access

1. Start the AutoGen Web Tester:
   ```bash
   cd /Users/losequeira/Documents/autogen-web-tester
   python3 web_ui.py
   ```

2. Open your browser to `http://localhost:8080`

3. Look at the bottom of the screen - **"AI Chat"** is on the left side, next to the **"Generated Playwright Code"** panel on the right

## Basic Usage

### Generate New Code

**Example 1: Simple Navigation**
```
You: Generate code to navigate to google.com
```
→ AI will create complete Playwright code with navigation

**Example 2: Form Filling**
```
You: Create code to fill a login form with username "test@example.com" and password "password123"
```
→ AI will generate code with form selectors and fill commands

**Example 3: Complete Workflow**
```
You: Generate code to:
1. Navigate to example.com
2. Click the login button
3. Fill username and password
4. Submit the form
5. Take a screenshot
```
→ AI will create a complete test workflow

### Modify Existing Code

If you have code in the bottom panel (from a previous test run or chat), you can modify it:

```
You: Add error handling to catch if the login fails
```
→ AI reads your existing code and adds try-catch blocks

```
You: Add a wait statement before clicking submit
```
→ AI inserts the appropriate wait command

### Iterative Development

Build code step-by-step:

```
You: Generate code to navigate to example.com
AI: [generates navigation code]

You: Now add code to click the signup button
AI: [adds click statement]

You: Add form filling for name and email
AI: [adds form filling code]

You: Add validation to check if signup succeeded
AI: [adds validation logic]
```

## Tips & Tricks

### Be Specific
❌ "Make a test"
✅ "Generate code to test the login form on example.com with username 'test@example.com'"

### Reference Context
The AI can see code in the bottom panel:
```
You: The current code is missing error handling. Add try-catch blocks.
```

### Use Natural Language
```
You: I need to wait 2 seconds before clicking the submit button
```

### Ask for Explanations
```
You: Explain what the current code does
```

### Request Best Practices
```
You: Add proper error handling and logging to this code
```

## Common Patterns

### Navigation
```
"Navigate to https://example.com"
"Go to the homepage and then click the About link"
```

### Clicking Elements
```
"Click the button with text 'Sign Up'"
"Click the element with class 'submit-btn'"
```

### Form Filling
```
"Fill the email field with 'test@example.com'"
"Fill all form fields with test data"
```

### Waiting
```
"Wait for the page to load"
"Wait 3 seconds before clicking"
"Wait for the success message to appear"
```

### Screenshots
```
"Take a screenshot and save it as 'result.png'"
"Add a screenshot after the login succeeds"
```

### Validation
```
"Check if the page contains 'Welcome back'"
"Verify the URL changed to /dashboard"
```

## Keyboard Shortcuts

- **Ctrl + Enter**: Send message in AI Chat

## Saving Generated Code

1. After AI generates code, it appears in the bottom "Generated Playwright Code" panel
2. Click **"💾 Save Test"**
3. Enter a name for your test
4. The test is saved and can be run later **without using AI tokens**

## Clearing Chat

Click the **"Clear"** button to:
- Clear all chat messages
- Reset conversation history
- Start fresh with a new context

## Integration with Test Steps

You can use both workflows:

1. **AI Chat** (bottom left): Fast, iterative code generation without browser execution
2. **Test Steps** (top left): Full test execution with live browser preview

Both workflows output code to the **Generated Playwright Code** panel (bottom right), so you can:
- Generate code via chat → See it appear immediately on the right → Run it as a saved test
- Run test steps → See generated code on the right → Modify it via chat on the left

## Example Session

```
[User looks at bottom section - AI Chat on left, Code panel on right]

You: Generate code to test Google search
AI: I'll create code that navigates to Google and performs a search.
[Code appears in chat on left AND in code panel on right - visible side-by-side]

You: Change the search term to "Playwright testing"
AI: [Updates code with new search term - instantly visible on right]

You: Add a screenshot after search results appear
AI: [Adds screenshot command - code updates on right]

You: Perfect!
[User clicks "Save Test" in code panel and names it "Google Search Test"]

[Later, user runs the saved test without using AI tokens]
```

## Troubleshooting

### "AI is thinking..." doesn't go away
- Check your OpenAI API key in `.env`
- Check browser console for errors
- Refresh the page and try again

### Code not appearing in bottom panel
- Check that the AI response includes a code block
- Look for error messages in the chat
- Try rephrasing your request

### "Error: ..." message in chat
- Check your internet connection
- Verify OpenAI API key is valid
- Check if you have API credits remaining

## Best Practices

1. **Start Simple**: Begin with basic code, then iterate
2. **Be Specific**: Provide exact URLs, selectors, and values
3. **Test Incrementally**: Generate small pieces, verify they work
4. **Save Often**: Save working code before making major changes
5. **Use Clear Chat**: Reset when switching to a completely different task

## Next Steps

1. Try generating a simple test
2. Modify it using chat
3. Save the final version
4. Run it from the "Saved Tests" section
5. Experiment with more complex scenarios!

---

**Note**: The AI Chat uses the same OpenAI API key as the test execution agent. Each message costs a small amount of tokens. Saved tests can be run unlimited times without additional AI costs.
