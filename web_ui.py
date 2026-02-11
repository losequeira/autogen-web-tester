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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'autogen-web-tester-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize code generation agent
code_agent = CodeGenerationAgent(api_key=config.OPENAI_API_KEY)

# Store active browser session and task
active_browser = None
active_task = None
stop_requested = False

# Track current AI step execution for code generation prompt
current_ai_step = None  # {'filename': '...', 'name': '...'}

# Saved tests directory
SAVED_TESTS_DIR = Path(__file__).parent / 'saved_tests'
SAVED_TESTS_DIR.mkdir(exist_ok=True)

# AI Steps directory
AI_STEPS_DIR = Path(__file__).parent / 'ai_steps'
AI_STEPS_DIR.mkdir(exist_ok=True)

# Codegen recordings tracking
active_recordings = {}
TEMP_RECORDINGS_DIR = Path(__file__).parent / 'temp_recordings'
TEMP_RECORDINGS_DIR.mkdir(exist_ok=True)


def cleanup_old_artifacts(test_name: str, keep_last_n: int = 10):
    """Remove old artifact directories, keeping only the last N."""
    import shutil
    artifact_base = Path(__file__).parent / "test_artifacts" / test_name
    if not artifact_base.exists():
        return

    # Get all timestamp directories, sorted by creation time (newest first)
    try:
        dirs = sorted(artifact_base.iterdir(), key=lambda x: x.stat().st_ctime, reverse=True)
    except Exception as e:
        print(f"Warning: Could not list artifact directories: {e}")
        return

    # Remove all but the last N
    for old_dir in dirs[keep_last_n:]:
        try:
            shutil.rmtree(old_dir)
            print(f"Cleaned up old artifact: {old_dir}")
        except Exception as e:
            print(f"Warning: Could not remove old artifacts: {e}")


def update_test_artifacts(filename: str, artifact_dir: Path, test_status: str = 'unknown'):
    """Update test JSON metadata with artifact information."""
    if not filename:
        return

    # Determine which directory to use (saved_tests or ai_steps)
    if filename.endswith('.json'):
        # Could be either saved test or AI step
        test_file = SAVED_TESTS_DIR / filename
        if not test_file.exists():
            test_file = AI_STEPS_DIR / filename
    else:
        test_file = AI_STEPS_DIR / filename

    if not test_file.exists():
        print(f"Warning: Test file not found for artifact update: {filename}")
        return

    try:
        with open(test_file, 'r') as f:
            test_data = json.load(f)

        # Find video file (Playwright names it automatically)
        video_files = list(artifact_dir.glob("*.webm"))
        video_path = video_files[0].relative_to(Path(__file__).parent) if video_files else None
        video_size_mb = video_files[0].stat().st_size / (1024*1024) if video_files else 0

        # Find HAR file
        har_files = list(artifact_dir.glob("*.har"))
        har_path = har_files[0].relative_to(Path(__file__).parent) if har_files else None

        # Add artifact info
        if 'artifacts' not in test_data:
            test_data['artifacts'] = []

        timestamp = artifact_dir.name  # Directory name is the timestamp
        test_data['artifacts'].append({
            'timestamp': timestamp,
            'video_path': str(video_path) if video_path else None,
            'video_size_mb': round(video_size_mb, 2),
            'har_path': str(har_path) if har_path else None,
            'status': test_status
        })

        # Update test metadata
        test_data['last_run'] = datetime.now().isoformat()
        test_data['last_run_status'] = test_status

        # Save updated metadata
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)

        print(f"Updated test metadata with artifact: {video_path}")

        # Cleanup old artifacts (keep last 10)
        test_name = Path(filename).stem
        cleanup_old_artifacts(test_name, keep_last_n=10)

    except Exception as e:
        print(f"Warning: Could not update test metadata: {e}")


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
                if self.streaming:  # Only log if we're supposed to be streaming
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


def generate_playwright_code(actions):
    """Generate complete Playwright test code from actions."""
    import re

    # Check if any action contains an email pattern like test+<random>@example.com
    has_random_email = any(
        re.search(r'test\+[a-z0-9]+@example\.com', action)
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
        ""
    ])

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


