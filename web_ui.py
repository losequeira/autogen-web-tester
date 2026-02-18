"""
Web UI for AutoGen Web Tester
Provides a browser interface to write and run tests, watch browser automation live.
"""

import asyncio
import base64
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
import re

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

from browser_tool import BrowserTool
from code_agent import CodeGenerationAgent
import config
from config import Config

# Import multi-user modules
import db
from auth import init_auth
from decorators import workspace_access_required, workspace_owner_required

app = Flask(__name__)

# Apply multi-user configuration
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
print("Initializing database...")
os.makedirs(Config.USER_DATA_PATH, exist_ok=True)
os.makedirs(os.path.join(Config.USER_DATA_PATH, 'workspaces'), exist_ok=True)
init_db(Config.DATABASE_URL)

# Initialize authentication
print("Initializing authentication...")
init_auth(app)

# Cleanup database connections on app shutdown
@app.teardown_appcontext
def shutdown_session(exception=None):
    close_db_session()


# ========== WORKSPACE HELPER FUNCTIONS ==========

def get_workspace_path(workspace_id: int) -> Path:
    """Get the base path for a workspace."""
    return Path(Config.USER_DATA_PATH) / 'workspaces' / str(workspace_id)


def get_workspace_artifacts_dir(workspace_id: int) -> Path:
    """Get the artifacts directory for a workspace."""
    return get_workspace_path(workspace_id) / 'artifacts'


# ========== END WORKSPACE HELPER FUNCTIONS ==========

# Initialize code generation agent
code_agent = CodeGenerationAgent(api_key=config.OPENAI_API_KEY)

# Store active browser session and task
active_browser = None
active_task = None
stop_requested = False

# Track current AI step execution for code generation prompt
current_ai_step = None  # {'filename': '...', 'name': '...'}

# Codegen recordings tracking
active_recordings = {}
TEMP_RECORDINGS_DIR = Path(__file__).parent / 'temp_recordings'
TEMP_RECORDINGS_DIR.mkdir(exist_ok=True)



def update_test_artifacts(filename: str, artifact_dir: Path, test_status: str = 'unknown', workspace_id: int = None):
    """Update test artifact metadata in the database."""
    print(f"📼 update_test_artifacts called: filename={filename}, workspace_id={workspace_id}, status={test_status}")
    if not filename or not workspace_id:
        print(f"Warning: Cannot update artifacts without filename and workspace_id (filename={filename}, workspace_id={workspace_id})")
        return

    try:
        db.add_test_artifact(workspace_id, filename, artifact_dir, test_status)
        print(f"📼 Artifact saved successfully")
    except Exception as e:
        import traceback
        print(f"Warning: Could not update test metadata: {e}")
        traceback.print_exc()