async def run_test_async(task: str):
    """Run the test with live updates."""
    global active_browser, stop_requested, current_ai_step

    stop_requested = False  # Reset stop flag
    socketio.emit('log', {'type': 'info', 'message': 'Initializing browser...'})

    # Create artifacts directory if this is an AI step test with filename
    artifact_dir = None
    video_dir = None
    test_filename = None  # Save filename before current_ai_step gets reset
    test_status = None  # Track test status for artifact metadata
    if current_ai_step and current_ai_step.get('filename'):
        from pathlib import Path
        test_filename = current_ai_step['filename']  # Save for artifact update later
        test_name = Path(test_filename).stem
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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

            # Create model client
            socketio.emit('log', {'type': 'info', 'message': 'Initializing AI model...'})

            model_client = OpenAIChatCompletionClient(
                model=config.MODEL_NAME,
                api_key=config.OPENAI_API_KEY
            )

            # System message
            system_message = """You are a web testing automation agent. Your job is to interact with websites using the provided browser tools.

CRITICAL: You MUST follow the user's test steps EXACTLY as written. Do NOT skip validation steps. Do NOT ignore errors.

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

Available tools:
- navigate, click_text, click, fill_form, find_inputs, get_page_content, get_current_url, get_text, screenshot, get_html

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
                    get_html_tool
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
        if artifact_dir and test_filename:
            # Give the browser time to finalize the video
            import time
            time.sleep(1)
            update_test_artifacts(
                test_filename,
                artifact_dir,
                test_status or 'unknown'
            )


def run_test_sync(task: str):
    """Wrapper to run async test in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_test_async(task))
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