class BrowserToolWithScreenshots(BrowserTool):
    """Extended BrowserTool that captures screenshots after each action and continuously streams."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming = False
        self.stream_task = None
        self.playwright_code = []  # Track Playwright code

    async def start_streaming(self):
        """Start continuous screenshot streaming for video-like experience."""
        self.streaming = True
        while self.streaming and self.page:
            try:
                await self._send_screenshot('stream')
                # Stream at ~40 FPS for very smooth video-like experience
                await asyncio.sleep(0.025)  # 25ms = 40 frames per second
            except Exception as e:
                if not self.streaming:
                    break
                error_msg = str(e).lower()
                # If a popup closed but original page is still alive, retry
                if "target closed" in error_msg and self.original_page and self.page != self.original_page:
                    self.page = self.original_page
                    await asyncio.sleep(0.1)
                    continue
                print(f"Stream error: {e}")
                break

    def stop_streaming(self):
        """Stop continuous streaming."""
        self.streaming = False

    async def _send_screenshot(self, action_name: str):
        """Capture and send screenshot via WebSocket (optimized for speed)."""
        try:
            # Use JPEG format with quality=40 for fast streaming at high FPS
            # Only capture viewport (not full page) for faster transmission
            screenshot_bytes = await self.page.screenshot(
                type='jpeg',
                quality=40,
                full_page=False
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            socketio.emit('screenshot', {
                'action': action_name,
                'image': screenshot_b64,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            error_msg = str(e).lower()
            if "target closed" in error_msg or "closed" in error_msg:
                # Popup closed - fall back to original page
                if self.original_page and self.page != self.original_page:
                    self.page = self.original_page
                    return
            print(f"Screenshot error: {e}")

    async def navigate(self, url: str) -> str:
        self.playwright_code.append(f'await page.goto("{url}")')
        result = await super().navigate(url)
        await self._send_screenshot('navigate')
        return result

    async def click_text(self, text: str, role: str = None) -> str:
        # Escape quotes in text
        escaped_text = text.replace('"', '\\"')
        if role == 'button':
            self.playwright_code.append(f'await page.get_by_role("button", name="{escaped_text}").click()')
        else:
            self.playwright_code.append(f'await page.get_by_text("{escaped_text}").click()')
        result = await super().click_text(text, role)
        await self._send_screenshot('click_text')
        return result

    async def fill_form(self, selector: str, value: str) -> str:
        # Escape quotes in selector and value
        escaped_selector = selector.replace('"', '\\"')
        escaped_value = value.replace('"', '\\"')
        self.playwright_code.append(f'await page.fill("{escaped_selector}", "{escaped_value}")')
        result = await super().fill_form(selector, value)
        await self._send_screenshot('fill_form')
        return result

    async def click(self, selector: str) -> str:
        # Escape quotes in selector
        escaped_selector = selector.replace('"', '\\"')
        self.playwright_code.append(f'await page.click("{escaped_selector}")')
        result = await super().click(selector)
        await self._send_screenshot('click')
        return result

    async def click_and_wait_for_popup(self, selector: str) -> str:
        escaped_selector = selector.replace('"', '\\"')
        self.playwright_code.append(f'async with original_page.expect_popup() as popup_info:')
        self.playwright_code.append(f'    await original_page.click("{escaped_selector}")')
        self.playwright_code.append(f'page = await popup_info.value')
        result = await super().click_and_wait_for_popup(selector)
        await self._send_screenshot('click_and_wait_for_popup')
        return result

    async def click_text_and_wait_for_popup(self, text: str) -> str:
        escaped_text = text.replace('"', '\\"')
        self.playwright_code.append(f'async with original_page.expect_popup() as popup_info:')
        self.playwright_code.append(f'    await original_page.click("text={escaped_text}")')
        self.playwright_code.append(f'page = await popup_info.value')
        result = await super().click_text_and_wait_for_popup(text)
        await self._send_screenshot('click_text_and_wait_for_popup')
        return result

    async def switch_to_original_page(self) -> str:
        self.playwright_code.append(f'page = original_page')
        result = await super().switch_to_original_page()
        await self._send_screenshot('switch_to_original_page')
        return result

    async def close_current_page(self) -> str:
        self.playwright_code.append(f'await page.close()')
        self.playwright_code.append(f'page = original_page')
        result = await super().close_current_page()
        await self._send_screenshot('close_current_page')
        return result


def generate_playwright_code(actions):
    """Generate complete Playwright test code from actions."""
    import re

    # Check if any action contains an email pattern like test+<random>@example.com
    has_random_email = any(
        re.search(r'test\+[a-z0-9]+@example\.com', action)
        for action in actions
    )

    # Check if any action uses popup handling
    has_popup = any(
        'original_page' in action or 'popup_info' in action
        for action in actions
    )

    code_lines = [
        "from playwright.async_api import async_playwright",
        "import asyncio"
    ]

    # Add random/string imports if needed
    if has_random_email:
        code_lines.extend([
            "import random",
            "import string"
        ])

    code_lines.extend([
        "",
        "async def run():",
        "    async with async_playwright() as p:",
        "        browser = await p.chromium.launch(headless=False)",
        "        page = await browser.new_page()",
    ])

    if has_popup:
        code_lines.append("        original_page = page")

    code_lines.append("")

    # Add random email generator if needed
    if has_random_email:
        code_lines.extend([
            "        # Generate random 10-character string for unique email",
            "        random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))",
            "        random_email = f\"test+{random_chars}@example.com\"",
            ""
        ])

    # Add tracked actions, replacing hardcoded emails with random_email variable
    for action in actions:
        if has_random_email and 'test+' in action and '@example.com' in action:
            # Replace the hardcoded email with the variable
            modified_action = re.sub(
                r'"test\+[a-z0-9]+@example\.com"',
                'random_email',
                action
            )
            code_lines.append(f"        {modified_action}")
        elif action.startswith('    '):
            # Indented popup sub-action (e.g. inside async with block)
            code_lines.append(f"        {action}")
        else:
            code_lines.append(f"        {action}")

    code_lines.extend([
        "",
        "        await browser.close()",
        "",
        "asyncio.run(run())"
    ])

    return "\n".join(code_lines)


def convert_codegen_to_saved_format(codegen_output: str) -> str:
    """
    Convert Playwright codegen output to our standard test format.

    Codegen generates:
        async def run(playwright: Playwright) -> None:
            browser = await playwright.chromium.launch(...)
            page = await browser.new_page()
            ...actions...
            await browser.close()

    We want:
        async def run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(...)
                page = await browser.new_page()
                ...actions...
                await browser.close()
    """
    try:
        # Extract actions between page creation and browser close
        lines = codegen_output.split('\n')
        actions = []
        capture = False

        for line in lines:
            # Start capturing after "page = await browser.new_page()"
            if 'page = await browser.new_page()' in line or 'page = await context.new_page()' in line:
                capture = True
                continue

            # Stop capturing at browser.close() or context.close()
            if capture and ('await browser.close()' in line or 'await context.close()' in line):
                break

            # Capture action lines (skip empty lines and main() function)
            if capture and line.strip() and 'async def main' not in line and 'asyncio.run' not in line and 'async with async_playwright()' not in line:
                # Remove leading indentation (usually 4 spaces from codegen)
                clean_line = line.lstrip()
                if clean_line and not clean_line.startswith('#'):
                    actions.append(clean_line)

        # Build our standard format
        code_lines = [
            "from playwright.async_api import async_playwright",
            "import asyncio",
            "",
            "async def run():",
            "    async with async_playwright() as p:",
            "        browser = await p.chromium.launch(headless=False)",
            "        page = await browser.new_page()",
            ""
        ]

        # Add captured actions with proper indentation (8 spaces)
        for action in actions:
            code_lines.append(f"        {action}")

        # Add closing
        code_lines.extend([
            "",
            "        await browser.close()",
            "",
            "asyncio.run(run())"
        ])

        return "\n".join(code_lines)

    except Exception as e:
        # If parsing fails, return a commented version of the original with a warning
        return f"# Warning: Could not parse codegen output automatically\n# Error: {str(e)}\n# Original output:\n\n{codegen_output}"


def run_codegen_process(recording_id: str, url: str, output_file: str, test_name: str = None):
    """
    Run Playwright codegen subprocess and emit results when complete.
    This runs in a background thread.
    """
    try:
        # Emit starting status
        socketio.emit('codegen_status', {
            'recording_id': recording_id,
            'status': 'recording',
            'message': f'🎥 Recording started for {url}'
        })

        # Start Playwright codegen process
        process = subprocess.Popen(
            [
                'playwright', 'codegen',
                '--target', 'python-async',
                '--output', output_file,
                '--browser', 'chromium',
                url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Store process in active recordings
        active_recordings[recording_id] = {
            'process': process,
            'output_file': output_file,
            'url': url,
            'test_name': test_name
        }

        # Wait for user to close the window (blocking)
        return_code = process.wait()

        # Check if process completed successfully
        if return_code == 0:
            # Read generated code
            with open(output_file, 'r') as f:
                codegen_output = f.read()

            # Convert to our format
            converted_code = convert_codegen_to_saved_format(codegen_output)

            # Emit completion event
            socketio.emit('codegen_complete', {
                'recording_id': recording_id,
                'code': converted_code,
                'name': test_name or f'Recorded Test - {url}'
            })

            socketio.emit('log', {
                'type': 'success',
                'message': f'✅ Recording completed! Code generated successfully.'
            })
        else:
            # Process failed
            stderr_output = process.stderr.read().decode('utf-8') if process.stderr else 'Unknown error'
            socketio.emit('codegen_error', {
                'recording_id': recording_id,
                'message': f'Recording failed: {stderr_output}'
            })

            socketio.emit('log', {
                'type': 'error',
                'message': f'❌ Recording failed: {stderr_output}'
            })

    except FileNotFoundError:
        # Playwright not installed
        socketio.emit('codegen_error', {
            'recording_id': recording_id,
            'message': 'Playwright not found. Please install: pip install playwright && playwright install chromium'
        })
        socketio.emit('log', {
            'type': 'error',
            'message': '❌ Playwright not found. Run: pip install playwright && playwright install chromium'
        })

    except Exception as e:
        socketio.emit('codegen_error', {
            'recording_id': recording_id,
            'message': f'Error during recording: {str(e)}'
        })
        socketio.emit('log', {
            'type': 'error',
            'message': f'❌ Recording error: {str(e)}'
        })

    finally:
        # Clean up
        if recording_id in active_recordings:
            del active_recordings[recording_id]

        # Clean up temp file
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
        except Exception:
            pass


async def run_test_async(task: str, test_filename: str = None, workspace_id: int = None):
    """Run the test with live updates."""
    global active_browser, stop_requested, current_ai_step

    stop_requested = False  # Reset stop flag
    socketio.emit('log', {'type': 'info', 'message': 'Initializing browser...'})

    # Create artifacts directory if this is an AI step test with filename
    artifact_dir = None
    video_dir = None
    saved_test_filename = test_filename  # Save filename before current_ai_step gets reset
    saved_workspace_id = workspace_id
    test_status = None  # Track test status for artifact metadata

    # Get filename and workspace_id from current_ai_step if not provided
    if current_ai_step:
        if not saved_test_filename:
            saved_test_filename = current_ai_step.get('filename')
        if not saved_workspace_id:
            saved_workspace_id = current_ai_step.get('workspace_id')

    if saved_test_filename:
        from pathlib import Path
        test_name = Path(saved_test_filename).stem
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Use workspace-scoped directory if workspace_id provided
        if saved_workspace_id:
            workspace_path = get_workspace_path(saved_workspace_id)
            artifact_dir = workspace_path / "test_artifacts" / test_name / timestamp
        else:
            # Fallback to global directory
            artifact_dir = Path(__file__).parent / "test_artifacts" / test_name / timestamp

        artifact_dir.mkdir(parents=True, exist_ok=True)
        video_dir = str(artifact_dir)
        socketio.emit('log', {'type': 'info', 'message': f'📹 Video recording enabled to: {video_dir}'})

    try:
        # Initialize browser with screenshots and optional video recording
        async with BrowserToolWithScreenshots(
            headless=True,
            timeout=config.TIMEOUT,
            record_video_dir=video_dir,
            record_har=True if video_dir else False
        ) as browser:
            active_browser = browser

            socketio.emit('log', {'type': 'info', 'message': 'Browser initialized'})

            # Start continuous video-like streaming
            asyncio.create_task(browser.start_streaming())

            # Create tools
            navigate_tool = FunctionTool(
                browser.navigate,
                description="Navigate to a URL. Provide the full URL as a string."
            )

            fill_tool = FunctionTool(
                browser.fill_form,
                description="Fill a form field. Provide CSS selector and value."
            )

            click_tool = FunctionTool(
                browser.click,
                description="Click an element. Provide CSS selector."
            )

            click_text_tool = FunctionTool(
                browser.click_text,
                description="Click element by visible text. Parameters: text (required), role (optional: 'button')."
            )

            get_text_tool = FunctionTool(
                browser.get_text,
                description="Get text content from an element. Provide CSS selector."
            )

            screenshot_tool = FunctionTool(
                browser.screenshot,
                description="Take a screenshot. Provide file path like 'screenshot.png'"
            )

            get_content_tool = FunctionTool(
                browser.get_page_content,
                description="Get the current page content and URL for context."
            )

            get_url_tool = FunctionTool(
                browser.get_current_url,
                description="Get the current page URL."
            )

            find_inputs_tool = FunctionTool(
                browser.find_inputs,
                description="Find all input fields on page with their exact selectors."
            )

            get_html_tool = FunctionTool(
                browser.get_html,
                description="Get the raw HTML of the page."
            )

            click_popup_tool = FunctionTool(
                browser.click_and_wait_for_popup,
                description="Click a CSS selector that opens a popup/new tab (e.g. OAuth), then switch to it. All subsequent actions will target the popup."
            )

            click_text_popup_tool = FunctionTool(
                browser.click_text_and_wait_for_popup,
                description="Click an element by visible text that opens a popup/new tab (e.g. 'Sign in with Google'), then switch to it. All subsequent actions will target the popup."
            )

            switch_to_original_tool = FunctionTool(
                browser.switch_to_original_page,
                description="Switch back to the original/main page after finishing with a popup. Call this after OAuth or popup flow is complete."
            )

            close_popup_tool = FunctionTool(
                browser.close_current_page,
                description="Close the current popup page and switch back to the original page. Use if popup did not auto-close."
            )

            # Create model client
            socketio.emit('log', {'type': 'info', 'message': 'Initializing AI model...'})

            model_client = OpenAIChatCompletionClient(
                model=config.MODEL_NAME,
                api_key=config.OPENAI_API_KEY
            )

            # System message
            system_message = """You are a web testing automation agent. Your job is to interact with websites using the provided browser tools.

CRITICAL: You MUST follow the user's test steps EXACTLY as written. Do NOT skip validation steps. Do NOT ignore errors.
CRITICAL: When a step says to click text like "Sign in", you MUST click EXACTLY "Sign in" - NOT "Sign Up", NOT "Sign In With Google", NOT any variation. Match the EXACT text the user wrote. Case and wording matter.

BEFORE YOU DO ANYTHING ELSE - READ THIS:
- When filling a form field, you MUST use THREE separate actions:
  1. FIRST: Call find_inputs to identify the exact selector
  2. SECOND: Call click(selector) to click the field
  3. THIRD: Call fill_form(selector, value) to fill ONLY that field's value
- NEVER put multiple values in one field
- NEVER skip the click step if the user says "Click the field"
- After EACH fill_form call, verify it worked by checking page content

TOOL USAGE RULES (CRITICAL - ALWAYS FOLLOW):

1. **Clicking Buttons/Links:**
   - For ANY button or link with visible text (e.g., "Sign Up", "Submit", "Login"), ALWAYS use click_text with the exact text
   - When clicking submit buttons, use role='button' parameter to avoid clicking header/navigation links with same text
   - Example: click_text(text='Sign Up', role='button') for submit buttons
   - Only use click(selector) as last resort if click_text fails

2. **Filling Forms - MANDATORY 3-STEP PROCESS:**

   For EVERY form field you fill, you MUST do ALL THREE steps:

   STEP 1: Call find_inputs
   - This is NOT optional
   - This gives you the EXACT selector for each field
   - Look at the output carefully to identify which field is which

   STEP 2: Call click(selector)
   - Use the EXACT selector from find_inputs
   - Example: click('input[name="fullName"]')
   - This focuses the field

   STEP 3: Call fill_form(selector, value)
   - Use the SAME selector from step 2
   - Put ONLY the value for THIS field
   - Example: fill_form('input[name="fullName"]', 'John Doe')
   - DO NOT put email in the name field
   - DO NOT concatenate multiple values

   EXAMPLE for Full Name field:
   - find_inputs → see [0] input name="fullName", placeholder="Full Name"
   - click('input[name="fullName"]')
   - fill_form('input[name="fullName"]', 'John Doe')

   EXAMPLE for Email field:
   - (find_inputs already called above)
   - click('input[name="email"]')
   - fill_form('input[name="email"]', 'test@example.com')

   CRITICAL RULE - ONE FIELD AT A TIME:
   - Complete ALL 3 steps for ONE field before moving to the next field
   - Do NOT click multiple fields before filling them
   - Do NOT go back and re-fill a field unless validation explicitly failed
   - Sequence: find_inputs → click field1 → fill field1 → click field2 → fill field2

   INSTANT FAIL if you:
   - Skip find_inputs
   - Skip the click step when user says "Click the field"
   - Put wrong value in wrong field
   - Concatenate values like "John Doetest@example.com"
   - Click field2 before filling field1
   - Fill the same field multiple times without a validation failure

3. **Random Values:**
   - When task says "random 10 characters", generate a random 10-character alphanumeric string (lowercase letters and numbers)
   - Example: "test+(random 10 characters)@example.com" → "test+a7f3k9m2p1@example.com"
   - Generate a NEW random string each time you run the test

4. **Navigation:**
   - Use navigate(url) to go to pages
   - After navigation, wait for page to load (automatic)

5. **Verification (CRITICAL - Read Carefully):**
   - PRIMARY: Use get_page_content to check if the expected content is visible on the page
   - SECONDARY: Use get_current_url to check if URL changed (optional - some sites use SPAs)
   - The presence of expected content is MORE IMPORTANT than URL changes
   - Some modern websites update content without changing URLs (Single Page Applications)

6. **Form Filling Verification (MANDATORY):**
   - After filling ALL form fields, you MUST call get_page_content to verify what was actually filled
   - Check that EACH field contains the CORRECT value and ONLY that value
   - If ANY field contains concatenated values (e.g., "Alice Bobtest@email.com"), check if user's steps say "go back to step X"
   - If user says "go back to step X", retry that step up to 2 times before failing
   - If the user's test steps include validation steps (e.g., "Check if full name input has a value and it is correct. If not go back to step 3"), you MUST:
     1. Execute the validation check
     2. If it fails, go back to the specified step and retry
     3. If it fails after 2 retries, THEN report TEST FAILED
   - DO NOT proceed to form submission if validation fails
   - DO NOT ignore retry instructions in the user's steps
   - ONLY report TEST FAILED if retries are exhausted or no retry instruction exists

7. **Form Submission Workflow:**
   - BEFORE clicking submit, verify ALL fields are filled correctly (see section 6)
   - If you see validation error messages (e.g., "Please enter a valid email address"), DO NOT click submit
   - Fix the errors first, THEN submit
   - When you click a submit button (role='button'), the system automatically waits 6 seconds
   - After this wait, check get_page_content to verify the expected success content is visible
   - IMPORTANT: If the expected content is present, the test PASSED - even if the URL didn't change
   - URL changes are a bonus confirmation, not a requirement
   - Only fail if the expected content is NOT found after waiting

8. **Test Completion (CRITICAL):**
   - After completing ALL test steps AND all verifications, you MUST provide a final status report
   - If all steps succeeded and all verifications passed, respond with: "TEST PASSED: [brief summary]"
   - If any step failed or verification didn't match, respond with: "TEST FAILED: [what went wrong]"
   - If there was an error during execution, respond with: "TEST ERROR: [error details]"
   - After providing the status, STOP - do not continue or ask for more instructions
   - Your final message should be the test status report

9. **Popup/OAuth Flows (e.g. Google Sign-In):**
   - When a button opens a popup or new tab (like "Sign in with Google"), use click_text_and_wait_for_popup(text) instead of click_text
   - This switches ALL subsequent tool calls to target the popup window automatically
   - Complete the OAuth flow in the popup (fill email, click Next, fill password, click Next)
   - After the popup closes or OAuth completes, call switch_to_original_page() to go back to the main page
   - If the popup did not auto-close, call close_current_page() first, then switch_to_original_page() is automatic
   - Example Google OAuth flow:
     1. click_text_and_wait_for_popup("Sign in with Google")
     2. fill_form('input[type="email"]', 'user@gmail.com')
     3. click_text("Next")
     4. fill_form('input[type="password"]', 'password123')
     5. click_text("Next")
     6. switch_to_original_page()
     7. Verify dashboard/authenticated state

Available tools:
- navigate, click_text, click, fill_form, find_inputs, get_page_content, get_current_url, get_text, screenshot, get_html
- click_and_wait_for_popup, click_text_and_wait_for_popup, switch_to_original_page, close_current_page