def run_playwright_code_with_streaming(code: str, filename: str = None):
    """Execute Playwright code with automatic screenshot streaming to browser sidebar."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create artifacts directory for this test run if filename provided
    artifact_dir = None
    video_dir = None
    test_status = None  # Track test status for artifact metadata
    if filename:
        print(f"🎬 Filename provided: {filename}")
        from pathlib import Path
        from datetime import datetime
        test_name = Path(filename).stem
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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
                self._streaming = True
                while self._streaming:
                    try:
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
                print(f"👆 PageWrapper.click() called for selector: {selector}")
                result = await self._page.click(selector, **kwargs)
                await send_screenshot(self._page, 'click')
                return result

            async def fill(self, selector, value, **kwargs):
                """Fill and capture screenshot."""
                print(f"✍️ PageWrapper.fill() called for selector: {selector}")
                result = await self._page.fill(selector, value, **kwargs)
                await send_screenshot(self._page, 'fill')
                return result

            async def type(self, selector, text, **kwargs):
                """Type and capture screenshot."""
                result = await self._page.type(selector, text, **kwargs)
                await send_screenshot(self._page, 'type')
                return result

            async def press(self, selector, key, **kwargs):
                """Press key and capture screenshot."""
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
                """Create new context with wrapper."""
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
            loop.close()

            # Update test artifacts if video recording was enabled
            if artifact_dir and filename:
                # Give the browser time to finalize the video
                import time
                time.sleep(1)
                update_test_artifacts(
                    filename,
                    artifact_dir,
                    test_status or 'unknown'
                )


def run_playwright_code_headless(code: str, filename: str):
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
def save_test():
    """Save a Playwright test for later reuse."""
    data = request.json
    name = data.get('name')
    code = data.get('code')
    source = data.get('source', 'ai')  # Default to 'ai' for backward compatibility

    if not name or not code:
        return jsonify({'error': 'Name and code required'}), 400

    # Sanitize filename
    filename = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = filename.replace(' ', '_') + '.json'

    test_data = {
        'name': name,
        'code': code,
        'source': source,
        'created': datetime.now().isoformat()
    }

    filepath = SAVED_TESTS_DIR / filename
    with open(filepath, 'w') as f:
        json.dump(test_data, f, indent=2)

    return jsonify({'success': True, 'filename': filename})


@app.route('/api/saved-tests')
def get_saved_tests():
    """Get list of saved tests."""
    tests = []
    for filepath in SAVED_TESTS_DIR.glob('*.json'):
        try:
            with open(filepath, 'r') as f:
                test_data = json.load(f)
                tests.append({
                    'filename': filepath.name,
                    'name': test_data.get('name'),
                    'created': test_data.get('created'),
                    'source': test_data.get('source', 'ai'),  # Default to 'ai' for backward compatibility
                    'last_run_status': test_data.get('last_run_status'),  # 'success', 'error', or 'stopped'
                    'artifacts': test_data.get('artifacts', []),  # Include artifacts for video recordings
                    'last_run_time': test_data.get('last_run_time')
                })
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    # Sort by creation date, newest first
    tests.sort(key=lambda x: x.get('created', ''), reverse=True)
    return jsonify(tests)


@app.route('/api/saved-tests/<filename>', methods=['GET'])
def get_saved_test(filename):
    """Get a specific saved test."""
    filepath = SAVED_TESTS_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            test_data = json.load(f)
        return jsonify(test_data)
    return jsonify({'error': 'Test not found'}), 404


@app.route('/api/saved-tests/<filename>', methods=['PUT'])
def update_saved_test(filename):
    """Update a saved test."""
    filepath = SAVED_TESTS_DIR / filename
    if not filepath.exists():
        return jsonify({'error': 'Test not found'}), 404

    data = request.json
    code = data.get('code')
    name = data.get('name')

    if not code:
        return jsonify({'error': 'Code required'}), 400

    test_data = {
        'name': name or filename.replace('.json', '').replace('_', ' '),
        'code': code,
        'source': data.get('source', 'ai'),  # Preserve source field
        'created': data.get('created', datetime.now().isoformat()),
        'updated': datetime.now().isoformat()
    }

    with open(filepath, 'w') as f:
        json.dump(test_data, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/saved-tests/<filename>', methods=['DELETE'])
def delete_saved_test(filename):
    """Delete a saved test."""
    filepath = SAVED_TESTS_DIR / filename
    if filepath.exists():
        filepath.unlink()
        return jsonify({'success': True})
    return jsonify({'error': 'Test not found'}), 404


@app.route('/api/saved-tests/<filename>/status', methods=['POST'])
def update_test_status(filename):
    """Update the last run status of a saved test."""
    filepath = SAVED_TESTS_DIR / filename
    if not filepath.exists():
        return jsonify({'error': 'Test not found'}), 404

    data = request.json
    status = data.get('status')  # 'success', 'error', or 'stopped'

    try:
        # Read existing test data
        with open(filepath, 'r') as f:
            test_data = json.load(f)

        # Update status fields
        test_data['last_run_status'] = status
        test_data['last_run_time'] = datetime.now().isoformat()

        # Write back
        with open(filepath, 'w') as f:
            json.dump(test_data, f, indent=2)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def json_to_markdown(step_data):
    """Convert AI step JSON to markdown (just the steps content)."""
    # Return just the steps content - metadata stays in JSON
    return step_data.get('steps', '')


def markdown_to_json(markdown_content):
    """Convert markdown content back to JSON structure (just updates steps field)."""
    # Return just the steps content - other fields will be preserved from original JSON
    return {
        'steps': markdown_content.strip()
    }


@app.route('/api/ai-steps')
def get_ai_steps():
    """Get list of AI step tests."""
    steps = []
    for filepath in AI_STEPS_DIR.glob('*.json'):
        try:
            with open(filepath, 'r') as f:
                step_data = json.load(f)
                steps.append({
                    'filename': filepath.name,
                    'name': step_data.get('name'),
                    'steps': step_data.get('steps'),
                    'created': step_data.get('created'),
                    'last_run': step_data.get('last_run'),
                    'status': step_data.get('status')
                })
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    # Sort by creation date, newest first
    steps.sort(key=lambda x: x.get('created', ''), reverse=True)
    return jsonify(steps)


@app.route('/api/ai-steps', methods=['POST'])
def save_ai_step():
    """Save new AI step test."""
    data = request.json
    name = data.get('name')
    steps = data.get('steps')

    if not name or not steps:
        return jsonify({'error': 'Name and steps required'}), 400

    # Sanitize filename
    filename = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = filename.replace(' ', '_') + '.json'

    step_data = {
        'name': name,
        'steps': steps,
        'created': datetime.now().isoformat(),
        'last_run': None,
        'status': None
    }

    filepath = AI_STEPS_DIR / filename
    with open(filepath, 'w') as f:
        json.dump(step_data, f, indent=2)

    return jsonify({'success': True, 'filename': filename})


@app.route('/api/ai-steps/<filename>', methods=['GET'])
def get_ai_step(filename):
    """Get a specific AI step test."""
    filepath = AI_STEPS_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            step_data = json.load(f)
        return jsonify(step_data)
    return jsonify({'error': 'AI step not found'}), 404


@app.route('/api/ai-steps/<filename>', methods=['PUT'])
def update_ai_step(filename):
    """Update an existing AI step test."""
    filepath = AI_STEPS_DIR / filename
    if not filepath.exists():
        return jsonify({'error': 'AI step not found'}), 404

    data = request.json
    steps = data.get('steps')
    name = data.get('name')

    if not steps:
        return jsonify({'error': 'Steps required'}), 400

    step_data = {
        'name': name or filename.replace('.json', '').replace('_', ' '),
        'steps': steps,
        'created': data.get('created', datetime.now().isoformat()),
        'updated': datetime.now().isoformat(),
        'last_run': data.get('last_run'),
        'status': data.get('status')
    }

    with open(filepath, 'w') as f:
        json.dump(step_data, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/ai-steps/<filename>', methods=['DELETE'])
def delete_ai_step(filename):
    """Delete an AI step test."""
    filepath = AI_STEPS_DIR / filename
    if filepath.exists():
        filepath.unlink()
        return jsonify({'success': True})
    return jsonify({'error': 'AI step not found'}), 404


@app.route('/api/ai-steps/<filename>/markdown', methods=['GET'])
def get_ai_step_markdown(filename):
    """Get AI step in markdown format."""
    filepath = AI_STEPS_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            step_data = json.load(f)
        markdown = json_to_markdown(step_data)
        return jsonify({'markdown': markdown, 'filename': filename})
    return jsonify({'error': 'AI step not found'}), 404


@app.route('/api/ai-steps/<filename>/markdown', methods=['PUT'])
def update_ai_step_markdown(filename):
    """Update AI step from markdown format."""
    filepath = AI_STEPS_DIR / filename
    if not filepath.exists():
        return jsonify({'error': 'AI step not found'}), 404

    data = request.json
    markdown_content = data.get('markdown')
    if not markdown_content:
        return jsonify({'error': 'Markdown content required'}), 400

    # Read existing data to preserve metadata
    try:
        with open(filepath, 'r') as f:
            step_data = json.load(f)
    except:
        # If file doesn't exist or is invalid, create new structure
        step_data = {
            'name': filename.replace('.json', '').replace('_', ' '),
            'created': datetime.now().isoformat(),
            'last_run': None,
            'status': None
        }

    # Update only the steps content from markdown
    updated_fields = markdown_to_json(markdown_content)
    step_data.update(updated_fields)

    # Update timestamp
    step_data['updated'] = datetime.now().isoformat()

    with open(filepath, 'w') as f:
        json.dump(step_data, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/artifacts/<path:filepath>')
def serve_artifact(filepath):
    """Serve test artifact files (videos, HAR, traces)."""
    # filepath already includes "test_artifacts/" prefix, so just use it directly
    artifact_path = Path(__file__).parent / filepath

    # Security: Ensure path is within test_artifacts directory
    try:
        artifact_path = artifact_path.resolve()
        base_path = (Path(__file__).parent / "test_artifacts").resolve()
        if not str(artifact_path).startswith(str(base_path)):
            return jsonify({'error': 'Invalid path'}), 403
    except Exception:
        return jsonify({'error': 'Invalid path'}), 400

    if not artifact_path.exists():
        return jsonify({'error': 'Artifact not found'}), 404

    return send_file(artifact_path)


@app.route('/api/saved-tests/<filename>/artifacts')
def get_test_artifacts(filename):
    """Get list of artifacts for a saved test."""
    filepath = SAVED_TESTS_DIR / filename
    if not filepath.exists():
        # Try AI steps directory
        filepath = AI_STEPS_DIR / filename
        if not filepath.exists():
            return jsonify({'error': 'Test not found'}), 404

    try:
        with open(filepath, 'r') as f:
            test_data = json.load(f)

        artifacts = test_data.get('artifacts', [])
        return jsonify(artifacts)
    except Exception as e:
        return jsonify({'error': f'Failed to load artifacts: {str(e)}'}), 500


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

    if not filename:
        emit('log', {'type': 'error', 'message': 'No test specified'})
        return

    filepath = SAVED_TESTS_DIR / filename
    if not filepath.exists():
        emit('log', {'type': 'error', 'message': 'Test not found'})
        return

    try:
        with open(filepath, 'r') as f:
            test_data = json.load(f)
            code = test_data.get('code')

        emit('log', {'type': 'info', 'message': f'Running saved test: {test_data.get("name")}'})
        emit('log', {'type': 'info', 'message': '🚀 Executing Playwright code with live browser preview...'})

        # Run the saved test with streaming in background thread
        socketio.start_background_task(run_playwright_code_with_streaming, code, filename)

    except Exception as e:
        emit('log', {'type': 'error', 'message': f'Error running saved test: {str(e)}'})


@socketio.on('run_all_tests')
def handle_run_all_tests(data):
    """Handle running all saved tests in parallel."""
    filenames = data.get('filenames', [])
    socketio.start_background_task(run_all_tests_parallel, filenames)


def run_all_tests_parallel(filenames):
    """Execute all tests in parallel and collect results."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    start_time = time.time()
    results = []

    def run_single_test(filename):
        """Execute a single test and return result."""
        try:
            # Load test file
            filepath = SAVED_TESTS_DIR / filename
            if not filepath.exists():
                return {
                    'filename': filename,
                    'name': filename,
                    'status': 'error',
                    'error': 'Test file not found'
                }

            with open(filepath, 'r') as f:
                test_data = json.load(f)

            name = test_data.get('name', filename)
            code = test_data.get('code', '')

            # Execute test in headless mode
            status, error_msg = run_playwright_code_headless(code, filename)

            # Update test file with results
            test_data['last_run_status'] = status
            test_data['last_run_time'] = time.time()
            if error_msg:
                test_data['last_error'] = error_msg

            with open(filepath, 'w') as f:
                json.dump(test_data, f, indent=2)

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
    """Handle running an AI step test from file."""
    global current_ai_step

    filename = data.get('filename')

    if not filename:
        emit('log', {'type': 'error', 'message': 'No AI step specified'})
        return

    filepath = AI_STEPS_DIR / filename
    if not filepath.exists():
        emit('log', {'type': 'error', 'message': 'AI step not found'})
        return

    try:
        with open(filepath, 'r') as f:
            step_data = json.load(f)
            steps = step_data.get('steps')
            name = step_data.get('name')

        if not steps:
            emit('log', {'type': 'error', 'message': 'No steps found in AI step test'})
            return

        emit('log', {'type': 'info', 'message': f'🤖 Running AI steps: {name}'})

        # Update last_run timestamp
        step_data['last_run'] = datetime.now().isoformat()
        with open(filepath, 'w') as f:
            json.dump(step_data, f, indent=2)

        # Track current AI step for code generation prompt
        current_ai_step = {'filename': filename, 'name': name}

        # Run test using existing run_test_sync logic
        socketio.start_background_task(run_test_sync, steps)

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
    emit('log', {'type': 'info', 'message': 'Connected to AutoGen Web Tester'})


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