These rules apply to ALL tasks. Users will give you natural language instructions - translate them using these rules."""

            # Create agent
            agent = AssistantAgent(
                name="web_tester",
                model_client=model_client,
                tools=[
                    navigate_tool,
                    click_text_tool,
                    click_tool,
                    fill_tool,
                    find_inputs_tool,
                    get_content_tool,
                    get_url_tool,
                    get_text_tool,
                    screenshot_tool,
                    get_html_tool,
                    click_popup_tool,
                    click_text_popup_tool,
                    switch_to_original_tool,
                    close_popup_tool
                ],
                system_message=system_message
            )

            socketio.emit('log', {'type': 'info', 'message': 'Starting test execution...'})

            # Create team
            termination = MaxMessageTermination(max_messages=30)
            team = RoundRobinGroupChat([agent], termination_condition=termination)

            # Run and stream results
            async for message in team.run_stream(task=task):
                # Check if stop was requested
                if stop_requested:
                    socketio.emit('log', {'type': 'error', 'message': 'Test stopped by user'})
                    # Only send playwright_code for regular tests (not AI steps)
                    if not current_ai_step:
                        playwright_code = generate_playwright_code(browser.playwright_code)
                        socketio.emit('playwright_code', {'code': playwright_code})
                    socketio.emit('test_complete', {'status': 'stopped'})
                    current_ai_step = None  # Reset on stop
                    return

                # Send each message to frontend
                msg_data = {
                    'type': type(message).__name__,
                    'content': str(message),
                    'timestamp': datetime.now().isoformat()
                }

                socketio.emit('agent_message', msg_data)

                # Parse and send structured log
                if hasattr(message, 'source'):
                    socketio.emit('log', {
                        'type': 'agent_action',
                        'message': f"[{message.source}] {str(message)[:200]}..."
                    })

                # Check if test completed with status
                message_content = str(message)
                if 'TEST PASSED:' in message_content:
                    test_status = 'passed'
                    # Generate Playwright code
                    playwright_code = generate_playwright_code(browser.playwright_code)
                    socketio.emit('log', {'type': 'success', 'message': 'Test completed: PASSED'})

                    # If this was an AI step, prompt user to save generated code
                    if current_ai_step:
                        socketio.emit('ai_step_complete_with_code', {
                            'status': 'success',
                            'code': playwright_code,
                            'ai_step_name': current_ai_step['name'],
                            'ai_step_filename': current_ai_step['filename']
                        })
                        current_ai_step = None  # Reset after prompting
                    else:
                        # Regular test - send code and complete event
                        socketio.emit('playwright_code', {'code': playwright_code})
                        socketio.emit('test_complete', {'status': 'success'})
                    break
                elif 'TEST FAILED:' in message_content:
                    test_status = 'failed'
                    socketio.emit('log', {'type': 'error', 'message': 'Test completed: FAILED'})
                    # Only send playwright_code for regular tests (not AI steps)
                    if not current_ai_step:
                        playwright_code = generate_playwright_code(browser.playwright_code)
                        socketio.emit('playwright_code', {'code': playwright_code})
                    socketio.emit('test_complete', {'status': 'error'})
                    current_ai_step = None  # Reset on failure
                    break
                elif 'TEST ERROR:' in message_content:
                    test_status = 'error'
                    socketio.emit('log', {'type': 'error', 'message': 'Test completed: ERROR'})
                    # Only send playwright_code for regular tests (not AI steps)
                    if not current_ai_step:
                        playwright_code = generate_playwright_code(browser.playwright_code)
                        socketio.emit('playwright_code', {'code': playwright_code})
                    socketio.emit('test_complete', {'status': 'error'})
                    current_ai_step = None  # Reset on error
                    break

            # If loop ended naturally without status (hit max messages)
            if not stop_requested and test_status is None:
                socketio.emit('log', {'type': 'error', 'message': 'Test ended without clear status (may have hit message limit)'})
                # Only send playwright_code for regular tests (not AI steps)
                if not current_ai_step:
                    playwright_code = generate_playwright_code(browser.playwright_code)
                    socketio.emit('playwright_code', {'code': playwright_code})
                socketio.emit('test_complete', {'status': 'error', 'message': 'Test timed out or hit message limit'})
                current_ai_step = None  # Reset on timeout

    except Exception as e:
        error_msg = f"Error during test execution: {str(e)}"
        socketio.emit('log', {'type': 'error', 'message': error_msg})
        socketio.emit('test_complete', {'status': 'error', 'message': str(e)})
        test_status = 'error'  # Set for artifact tracking
        current_ai_step = None  # Reset on exception
    finally:
        # Stop streaming when test completes
        if active_browser:
            active_browser.stop_streaming()
        active_browser = None

        # Update test artifacts if video recording was enabled
        if artifact_dir and saved_test_filename:
            # Give the browser time to finalize the video
            import time
            time.sleep(2)
            update_test_artifacts(
                saved_test_filename,
                artifact_dir,
                test_status or 'unknown',
                workspace_id=saved_workspace_id
            )
            # Tell frontend to refresh now that artifacts are saved
            socketio.emit('artifacts_updated', {'filename': saved_test_filename})


def run_test_sync(task: str, test_filename: str = None, workspace_id: int = None):
    """Wrapper to run async test in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_test_async(task, test_filename, workspace_id))
    finally:
        # Properly shutdown the event loop to avoid crashes
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Run loop until all tasks are cancelled
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


def run_playwright_code(code: str):
    """Execute saved Playwright code directly (no AI)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Execute the code
        exec_globals = {'socketio': socketio, 'emit': emit}
        exec(code.replace('asyncio.run(run())', ''), exec_globals)

        # Run the async function
        if 'run' in exec_globals:
            loop.run_until_complete(exec_globals['run']())
            socketio.emit('log', {'type': 'success', 'message': '✅ Saved test completed successfully!'})
            socketio.emit('test_complete', {'status': 'success'})
        else:
            socketio.emit('log', {'type': 'error', 'message': 'Error: Could not find run() function in saved code'})
            socketio.emit('test_complete', {'status': 'error'})

    except Exception as e:
        error_msg = f'Error executing saved test: {str(e)}'
        socketio.emit('log', {'type': 'error', 'message': error_msg})
        socketio.emit('test_complete', {'status': 'error', 'message': str(e)})
    finally:
        # Properly shutdown the event loop
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


def run_playwright_code_with_streaming(code: str, filename: str = None, workspace_id: int = None):
    """Execute Playwright code with automatic screenshot streaming to browser sidebar."""
    global stop_requested
    stop_requested = False  # Reset stop flag at the start of execution

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create artifacts directory for this test run if filename provided
    artifact_dir = None
    video_dir = None
    test_status = None  # Track test status for artifact metadata
    if filename:
        print(f"🎬 Filename provided: {filename}, workspace_id: {workspace_id}")
        from pathlib import Path
        from datetime import datetime
        test_name = Path(filename).stem
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Use workspace-scoped directory if workspace_id provided
        if workspace_id:
            workspace_path = get_workspace_path(workspace_id)
            artifact_dir = workspace_path / "test_artifacts" / test_name / timestamp
        else:
            # Fallback to global directory
            artifact_dir = Path(__file__).parent / "test_artifacts" / test_name / timestamp

        artifact_dir.mkdir(parents=True, exist_ok=True)
        video_dir = str(artifact_dir)
        print(f"📹 Video directory created: {video_dir}")
        socketio.emit('log', {'type': 'info', 'message': f'📹 Video recording enabled to: {video_dir}'})
    else:
        print("⚠️  No filename provided - video recording disabled")

    async def execute_with_auto_streaming():
        """Execute code with automatic screenshot streaming after each action."""
        from playwright.async_api import async_playwright

        # Screenshot helper that will be available in user's code
        async def send_screenshot(page, action_name='action'):
            """Capture and send screenshot to browser sidebar."""
            try:
                print(f"📸 Capturing screenshot for action: {action_name}")
                screenshot_bytes = await page.screenshot(
                    type='jpeg',
                    quality=40,
                    full_page=False
                )
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                print(f"✅ Screenshot captured ({len(screenshot_b64)} bytes), sending to browser...")
                socketio.emit('screenshot', {
                    'action': action_name,
                    'image': screenshot_b64,
                    'timestamp': datetime.now().isoformat()
                })
                print(f"✅ Screenshot sent for action: {action_name}")
            except Exception as e:
                print(f"❌ Screenshot error: {e}")
                import traceback
                traceback.print_exc()

        # Page wrapper that automatically captures screenshots
        class PageWrapper:
            """Wraps Playwright Page to automatically capture screenshots after actions."""

            def __init__(self, page):
                self._page = page
                self._streaming = False
                self._stream_task = None

            async def _start_streaming(self):
                """Start continuous screenshot streaming."""
                global stop_requested
                self._streaming = True
                while self._streaming:
                    try:
                        # Check if stop was requested
                        if stop_requested:
                            print("⏹ Stop requested - cancelling streaming")
                            raise asyncio.CancelledError("Test stopped by user")
                        await send_screenshot(self._page, 'stream')
                        await asyncio.sleep(0.1)  # 10 FPS
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        break

            def _stop_streaming(self):
                """Stop streaming."""
                self._streaming = False
                if self._stream_task:
                    self._stream_task.cancel()

            async def goto(self, url, **kwargs):
                """Navigate and capture screenshot."""
                global stop_requested
                if stop_requested:
                    print("⏹ Stop requested - cancelling goto action")
                    raise asyncio.CancelledError("Test stopped by user")
                print(f"🌐 PageWrapper.goto() called for URL: {url}")
                result = await self._page.goto(url, **kwargs)
                await send_screenshot(self._page, 'navigate')
                # Start streaming after first navigation
                if not self._stream_task:
                    print("📹 Starting continuous screenshot streaming at 10 FPS...")
                    self._stream_task = asyncio.create_task(self._start_streaming())
                return result

            async def click(self, selector, **kwargs):
                """Click and capture screenshot."""
                global stop_requested
                if stop_requested:
                    print("⏹ Stop requested - cancelling click action")
                    raise asyncio.CancelledError("Test stopped by user")
                print(f"👆 PageWrapper.click() called for selector: {selector}")
                result = await self._page.click(selector, **kwargs)
                await send_screenshot(self._page, 'click')
                return result

            async def fill(self, selector, value, **kwargs):
                """Fill and capture screenshot."""
                global stop_requested
                if stop_requested:
                    print("⏹ Stop requested - cancelling fill action")
                    raise asyncio.CancelledError("Test stopped by user")
                print(f"✍️ PageWrapper.fill() called for selector: {selector}")
                result = await self._page.fill(selector, value, **kwargs)
                await send_screenshot(self._page, 'fill')
                return result

            async def type(self, selector, text, **kwargs):
                """Type and capture screenshot."""
                global stop_requested
                if stop_requested:
                    print("⏹ Stop requested - cancelling type action")
                    raise asyncio.CancelledError("Test stopped by user")
                result = await self._page.type(selector, text, **kwargs)
                await send_screenshot(self._page, 'type')
                return result

            async def press(self, selector, key, **kwargs):
                """Press key and capture screenshot."""
                global stop_requested
                if stop_requested:
                    print("⏹ Stop requested - cancelling press action")
                    raise asyncio.CancelledError("Test stopped by user")
                result = await self._page.press(selector, key, **kwargs)
                await send_screenshot(self._page, 'press')
                return result

            async def screenshot(self, **kwargs):
                """Take screenshot and send to sidebar."""
                result = await self._page.screenshot(**kwargs)
                await send_screenshot(self._page, 'screenshot')
                return result

            async def close(self):
                """Stop streaming and close page."""
                self._stop_streaming()
                return await self._page.close()

            def __getattr__(self, name):
                """Forward all other attributes to the real page."""
                return getattr(self._page, name)

        # Browser context wrapper
        class ContextWrapper:
            def __init__(self, context):
                self._context = context

            async def new_page(self):
                """Create new page with screenshot wrapper."""
                page = await self._context.new_page()
                return PageWrapper(page)

            def __getattr__(self, name):
                return getattr(self._context, name)

        # Browser wrapper
        class BrowserWrapper:
            def __init__(self, browser, default_context=None):
                self._browser = browser
                self._default_context = default_context
                self._contexts = []

            async def new_page(self):
                """Create new page with screenshot wrapper."""
                # If we have a default context (with video recording), use it
                if self._default_context:
                    page = await self._default_context.new_page()
                    return PageWrapper(page)
                else:
                    page = await self._browser.new_page()
                    return PageWrapper(page)

            async def new_context(self, **kwargs):
                """Create new context with wrapper and video recording if enabled."""
                # Add video recording parameters if video_dir is set
                if video_dir and 'record_video_dir' not in kwargs:
                    print(f"📹 Adding video recording to user-created context: {video_dir}")
                    kwargs['record_video_dir'] = video_dir
                    kwargs['record_video_size'] = {"width": 1280, "height": 720}
                    # Also add HAR recording if not present
                    if 'record_har_path' not in kwargs:
                        kwargs['record_har_path'] = f"{video_dir}/network.har"
                context = await self._browser.new_context(**kwargs)
                wrapped = ContextWrapper(context)
                self._contexts.append(wrapped)
                return wrapped

            async def close(self):
                """Close all contexts and browser."""
                print("🔴 BrowserWrapper.close() called - saving videos...")
                # Close all contexts first (to save videos)
                for ctx in self._contexts:
                    try:
                        print(f"  Closing context: {ctx}")
                        await ctx.close()
                    except Exception as e:
                        print(f"  Error closing context: {e}")
                if self._default_context:
                    try:
                        print(f"  Closing default context for video recording...")
                        await self._default_context.close()
                        print(f"  ✅ Default context closed - video should be saved")
                    except Exception as e:
                        print(f"  ❌ Error closing default context: {e}")
                print("  Closing browser...")
                result = await self._browser.close()
                print("  ✅ Browser closed")
                return result

            def __getattr__(self, name):
                return getattr(self._browser, name)

        # Playwright wrapper
        class PlaywrightWrapper:
            def __init__(self, playwright):
                self._playwright = playwright

            @property
            def chromium(self):
                return LauncherWrapper(self._playwright.chromium)

            @property
            def firefox(self):
                return LauncherWrapper(self._playwright.firefox)

            @property
            def webkit(self):
                return LauncherWrapper(self._playwright.webkit)

            def __getattr__(self, name):
                return getattr(self._playwright, name)

        # Browser launcher wrapper
        class LauncherWrapper:
            def __init__(self, launcher):
                self._launcher = launcher

            async def launch(self, **kwargs):
                """Launch browser with wrapper. Force headless=True to prevent window flickering."""
                # Override headless to True for smooth streaming without window
                kwargs['headless'] = True
                print(f"🚀 Launching browser in HEADLESS mode (streaming to sidebar only)")
                browser = await self._launcher.launch(**kwargs)

                # Create context with video recording if video_dir is set
                default_context = None
                if video_dir:
                    print(f"📹 Creating browser context with video recording to: {video_dir}")
                    context_options = {
                        'record_video_dir': video_dir,
                        'record_video_size': {"width": 1280, "height": 720}
                    }
                    # Also record HAR file for network activity
                    context_options['record_har_path'] = f"{video_dir}/network.har"
                    raw_context = await browser.new_context(**context_options)
                    default_context = ContextWrapper(raw_context)

                return BrowserWrapper(browser, default_context)

            def __getattr__(self, name):
                return getattr(self._launcher, name)

        # Custom async_playwright that returns wrapped version
        class async_playwright_wrapper:
            async def __aenter__(self):
                print("🎭 async_playwright_wrapper.__aenter__() called - using wrapped Playwright!")
                self._playwright_context = async_playwright()
                playwright = await self._playwright_context.__aenter__()
                wrapped = PlaywrightWrapper(playwright)
                print("✅ Playwright wrapped successfully")
                return wrapped

            async def __aexit__(self, *args):
                print("🎭 async_playwright_wrapper.__aexit__() called")
                return await self._playwright_context.__aexit__(*args)

        try:
            nonlocal test_status
            # Remove the playwright import line and asyncio.run() from user's code
            # so we can provide our wrapped version
            modified_code = code.replace('asyncio.run(run())', '')

            # Remove common import patterns
            import_patterns = [
                'from playwright.async_api import async_playwright\n',
                'from playwright.async_api import async_playwright, Playwright\n',
                'from playwright.async_api import Playwright, async_playwright\n',
                'import asyncio\n',
            ]
            for pattern in import_patterns:
                modified_code = modified_code.replace(pattern, '')

            # Log the modified code for debugging
            print("=" * 50)
            print("Modified code to execute:")
            print(modified_code)
            print("=" * 50)

            # Execute user's code with wrapped Playwright
            exec_globals = {
                'asyncio': asyncio,
                'async_playwright': async_playwright_wrapper,
                'base64': base64,
                'datetime': datetime,
                'socketio': socketio,
            }
            exec(modified_code, exec_globals)

            # Get and run the user's run function
            if 'run' not in exec_globals:
                socketio.emit('log', {'type': 'error', 'message': 'Error: Could not find run() function in code'})
                socketio.emit('test_complete', {'status': 'error'})
                return

            run_func = exec_globals['run']
            await run_func()

            test_status = 'success'
            socketio.emit('log', {'type': 'success', 'message': '✅ Code execution completed successfully!'})
            socketio.emit('test_complete', {'status': 'success'})

        except asyncio.CancelledError:
            # Test was stopped by user
            test_status = 'stopped'
            socketio.emit('log', {'type': 'info', 'message': '⏹ Test stopped by user'})
            socketio.emit('test_complete', {'status': 'stopped'})
        except Exception as e:
            import traceback
            error_msg = f'Error executing code: {str(e)}'
            test_status = 'error'
            socketio.emit('log', {'type': 'error', 'message': error_msg})
            socketio.emit('log', {'type': 'error', 'message': f'Traceback: {traceback.format_exc()}'})
            socketio.emit('test_complete', {'status': 'error', 'message': str(e)})

    try:
        loop.run_until_complete(execute_with_auto_streaming())
    except Exception as e:
        import traceback
        test_status = 'error'
        socketio.emit('log', {'type': 'error', 'message': f'Execution error: {str(e)}'})
        socketio.emit('log', {'type': 'error', 'message': f'Traceback: {traceback.format_exc()}'})
        socketio.emit('test_complete', {'status': 'error'})
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # Update test artifacts AFTER loop cleanup (separate block so it always runs)
    print(f"📼 === ARTIFACT SAVE BLOCK REACHED === artifact_dir={artifact_dir}, filename={filename}, workspace_id={workspace_id}")
    if artifact_dir and filename:
        try:
            import time
            time.sleep(2)  # Give browser time to finalize the video file
            print(f"📼 Saving artifacts: filename={filename}, workspace_id={workspace_id}, status={test_status}, dir={artifact_dir}")
            video_files = list(artifact_dir.glob("*.webm"))
            print(f"📼 Found video files: {video_files}")
            update_test_artifacts(
                filename,
                artifact_dir,
                test_status or 'unknown',
                workspace_id=workspace_id
            )
            # Tell frontend to refresh now that artifacts are saved
            socketio.emit('artifacts_updated', {'filename': filename})
        except Exception as e:
            import traceback
            print(f"📼 Error saving artifacts: {e}")
            traceback.print_exc()
    else:
        print(f"⚠️ Skipping artifact update: artifact_dir={artifact_dir}, filename={filename}")


def run_playwright_code_headless(code: str, filename: str, workspace_id: int = None):
    """Execute Playwright code in headless mode WITHOUT screenshot streaming.

    Returns:
        tuple: (status, error_message) where status is 'success' or 'error'
    """
    loop = None
    try:
        # Force headless mode
        modified_code = code.replace('headless=False', 'headless=True')

        # Create a new event loop for this execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Create namespace with required imports
        namespace = {
            'asyncio': asyncio,
            '__name__': '__main__'
        }

        # Execute the code (which includes the async def run() and asyncio.run(run()) calls)
        exec(modified_code, namespace)

        return 'success', None

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return 'error', error_msg
    finally:
        try:
            # Clean up the event loop
            if loop and not loop.is_closed():
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
        except Exception:
            pass


@app.route('/')
def index():
    """Render main page."""
    # Pass cloud environment flag to template
    is_cloud = bool(os.environ.get('K_SERVICE') or os.environ.get('CLOUD_RUN_JOB') or os.environ.get('GAE_ENV'))
    return render_template('index.html', is_cloud=is_cloud)


# ========== WORKSPACE MANAGEMENT API ENDPOINTS ==========

from flask_login import login_required, current_user
from models import Workspace, WorkspaceMember, WorkspaceRole, WorkspaceType, User


@app.route('/api/workspaces', methods=['GET'])
@login_required
def get_workspaces():
    """Get all workspaces accessible to current user (owned + shared)."""
    try:
        db = get_db_session()

        # Get owned workspaces
        owned_workspaces = db.query(Workspace).filter(
            Workspace.owner_id == current_user.id
        ).all()

        # Get shared workspaces (where user is a member)
        shared_workspaces = db.query(Workspace).join(
            WorkspaceMember
        ).filter(
            WorkspaceMember.user_id == current_user.id
        ).all()

        # Combine and deduplicate
        all_workspaces = {w.id: w for w in owned_workspaces + shared_workspaces}.values()

        return jsonify({
            'workspaces': [w.to_dict(include_members=True) for w in all_workspaces]
        }), 200

    except Exception as e:
        print(f"Error getting workspaces: {e}")
        return jsonify({'error': 'Failed to get workspaces'}), 500


@app.route('/api/workspaces', methods=['POST'])
@login_required
def create_workspace():
    """Create a new workspace."""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        workspace_type = data.get('type', 'private')

        if not name:
            return jsonify({'error': 'Workspace name is required'}), 400

        if workspace_type not in ['private', 'shared']:
            return jsonify({'error': 'Invalid workspace type'}), 400

        user = get_current_user()
        workspace = db.create_workspace(name=name, ws_type=workspace_type, owner_id=user['id'])

        return jsonify({
            'message': 'Workspace created successfully',
            'workspace': workspace
        }), 201

    except Exception as e:
        print(f"Error creating workspace: {e}")
        return jsonify({'error': 'Failed to create workspace'}), 500


@app.route('/api/workspaces/<int:workspace_id>', methods=['GET'])
@login_required
def get_workspace(workspace_id):
    """Get workspace details with members."""
    try:
        workspace = db.get_workspace_by_id(workspace_id)
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        user = get_current_user()
        if not db.workspace_has_access(workspace_id, user['id'], 'read'):
            return jsonify({'error': 'Access denied'}), 403

        # Ensure members are included
        if 'members' not in workspace:
            workspace['members'] = db.get_workspace_members(workspace_id)

        return jsonify({'workspace': workspace}), 200

    except Exception as e:
        print(f"Error getting workspace: {e}")
        return jsonify({'error': 'Failed to get workspace'}), 500


@app.route('/api/workspaces/<int:workspace_id>/members', methods=['POST'])
@login_required
def add_workspace_member(workspace_id):
    """Invite a user to a workspace."""
    try:
        data = request.get_json()

        username = data.get('username', '').strip()
        role = data.get('role', 'viewer')

        if not username:
            return jsonify({'error': 'Username is required'}), 400

        if role not in ['editor', 'viewer']:
            return jsonify({'error': 'Invalid role (use editor or viewer)'}), 400

        workspace = db.get_workspace_by_id(workspace_id)
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        user = get_current_user()
        if workspace['owner_id'] != user['id']:
            return jsonify({'error': 'Only workspace owner can add members'}), 403

        # Find user to invite
        invite_user = db.get_user_by_username(username)
        if not invite_user:
            return jsonify({'error': f'User {username} not found'}), 404

        # Don't add owner as member
        if invite_user['id'] == workspace['owner_id']:
            return jsonify({'error': 'Owner is already a member by default'}), 400

        # Check if user is already a member
        existing_members = db.get_workspace_members(workspace_id)
        for m in existing_members:
            if m['user_id'] == invite_user['id']:
                return jsonify({'error': f'{username} is already a member'}), 409

        member = db.add_workspace_member(workspace_id, invite_user['id'], role)

        return jsonify({
            'message': f'{username} added to workspace',
            'member': member
        }), 201

    except Exception as e:
        print(f"Error adding member: {e}")
        return jsonify({'error': 'Failed to add member'}), 500


@app.route('/api/workspaces/<int:workspace_id>/members/<user_id>', methods=['DELETE'])
@login_required
def remove_workspace_member(workspace_id, user_id):
    """Remove a user from a workspace."""
    try:
        workspace = db.get_workspace_by_id(workspace_id)
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        current = get_current_user()
        if workspace['owner_id'] != current['id']:
            return jsonify({'error': 'Only workspace owner can remove members'}), 403

        if not db.remove_workspace_member(workspace_id, user_id):
            return jsonify({'error': 'User is not a member of this workspace'}), 404

        return jsonify({'message': 'Member removed successfully'}), 200

    except Exception as e:
        print(f"Error removing member: {e}")
        return jsonify({'error': 'Failed to remove member'}), 500


@app.route('/api/workspaces/<int:workspace_id>/members/<user_id>/role', methods=['PUT'])
@login_required
def update_member_role(workspace_id, user_id):
    """Update a member's role in a workspace."""
    try:
        data = request.get_json()
        new_role = data.get('role', '').lower()

        if new_role not in ['editor', 'viewer']:
            return jsonify({'error': 'Invalid role (use editor or viewer)'}), 400

        workspace = db.get_workspace_by_id(workspace_id)
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404

        current = get_current_user()
        if workspace['owner_id'] != current['id']:
            return jsonify({'error': 'Only workspace owner can update member roles'}), 403

        member = db.update_member_role(workspace_id, user_id, new_role)
        if not member:
            return jsonify({'error': 'User is not a member of this workspace'}), 404

        return jsonify({
            'message': 'Member role updated successfully',
            'member': member
        }), 200

    except Exception as e:
        print(f"Error updating member role: {e}")
        return jsonify({'error': 'Failed to update member role'}), 500


# ========== END WORKSPACE MANAGEMENT API ENDPOINTS ==========


# ========== WORKSPACE-AWARE TEST MANAGEMENT API ENDPOINTS ==========

@app.route('/api/workspaces/<int:workspace_id>/tests', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_workspace_tests(workspace_id):
    """Get all tests in a workspace."""
    try:
        tests = db.get_tests(workspace_id)
        return jsonify({'tests': tests}), 200
    except Exception as e:
        print(f"Error getting workspace tests: {e}")
        return jsonify({'error': 'Failed to get tests'}), 500


@app.route('/api/workspaces/<int:workspace_id>/tests', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def create_workspace_test(workspace_id):
    """Create a new test in a workspace."""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        code = data.get('code', '')
        source = data.get('source', 'manual')

        if not name or not code:
            return jsonify({'error': 'Name and code are required'}), 400

        result = db.create_test(workspace_id, name, code, source, get_current_user()['id'])
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        print(f"Error creating test: {e}")
        return jsonify({'error': 'Failed to create test'}), 500


@app.route('/api/workspaces/<int:workspace_id>/tests/<filename>', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_workspace_test(workspace_id, filename):
    """Get a specific test from a workspace."""
    try:
        test_data = db.get_test(workspace_id, filename)
        if not test_data:
            return jsonify({'error': 'Test not found'}), 404
        return jsonify(test_data), 200
    except Exception as e:
        print(f"Error getting test: {e}")
        return jsonify({'error': 'Failed to get test'}), 500


@app.route('/api/workspaces/<int:workspace_id>/tests/<filename>', methods=['PUT'])
@login_required
@workspace_access_required(permission='write')
def update_workspace_test(workspace_id, filename):
    """Update a test in a workspace."""
    try:
        req_data = request.get_json()
        fields = {}
        if 'name' in req_data:
            fields['name'] = req_data['name']
        if 'code' in req_data:
            fields['code'] = req_data['code']
        if 'status' in req_data:
            fields['last_run_status'] = req_data['status']

        result = db.update_test(workspace_id, filename, **fields)
        if not result:
            return jsonify({'error': 'Test not found'}), 404
        return jsonify(result), 200
    except Exception as e:
        print(f"Error updating test: {e}")
        return jsonify({'error': 'Failed to update test'}), 500


@app.route('/api/workspaces/<int:workspace_id>/tests/<filename>', methods=['DELETE'])
@login_required
@workspace_access_required(permission='write')
def delete_workspace_test(workspace_id, filename):
    """Delete a test from a workspace."""
    try:
        if not db.delete_test(workspace_id, filename):
            return jsonify({'error': 'Test not found'}), 404
        return jsonify({'success': True, 'message': 'Test deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting test: {e}")
        return jsonify({'error': 'Failed to delete test'}), 500


@app.route('/api/workspaces/<int:workspace_id>/tests/<filename>/artifacts', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_workspace_test_artifacts(workspace_id, filename):
    """Get list of artifacts for a test in a workspace."""
    try:
        artifacts = db.get_test_artifacts(workspace_id, filename)
        if artifacts is None:
            return jsonify({'error': 'Test not found'}), 404
        return jsonify(artifacts), 200
    except Exception as e:
        print(f"Error getting test artifacts: {e}")
        return jsonify({'error': 'Failed to load artifacts'}), 500


@app.route('/api/workspaces/<int:workspace_id>/ai-steps', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_workspace_ai_steps(workspace_id):
    """Get all AI steps in a workspace."""
    try:
        ai_steps = db.get_ai_steps(workspace_id)
        return jsonify({'ai_steps': ai_steps}), 200
    except Exception as e:
        print(f"Error getting AI steps: {e}")
        return jsonify({'error': 'Failed to get AI steps'}), 500


# ========== END WORKSPACE-AWARE TEST MANAGEMENT API ENDPOINTS ==========


@app.route('/api/example-tests')
def example_tests():
    """Return example test templates."""
    examples = [
        {
            'name': 'Sunny Staging Signup',
            'url': 'https://sunny-staging.vercel.app/',
            'steps': """Complete the signup process on https://sunny-staging.vercel.app/:

1. Go to the website
2. Click the "Sign Up" button at the header
3. Fill out the signup form with:
   - Full Name: Test User
   - Email: test+(random 10 characters)@example.com
4. Submit the form by clicking the "Sign Up" button
5. Verify the success page contains:
   - Heading: "Just a couple of questions to save you time"
   - Subheading: "Bedrooms help us find your perfect fit"
   - 4 bedroom option cards"""
        },
        {
            'name': 'Google Search',
            'url': 'https://google.com',
            'steps': """Search on Google:

1. Go to https://google.com
2. Find the search box and type "AutoGen"
3. Click the search button or press enter
4. Verify results page shows search results"""
        }
    ]
    return jsonify(examples)


@app.route('/api/start-codegen', methods=['POST'])
def start_codegen():
    """Start Playwright codegen recording session."""
    # Check if running in cloud environment (Cloud Run, Docker, etc.)
    is_cloud = os.environ.get('K_SERVICE') or os.environ.get('CLOUD_RUN_JOB') or os.environ.get('GAE_ENV')

    if is_cloud:
        return jsonify({
            'error': 'Recording feature is not available in cloud deployments. Please run locally to use Playwright codegen.'
        }), 400

    data = request.json
    url = data.get('url', '')
    test_name = data.get('name', '')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    # Auto-prepend https:// if no protocol specified
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    # Generate unique recording ID
    recording_id = str(uuid.uuid4())

    # Create temp file for output
    temp_file = TEMP_RECORDINGS_DIR / f'{recording_id}.py'

    # Start codegen in background thread
    socketio.start_background_task(
        run_codegen_process,
        recording_id=recording_id,
        url=url,
        output_file=str(temp_file),
        test_name=test_name
    )

    return jsonify({
        'success': True,
        'recording_id': recording_id,
        'message': 'Recording started'
    })


@app.route('/api/save-test', methods=['POST'])
@login_required
def save_test():
    """Save a Playwright test for later reuse."""
    data = request.json
    name = data.get('name')
    code = data.get('code')
    source = data.get('source', 'ai')

    if not name or not code:
        return jsonify({'error': 'Name and code required'}), 400

    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify({'error': 'No workspace found'}), 400

    try:
        result = data_access.create_test(ws_id, name, code, source, current_user.id)
        return jsonify({'success': True, 'filename': result['filename']})
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        print(f"Error saving test: {e}")
        return jsonify({'error': 'Failed to save test'}), 500


@app.route('/api/saved-tests')
@login_required
def get_saved_tests():
    """Get list of saved tests."""
    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify([])
    tests = db.get_tests(ws_id)
    return jsonify(tests)


@app.route('/api/saved-tests/<filename>', methods=['GET'])
@login_required
def get_saved_test(filename):
    """Get a specific saved test."""
    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404
    test_data = db.get_test(ws_id, filename)
    if not test_data:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify(test_data)


@app.route('/api/saved-tests/<filename>', methods=['PUT'])
@login_required
def update_saved_test(filename):
    """Update a saved test."""
    data = request.json
    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404

    fields = {}
    if 'code' in data:
        fields['code'] = data['code']
    if 'name' in data:
        fields['name'] = data['name']
    if 'source' in data:
        fields['source'] = data['source']

    result = db.update_test(ws_id, filename, **fields)
    if not result:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify({'success': True})


@app.route('/api/saved-tests/<filename>', methods=['DELETE'])
@login_required
def delete_saved_test(filename):
    """Delete a saved test."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404
    if db.delete_test(ws_id, filename):
        return jsonify({'success': True})
    return jsonify({'error': 'Test not found'}), 404


@app.route('/api/saved-tests/<filename>/status', methods=['POST'])
@login_required
def update_test_status(filename):
    """Update the last run status of a saved test."""
    data = request.json
    status = data.get('status')
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404

    result = db.update_test(ws_id, filename,
                                     last_run_status=status,
                                     last_run_time=datetime.now())
    if not result:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify({'success': True})


def _get_workspace_id():
    """Get workspace_id from query param, falling back to user's default workspace."""
    ws_id = request.args.get('workspace_id', type=int)
    if not ws_id:
        ws_id = db.get_default_workspace_id(get_current_user()['id'])
    return ws_id


@app.route('/api/ai-steps')
@login_required
def get_ai_steps():
    """Get list of AI step tests."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify([])
    steps = db.get_ai_steps(ws_id)
    return jsonify(steps)


@app.route('/api/ai-steps', methods=['POST'])
@login_required
def save_ai_step():
    """Save new AI step test."""
    data = request.json
    name = data.get('name')
    steps = data.get('steps')

    if not name or not steps:
        return jsonify({'error': 'Name and steps required'}), 400

    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify({'error': 'No workspace found'}), 400

    try:
        result = data_access.create_ai_step(ws_id, name, steps, current_user.id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        print(f"Error saving AI step: {e}")
        return jsonify({'error': 'Failed to save AI step'}), 500


@app.route('/api/ai-steps/<filename>', methods=['GET'])
@login_required
def get_ai_step(filename):
    """Get a specific AI step test."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404
    step_data = db.get_ai_step(ws_id, filename)
    if not step_data:
        return jsonify({'error': 'AI step not found'}), 404
    return jsonify(step_data)


@app.route('/api/ai-steps/<filename>', methods=['PUT'])
@login_required
def update_ai_step(filename):
    """Update an existing AI step test."""
    data = request.json
    ws_id = data_access.get_default_workspace_id(current_user.id)
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404

    fields = {}
    if 'steps' in data:
        fields['steps'] = data['steps']
    if 'name' in data:
        fields['name'] = data['name']

    result = db.update_ai_step(ws_id, filename, **fields)
    if not result:
        return jsonify({'error': 'AI step not found'}), 404
    return jsonify({'success': True})


@app.route('/api/ai-steps/<filename>', methods=['DELETE'])
@login_required
def delete_ai_step(filename):
    """Delete an AI step test."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404
    if db.delete_ai_step(ws_id, filename):
        return jsonify({'success': True})
    return jsonify({'error': 'AI step not found'}), 404


@app.route('/api/ai-steps/<filename>/markdown', methods=['GET'])
@login_required
def get_ai_step_markdown(filename):
    """Get AI step in markdown format."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404
    step_data = db.get_ai_step(ws_id, filename)
    if not step_data:
        return jsonify({'error': 'AI step not found'}), 404
    return jsonify({'markdown': step_data.get('steps', ''), 'filename': filename})


@app.route('/api/ai-steps/<filename>/markdown', methods=['PUT'])
@login_required
def update_ai_step_markdown(filename):
    """Update AI step from markdown format."""
    data = request.json
    markdown_content = data.get('markdown')
    if not markdown_content:
        return jsonify({'error': 'Markdown content required'}), 400

    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404

    result = db.update_ai_step(ws_id, filename, steps=markdown_content.strip())
    if not result:
        return jsonify({'error': 'AI step not found'}), 404
    return jsonify({'success': True})


@app.route('/api/artifacts/<path:filepath>')
def serve_artifact(filepath):
    """Serve test artifact files (videos, HAR, traces)."""
    artifact_path = Path(__file__).parent / filepath

    # Security: Ensure path is within allowed directories
    try:
        artifact_path = artifact_path.resolve()
        base_path = (Path(__file__).parent / "test_artifacts").resolve()
        user_data_path = (Path(__file__).parent / Config.USER_DATA_PATH).resolve()
        if not (str(artifact_path).startswith(str(base_path)) or
                str(artifact_path).startswith(str(user_data_path))):
            return jsonify({'error': 'Invalid path'}), 403
    except Exception:
        return jsonify({'error': 'Invalid path'}), 400

    if not artifact_path.exists():
        return jsonify({'error': 'Artifact not found'}), 404

    return send_file(artifact_path)


@app.route('/api/saved-tests/<filename>/artifacts')
@login_required
def get_test_artifacts(filename):
    """Get list of artifacts for a saved test."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404
    artifacts = db.get_test_artifacts(ws_id, filename)
    if artifacts is None:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify(artifacts)


@app.route('/api/format-code', methods=['POST'])
def format_code():
    """Format Python code using Black formatter."""
    try:
        import black
        from black import Mode, TargetVersion

        data = request.get_json()
        code = data.get('code', '')

        if not code:
            return jsonify({'error': 'No code provided'}), 400

        # Format the code using Black
        try:
            formatted_code = black.format_str(
                code,
                mode=Mode(
                    target_versions={TargetVersion.PY310},
                    line_length=88,
                    string_normalization=True,
                    is_pyi=False,
                )
            )
            return jsonify({'formatted_code': formatted_code}), 200
        except black.InvalidInput as e:
            return jsonify({'error': f'Invalid Python syntax: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Formatting error: {str(e)}'}), 500

    except ImportError:
        return jsonify({'error': 'Black formatter not installed'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@socketio.on('run_test')
def handle_run_test(data):
    """Handle test execution request."""
    task = data.get('task', '')

    if not task:
        emit('log', {'type': 'error', 'message': 'No test steps provided'})
        return

    emit('log', {'type': 'info', 'message': 'Starting test...'})

    # Run test in background thread
    socketio.start_background_task(run_test_sync, task)


@socketio.on('stop_test')
def handle_stop_test():
    """Handle test stop request."""
    global stop_requested
    stop_requested = True
    emit('log', {'type': 'info', 'message': 'Stop request received, stopping test...'})


@socketio.on('run_playwright_code')
def handle_run_playwright_code(data):
    """Handle running Playwright code from the editor."""
    code = data.get('code', '')

    if not code:
        emit('log', {'type': 'error', 'message': 'No code provided'})
        return

    emit('log', {'type': 'info', 'message': '▶️ Executing Playwright code from editor...'})
    emit('log', {'type': 'info', 'message': '🚀 Starting browser session...'})

    # Run the code with screenshot streaming
    socketio.start_background_task(run_playwright_code_with_streaming, code)


@socketio.on('run_saved_test')
def handle_run_saved_test(data):
    """Handle running a saved Playwright test (no AI needed)."""
    filename = data.get('filename')
    workspace_id = data.get('workspaceId')

    if not filename:
        emit('log', {'type': 'error', 'message': 'No test specified'})
        return

    try:
        test_data = db.get_test(workspace_id, filename) if workspace_id else None
        if not test_data:
            emit('log', {'type': 'error', 'message': 'Test not found'})
            return

        code = test_data.get('code')
        emit('log', {'type': 'info', 'message': f'Running saved test: {test_data.get("name")}'})
        emit('log', {'type': 'info', 'message': '🚀 Executing Playwright code with live browser preview...'})

        socketio.start_background_task(run_playwright_code_with_streaming, code, filename, workspace_id)

    except Exception as e:
        emit('log', {'type': 'error', 'message': f'Error running saved test: {str(e)}'})


@socketio.on('run_all_tests')
def handle_run_all_tests(data):
    """Handle running all saved tests in parallel."""
    filenames = data.get('filenames', [])
    workspace_id = data.get('workspaceId')
    socketio.start_background_task(run_all_tests_parallel, filenames, workspace_id)


def run_all_tests_parallel(filenames, workspace_id=None):
    """Execute all tests in parallel and collect results."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    start_time = time.time()
    results = []

    def run_single_test(filename):
        """Execute a single test and return result."""
        try:
            test_data = db.get_test(workspace_id, filename) if workspace_id else None
            if not test_data:
                return {
                    'filename': filename,
                    'name': filename,
                    'status': 'error',
                    'error': 'Test not found'
                }

            name = test_data.get('name', filename)
            code = test_data.get('code', '')

            # Execute test in headless mode with workspace_id
            status, error_msg = run_playwright_code_headless(code, filename, workspace_id)

            # Update test status in DB
            db.update_test(workspace_id, filename,
                                    last_run_status=status,
                                    last_run_time=datetime.now())

            return {
                'filename': filename,
                'name': name,
                'status': status,
                'error': error_msg
            }

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            return {
                'filename': filename,
                'name': filename,
                'status': 'error',
                'error': error_msg
            }

    # Execute tests in parallel with max 5 workers
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_filename = {executor.submit(run_single_test, fn): fn for fn in filenames}

        for future in as_completed(future_to_filename):
            # Check if stop was requested
            global stop_requested
            if stop_requested:
                socketio.emit('log', {'type': 'info', 'message': '⏹ Batch run stopped by user'})
                # Cancel remaining futures
                for f in future_to_filename:
                    f.cancel()
                break

            result = future.result()
            results.append(result)

            # Emit progress update
            socketio.emit('batch_test_progress', result)

    # Calculate summary statistics
    duration = time.time() - start_time
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'success')
    failed = total - passed

    # Emit completion event
    socketio.emit('batch_run_complete', {
        'total': total,
        'passed': passed,
        'failed': failed,
        'duration': duration
    })


@socketio.on('run_ai_step')
def handle_run_ai_step(data):
    """Handle running an AI step test by database ID."""
    global current_ai_step

    step_id = data.get('id')
    # Fallback to filename+workspace for backwards compatibility
    filename = data.get('filename')
    workspace_id = data.get('workspaceId')

    if not step_id and not filename:
        emit('log', {'type': 'error', 'message': 'No AI step specified'})
        return

    try:
        if step_id:
            step_data = db.get_ai_step_by_id(step_id, workspace_id=workspace_id)
            if step_data:
                workspace_id = step_data['workspace_id']
                filename = step_data['filename']
        else:
            step_data = db.get_ai_step(workspace_id, filename) if workspace_id else None

        if not step_data:
            emit('log', {'type': 'error', 'message': 'AI step not found'})
            return

        steps = step_data.get('steps')
        name = step_data.get('name')

        if not steps:
            emit('log', {'type': 'error', 'message': 'No steps found in AI step test'})
            return

        emit('log', {'type': 'info', 'message': f'🤖 Running AI steps: {name}'})

        # Update last_run timestamp in DB
        db.update_ai_step(workspace_id, filename, last_run=datetime.now())

        # Track current AI step for code generation prompt
        current_ai_step = {'filename': filename, 'name': name, 'workspace_id': workspace_id}

        # Run test using existing run_test_sync logic with workspace_id
        socketio.start_background_task(run_test_sync, steps, filename, workspace_id)

    except Exception as e:
        emit('log', {'type': 'error', 'message': f'Error running AI step: {str(e)}'})


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message from AI Chat tab."""
    message = data.get('message')
    existing_code = data.get('existing_code')
    image = data.get('image')  # Base64 encoded image
    file_type = data.get('file_type', 'unknown')  # Get file type for context-aware assistance

    if not message and not image:
        emit('chat_error', {'message': 'No message or image provided'})
        return

    # Run in background to avoid blocking
    socketio.start_background_task(handle_code_chat, message, existing_code, image, file_type)


def handle_code_chat(message, existing_code, image=None, file_type='unknown'):
    """Background task to handle code generation chat."""
    try:
        # Generate response using code agent (with optional image and file type)
        result = code_agent.generate_response(message, existing_code, image, file_type)

        # Emit AI response
        socketio.emit('chat_response', {
            'role': 'ai',
            'message': result['message'],
            'timestamp': datetime.now().isoformat()
        })

        # Emit generated code or content (steps) if available
        if result.get('code'):
            # For test files - send code
            socketio.emit('code_suggestion', {
                'code': result['code'],
                'explanation': result.get('explanation', ''),
                'action': 'suggest',
                'content_type': 'code'
            })
        elif result.get('content'):
            # For AI steps files - send steps content
            socketio.emit('code_suggestion', {
                'code': result['content'],  # Using 'code' field for compatibility with frontend
                'explanation': result.get('explanation', ''),
                'action': 'suggest',
                'content_type': 'steps'
            })

    except Exception as e:
        socketio.emit('chat_error', {'message': str(e)})


@socketio.on('clear_chat')
def handle_clear_chat():
    """Handle chat history clear request."""
    code_agent.clear_history()
    emit('log', {'type': 'info', 'message': 'Chat history cleared'})


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    # Check if user is authenticated
    if not current_user.is_authenticated:
        emit('log', {'type': 'error', 'message': 'Authentication required'})
        return False  # Reject connection

    emit('log', {'type': 'info', 'message': f'Connected to AutoGen Web Tester (User: {current_user.username})'})


if __name__ == '__main__':
    # Get port from environment variable (Cloud Run sets PORT)
    port = int(os.environ.get('PORT', 8080))
    debug = not bool(os.environ.get('K_SERVICE'))  # Disable debug in Cloud Run

    print("🚀 AutoGen Web Tester UI")
    print(f"📱 Open your browser to: http://localhost:{port}")
    if os.environ.get('K_SERVICE'):
        print("☁️  Running in Cloud Run mode")
        print("⚠️  Recording feature disabled (use AI-driven tests)")
    print()

    socketio.run(app, debug=debug, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
