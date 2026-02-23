"""
Web UI for AutoGen Web Tester
Provides a browser interface to write and run tests, watch browser automation live.
"""

import asyncio
import base64
import sys
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
import re

# Resolve base directory for templates/static when running frozen (PyInstaller)
_BASE_DIR = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

from browser_tool import BrowserTool
from code_agent import CodeGenerationAgent
import config
from config import Config
import local_tree
import git_ops
import git.exc
import github_config
import requests as _requests

# Playwright trace viewer static assets (bundled with the playwright package)
import playwright as _playwright_pkg
_TRACE_VIEWER_DIR = (
    Path(_playwright_pkg.__file__).parent / 'driver' / 'package' / 'lib' / 'vite' / 'traceViewer'
)

# Import multi-user modules
import db
from auth import init_auth, login_required, get_current_user
from decorators import workspace_access_required

app = Flask(
    __name__,
    template_folder=str(_BASE_DIR / 'templates'),
    static_folder=str(_BASE_DIR / 'static'),
)

# Apply multi-user configuration
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize authentication
print("Initializing authentication...")
init_auth(app)


# ========== WORKSPACE HELPER FUNCTIONS ==========
# (Workspace paths removed — artifacts stored locally in ~/.autogen/artifacts/)
# ========== END WORKSPACE HELPER FUNCTIONS ==========

# Initialize code generation agent
code_agent = CodeGenerationAgent(api_key=config.OPENAI_API_KEY)

# Initialize workspace agent (tool-calling agent for file management)
from workspace_agent import WorkspaceAgent
workspace_agent = WorkspaceAgent()

# Store active browser session and task
active_browser = None
active_task = None
stop_requested = False
active_loop = None   # Event loop of the currently running test (for hard stop)

# Track current AI step execution for code generation prompt
current_ai_step = None  # {'filename': '...', 'name': '...'}

# Codegen recordings tracking
active_recordings = {}
TEMP_RECORDINGS_DIR = Path(__file__).parent / 'temp_recordings'
TEMP_RECORDINGS_DIR.mkdir(exist_ok=True)

# Embedded browser recorder sessions: recording_id -> {loop, actions, stop_event, page_ref, test_name}
active_recorders: dict = {}

# ===== Warm browser pool =====
# A single headless Chromium instance kept alive between test runs to eliminate startup latency.
import threading as _threading

_warm_loop: asyncio.AbstractEventLoop | None = None
_warm_browser = None          # Pre-launched Browser (stays alive between tests)
_warm_playwright_exit = None  # Callable to shut down the warm playwright context on app exit
_warm_ready = _threading.Event()
_active_test_task = None      # asyncio.Task for the currently running test (targeted stop)


async def _init_warm_browser():
    """Start Playwright + headless Chromium in the warm loop."""
    global _warm_browser, _warm_playwright_exit
    from playwright.async_api import async_playwright as _ap
    ctx = _ap()
    pw = await ctx.__aenter__()
    _warm_playwright_exit = lambda: ctx.__aexit__(None, None, None)
    _warm_browser = await pw.chromium.launch(headless=True)
    print("🔥 Warm browser ready — test startup will be instant")


def _warm_browser_thread():
    """Daemon thread: runs a persistent event loop with a pre-warmed Chromium browser."""
    global _warm_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _warm_loop = loop
    loop.run_until_complete(_init_warm_browser())
    _warm_ready.set()
    loop.run_forever()


_wb_thread = _threading.Thread(target=_warm_browser_thread, daemon=True, name='warm-browser')
_wb_thread.start()
# ===== End warm browser pool =====


def update_test_artifacts(
    filename: str,
    artifact_dir: Path,
    test_status: str = 'unknown',
    workspace_name: str = None,
    from_tree: bool = True,
):
    """Save test artifacts into the workspace directory and update local meta."""
    print(f"📼 update_test_artifacts called: filename={filename}, workspace_name={workspace_name}, status={test_status}")
    if not filename or not workspace_name:
        print(f"Warning: Cannot update artifacts without filename and workspace_name")
        return

    try:
        from storage import save_artifact_dir
        import shutil
        # Sanitize path for artifact dir: e2e/Landing.py -> e2e_Landing
        test_name = filename.replace("/", "_").replace("\\", "_")
        if test_name.endswith(".py"):
            test_name = test_name[:-3]
        artifact_dir_abs = artifact_dir.resolve()
        storage_paths = save_artifact_dir(artifact_dir_abs, workspace_name, test_name)
        root = _tree_root(workspace_name, "saved_tests")
        local_tree.write_last_run_meta(
            root, filename,
            status=test_status,
            last_run_time=datetime.utcnow().isoformat(),
        )
        # Write status.json inside the artifact dir for recordings gallery
        art_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / 'saved_tests' / 'artifacts' / test_name
        if art_dir.is_dir():
            import json as _json
            status_file = art_dir / 'status.json'
            status_file.write_text(_json.dumps({
                'status': test_status,
                'timestamp': datetime.utcnow().isoformat(),
            }), encoding='utf-8')
        print(f"📼 Artifact saved: {storage_paths.get('video_path')}")
        if artifact_dir_abs.exists():
            shutil.rmtree(artifact_dir_abs, ignore_errors=True)
    except Exception as e:
        import traceback
        print(f"Warning: Could not update artifacts: {e}")
        traceback.print_exc()


class BrowserToolWithScreenshots(BrowserTool):
    """Extended BrowserTool that captures screenshots after each action and continuously streams."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming = False
        self.stream_task = None
        self.playwright_code = []  # Track Playwright code
        self._current_url = ''    # Reliably tracked page URL

    async def start_streaming(self):
        """Use CDP Page.startScreencast for push-based streaming (falls back to polling)."""
        self.streaming = True
        import config as _config
        if not _config.USE_CDP_SCREENCAST or not self.page:
            # Fallback to polling
            self._current_url = self.page.url
            while self.streaming and self.page:
                try:
                    await self._send_screenshot('stream')
                    await asyncio.sleep(0.1)
                except Exception as e:
                    if not self.streaming:
                        break
                    error_msg = str(e).lower()
                    if "target closed" in error_msg and self.original_page and self.page != self.original_page:
                        self.page = self.original_page
                        await asyncio.sleep(0.1)
                        continue
                    print(f"Stream error: {e}")
                    break
            return

        cdp = await self.page.context.new_cdp_session(self.page)
        self._current_url = self.page.url

        # Track URL changes in real-time via Playwright's navigation event
        def on_navigated(frame):
            if frame == self.page.main_frame:
                self._current_url = frame.url

        self.page.on('framenavigated', on_navigated)

        async def on_frame(params):
            if not self.streaming:
                return
            socketio.emit('screenshot', {
                'action': 'stream',
                'image': params['data'],  # already base64 JPEG
                'timestamp': datetime.now().isoformat(),
                'url': self.page.url if self.page else self._current_url
            })
            try:
                await cdp.send('Page.screencastFrameAck', {'sessionId': params['sessionId']})
            except Exception:
                pass

        cdp.on('Page.screencastFrame', lambda p: asyncio.create_task(on_frame(p)))

        await cdp.send('Page.startScreencast', {
            'format': 'jpeg',
            'quality': _config.SCREENCAST_JPEG_QUALITY,
            'maxWidth': _config.SCREENCAST_MAX_WIDTH,
            'maxHeight': _config.SCREENCAST_MAX_HEIGHT,
            'everyNthFrame': 1
        })

        while self.streaming and self.page:
            await asyncio.sleep(0.2)

        try:
            self.page.remove_listener('framenavigated', on_navigated)
        except Exception:
            pass
        try:
            await cdp.send('Page.stopScreencast')
            await cdp.detach()
        except Exception:
            pass

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
                quality=config.SCREENCAST_JPEG_QUALITY,
                full_page=False
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            socketio.emit('screenshot', {
                'action': action_name,
                'image': screenshot_b64,
                'timestamp': datetime.now().isoformat(),
                'url': self.page.url if self.page else self._current_url
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
        self._current_url = self.page.url if self.page else url
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
        self._current_url = self.page.url if self.page else self._current_url
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
        self._current_url = self.page.url if self.page else self._current_url
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
        # Emit starting status (mode 'browser' = real Chromium window; frontend won't show in-app recorder)
        socketio.emit('codegen_status', {
            'recording_id': recording_id,
            'status': 'recording',
            'message': f'🎥 Recording started for {url}',
            'mode': 'browser',
        })

        # Start Playwright codegen process (same Python as app for venvs/frozen builds)
        process = subprocess.Popen(
            [
                sys.executable, '-m', 'playwright', 'codegen',
                '--target', 'python-async',
                '--output', output_file,
                '--browser', 'chromium',
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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


# Minimum pause (ms) between actions to record as an explicit wait step
RECORDER_WAIT_THRESHOLD_MS = 1000


def generate_code_from_actions(actions: list) -> str:
    """Generate Playwright Python code from a list of recorded (action, *args) tuples."""
    lines = [
        'from playwright.async_api import async_playwright',
        'import asyncio',
        '',
        'async def run():',
        '    async with async_playwright() as p:',
        '        browser = await p.chromium.launch(headless=False)',
        '        page = await browser.new_page()',
    ]
    for action in actions:
        kind = action[0]
        if kind == 'goto':
            url = action[1].replace("'", "\\'")
            lines.append(f"        await page.goto('{url}')")
        elif kind == 'click':
            lines.append(f"        await page.mouse.click({action[1]}, {action[2]})")
        elif kind == 'type':
            text = action[1].replace('\\', '\\\\').replace("'", "\\'")
            lines.append(f"        await page.keyboard.type('{text}')")
        elif kind == 'wait':
            ms = action[1]
            sec = ms / 1000.0
            lines.append(f"        await asyncio.sleep({sec})")
    lines.extend([
        '        await browser.close()',
        '',
        'asyncio.run(run())',
    ])
    return '\n'.join(lines)


def run_embedded_recorder(recording_id: str, url: str, test_name: str):
    """
    Run a headless Playwright browser for interactive recording.
    Streams screenshots via Socket.IO; responds to recorder_interact socket events.
    """
    import asyncio as _asyncio
    from playwright.async_api import async_playwright as _async_playwright

    loop = _asyncio.new_event_loop()
    actions: list = []
    stop_event = _asyncio.Event()
    page_ref: list = [None]

    active_recorders[recording_id] = {
        'loop': loop,
        'actions': actions,
        'stop_event': stop_event,
        'page_ref': page_ref,
        'test_name': test_name,
        'last_action_at': None,
    }

    viewport_w = getattr(config, 'VIDEO_SIZE_WIDTH', 1280)
    viewport_h = getattr(config, 'VIDEO_SIZE_HEIGHT', 720)

    async def _run():
        async with _async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': viewport_w, 'height': viewport_h}
            )
            page = await context.new_page()
            page_ref[0] = page

            try:
                await page.goto(url, timeout=30000)
                actions.append(('goto', url))
            except Exception as e:
                socketio.emit('log', {'type': 'error', 'message': f'Recorder navigation error: {e}'})

            socketio.emit('codegen_status', {
                'recording_id': recording_id,
                'status': 'recording',
                'message': f'Recording started at {url}',
                'viewport': {'width': viewport_w, 'height': viewport_h},
            })

            # Stream screenshots at ~10 FPS until stop is requested
            while not stop_event.is_set():
                try:
                    shot = await page.screenshot(type='jpeg', quality=70)
                    img_b64 = base64.b64encode(shot).decode('utf-8')
                    title = await page.title() if page else ''
                    socketio.emit('screenshot', {
                        'image': img_b64,
                        'action': 'stream',
                        'timestamp': datetime.now().isoformat(),
                        'recorder_id': recording_id,
                        'url': page.url,
                        'title': title or None,
                    })
                except Exception as e:
                    if not stop_event.is_set():
                        print(f'Recorder screenshot error: {e}')
                    break
                await _asyncio.sleep(0.1)

            await context.close()
            await browser.close()

    try:
        loop.run_until_complete(_run())
    except Exception as e:
        print(f'Embedded recorder error: {e}')
        socketio.emit('codegen_error', {
            'recording_id': recording_id,
            'message': str(e),
        })
    finally:
        loop.close()
        active_recorders.pop(recording_id, None)


def _maybe_append_wait_before_action(recorder: dict, actions: list) -> None:
    """If enough time passed since last action, append a ('wait', ms) step."""
    last = recorder.get('last_action_at')
    if last is None:
        return
    elapsed_ms = (time.time() - last) * 1000
    threshold = getattr(config, 'RECORDER_WAIT_THRESHOLD_MS', RECORDER_WAIT_THRESHOLD_MS)
    if elapsed_ms >= threshold:
        actions.append(('wait', round(elapsed_ms)))
    return


@socketio.on('recorder_interact')
def handle_recorder_interact(data):
    """Handle interactive input events (click, type, navigate, stop, wait) for the embedded recorder."""
    recording_id = data.get('recording_id')
    action = data.get('action')

    recorder = active_recorders.get(recording_id)
    if not recorder:
        return

    loop = recorder['loop']
    page = recorder['page_ref'][0]
    actions = recorder['actions']

    if action == 'click' and page:
        _maybe_append_wait_before_action(recorder, actions)
        x = int(data.get('x', 0))
        y = int(data.get('y', 0))
        actions.append(('click', x, y))
        recorder['last_action_at'] = time.time()
        asyncio.run_coroutine_threadsafe(page.mouse.click(x, y), loop)

    elif action == 'type' and page:
        _maybe_append_wait_before_action(recorder, actions)
        text = data.get('text', '')
        actions.append(('type', text))
        recorder['last_action_at'] = time.time()
        asyncio.run_coroutine_threadsafe(page.keyboard.type(text), loop)

    elif action == 'key' and page:
        key = data.get('key', '')
        if key:
            recorder['last_action_at'] = time.time()
            asyncio.run_coroutine_threadsafe(page.keyboard.press(key), loop)

    elif action == 'navigate' and page:
        _maybe_append_wait_before_action(recorder, actions)
        nav_url = data.get('url', '')
        if nav_url:
            actions.append(('goto', nav_url))
            recorder['last_action_at'] = time.time()
            asyncio.run_coroutine_threadsafe(page.goto(nav_url), loop)

    elif action == 'wait':
        duration_ms = int(data.get('duration_ms', 0))
        if duration_ms > 0:
            _maybe_append_wait_before_action(recorder, actions)
            actions.append(('wait', duration_ms))
            recorder['last_action_at'] = time.time()

    elif action == 'stop':
        code = generate_code_from_actions(actions)
        loop.call_soon_threadsafe(recorder['stop_event'].set)
        socketio.emit('codegen_complete', {
            'recording_id': recording_id,
            'code': code,
            'name': recorder.get('test_name') or 'Recorded Test',
        })


async def run_test_async(task: str, test_filename: str = None, workspace_name: str = None):
    """Run the test with live updates."""
    global active_browser, stop_requested, current_ai_step

    stop_requested = False  # Reset stop flag
    socketio.emit('log', {'type': 'info', 'message': 'Initializing browser...'})

    # Create artifacts directory if this is an AI step test with filename
    artifact_dir = None
    video_dir = None
    saved_test_filename = test_filename  # Save filename before current_ai_step gets reset
    saved_workspace_name = workspace_name
    test_status = None  # Track test status for artifact metadata

    # Get filename and workspace_name from current_ai_step if not provided
    if current_ai_step:
        if not saved_test_filename:
            saved_test_filename = current_ai_step.get('filename')
        if not saved_workspace_name:
            saved_workspace_name = current_ai_step.get('workspace_name')

    if saved_test_filename:
        from pathlib import Path
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Use a temp directory for Playwright recording (moved to ~/.autogen/artifacts/ after run)
        artifact_dir = Path(tempfile.mkdtemp(prefix='awt_')) / timestamp
        artifact_dir.mkdir(parents=True, exist_ok=True)
        video_dir = str(artifact_dir)
        socketio.emit('log', {'type': 'info', 'message': f'📹 Video recording enabled'})

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
            browser.stream_task = asyncio.create_task(browser.start_streaming())

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
            if active_browser.stream_task:
                active_browser.stream_task.cancel()
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
                workspace_name=saved_workspace_name,
            )
            # Tell frontend to refresh now that artifacts are saved
            socketio.emit('artifacts_updated', {'filename': saved_test_filename})


def run_test_sync(task: str, test_filename: str = None, workspace_name: str = None):
    """Wrapper to run async test in sync context."""
    global active_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    active_loop = loop
    try:
        loop.run_until_complete(run_test_async(task, test_filename, workspace_name))
    finally:
        active_loop = None
        # Properly shutdown the event loop to avoid crashes
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
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


def run_playwright_code_with_streaming(
    code: str, filename: str = None, workspace_name: str = None, from_tree: bool = False
):
    """Execute Playwright code with automatic screenshot streaming to browser sidebar."""
    global stop_requested, active_loop, _active_test_task
    stop_requested = False  # Reset stop flag at the start of execution

    # Wait for the warm browser to be ready (instant on subsequent runs)
    _warm_ready.wait(timeout=15)
    loop = _warm_loop
    active_loop = loop

    # Create artifacts directory for this test run if filename provided
    artifact_dir = None
    video_dir = None
    test_status = None  # Track test status for artifact metadata
    if filename:
        print(f"🎬 Filename provided: {filename}, workspace_name: {workspace_name}")
        from pathlib import Path
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Use a temp directory for Playwright recording (moved to ~/.autogen/artifacts/ after run)
        artifact_dir = Path(tempfile.mkdtemp(prefix='awt_')) / timestamp
        artifact_dir.mkdir(parents=True, exist_ok=True)
        video_dir = str(artifact_dir)
        print(f"📹 Video directory created: {video_dir}")
        socketio.emit('log', {'type': 'info', 'message': f'📹 Video recording enabled'})
    else:
        print("⚠️  No filename provided - video recording disabled")

    async def execute_with_auto_streaming():
        """Execute code with automatic screenshot streaming after each action."""
        from playwright.async_api import async_playwright

        # Track all created browser wrappers for cleanup
        _all_browsers = []

        # Screenshot helper that will be available in user's code
        async def send_screenshot(page, action_name='action'):
            """Capture and send screenshot to browser sidebar."""
            try:
                screenshot_bytes = await page.screenshot(
                    type='jpeg',
                    quality=config.SCREENCAST_JPEG_QUALITY,
                    full_page=False
                )
                socketio.emit('screenshot', {
                    'action': action_name,
                    'image': base64.b64encode(screenshot_bytes).decode('utf-8'),
                    'timestamp': datetime.now().isoformat(),
                    'url': page.url,
                })
            except Exception as e:
                pass

        # Page wrapper that automatically captures screenshots
        class PageWrapper:
            """Wraps Playwright Page to automatically capture screenshots after actions."""

            def __init__(self, page):
                self._page = page
                self._streaming = False
                self._stream_task = None

            async def _start_streaming(self):
                """Stream screenshots via polling at high quality."""
                global stop_requested
                self._streaming = True
                while self._streaming:
                    try:
                        if stop_requested:
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
                global stop_requested
                if stop_requested:
                    raise asyncio.CancelledError("Test stopped by user")
                result = await self._page.goto(url, **kwargs)
                # Start streaming after first navigation
                if not self._stream_task:
                    self._stream_task = asyncio.create_task(self._start_streaming())
                return result

            async def click(self, selector, **kwargs):
                global stop_requested
                if stop_requested:
                    raise asyncio.CancelledError("Test stopped by user")
                return await self._page.click(selector, **kwargs)

            async def fill(self, selector, value, **kwargs):
                global stop_requested
                if stop_requested:
                    raise asyncio.CancelledError("Test stopped by user")
                return await self._page.fill(selector, value, **kwargs)

            async def type(self, selector, text, **kwargs):
                global stop_requested
                if stop_requested:
                    raise asyncio.CancelledError("Test stopped by user")
                return await self._page.type(selector, text, **kwargs)

            async def press(self, selector, key, **kwargs):
                global stop_requested
                if stop_requested:
                    raise asyncio.CancelledError("Test stopped by user")
                return await self._page.press(selector, key, **kwargs)

            async def screenshot(self, **kwargs):
                return await self._page.screenshot(**kwargs)

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
            def __init__(self, browser, default_context=None, owns_browser=True):
                self._browser = browser
                self._default_context = default_context
                self._contexts = []
                self._closed = False
                self._owns_browser = owns_browser  # False for the warm browser

            async def new_page(self):
                """Create new page with screenshot wrapper."""
                # If we have a default context (with video recording), use it
                if self._default_context:
                    return await self._default_context.new_page()
                else:
                    page = await self._browser.new_page()
                    return PageWrapper(page)

            async def new_context(self, **kwargs):
                """Create new context with wrapper and video recording if enabled."""
                # Add video recording parameters if video_dir is set
                if video_dir and 'record_video_dir' not in kwargs:
                    print(f"📹 Adding video recording to user-created context: {video_dir}")
                    kwargs['record_video_dir'] = video_dir
                    kwargs['record_video_size'] = {'width': config.VIDEO_SIZE_WIDTH, 'height': config.VIDEO_SIZE_HEIGHT}
                    kwargs.setdefault('viewport', {'width': config.VIDEO_SIZE_WIDTH, 'height': config.VIDEO_SIZE_HEIGHT})
                    # Also add HAR recording if not present
                    if 'record_har_path' not in kwargs:
                        kwargs['record_har_path'] = f"{video_dir}/network.har"
                context = await self._browser.new_context(**kwargs)
                wrapped = ContextWrapper(context)
                self._contexts.append(wrapped)
                return wrapped

            async def close(self):
                """Close all contexts and browser (browser only if not the shared warm instance)."""
                if self._closed:
                    return
                self._closed = True
                # Close all contexts first (finalizes video recordings)
                for ctx in self._contexts:
                    try:
                        await ctx.close()
                    except Exception:
                        pass
                if self._default_context:
                    if config.ENABLE_TRACE_RECORDING and video_dir:
                        try:
                            await self._default_context.tracing.stop(path=f"{video_dir}/trace.zip")
                        except Exception:
                            pass
                    try:
                        await self._default_context.close()
                    except Exception:
                        pass
                # Only close the underlying browser if we own it (not the warm browser)
                if self._owns_browser:
                    try:
                        await self._browser.close()
                    except Exception:
                        pass

            def __getattr__(self, name):
                return getattr(self._browser, name)

        # Playwright wrapper
        class PlaywrightWrapper:
            def __init__(self, playwright):
                self._playwright = playwright

            @property
            def chromium(self):
                return LauncherWrapper(self._playwright.chromium if self._playwright else None)

            @property
            def firefox(self):
                return LauncherWrapper(self._playwright.firefox if self._playwright else None)

            @property
            def webkit(self):
                return LauncherWrapper(self._playwright.webkit if self._playwright else None)

            def __getattr__(self, name):
                if self._playwright is None:
                    raise AttributeError(name)
                return getattr(self._playwright, name)

        # Browser launcher wrapper
        class LauncherWrapper:
            def __init__(self, launcher):
                self._launcher = launcher

            async def launch(self, **kwargs):
                """Return the pre-warmed browser (or launch fresh if warm browser is unavailable)."""
                owns = False
                if _warm_browser and _warm_browser.is_connected():
                    browser = _warm_browser
                else:
                    # Fall back to a fresh launch if the warm browser died
                    kwargs['headless'] = True
                    browser = await self._launcher.launch(**kwargs)
                    owns = True

                # Create a fresh context per test (needed for video recording + clean state)
                default_context = None
                if video_dir:
                    context_options = {
                        'record_video_dir': video_dir,
                        'record_video_size': {'width': config.VIDEO_SIZE_WIDTH, 'height': config.VIDEO_SIZE_HEIGHT},
                        'viewport': {'width': config.VIDEO_SIZE_WIDTH, 'height': config.VIDEO_SIZE_HEIGHT},
                        'record_har_path': f"{video_dir}/network.har",
                    }
                    raw_context = await browser.new_context(**context_options)
                    if config.ENABLE_TRACE_RECORDING:
                        await raw_context.tracing.start(screenshots=True, snapshots=True)
                    default_context = ContextWrapper(raw_context)

                wrapped_browser = BrowserWrapper(browser, default_context, owns_browser=owns)
                _all_browsers.append(wrapped_browser)
                return wrapped_browser

            def __getattr__(self, name):
                return getattr(self._launcher, name)

        # Custom async_playwright that returns wrapped version backed by the warm browser
        class async_playwright_wrapper:
            async def __aenter__(self):
                # Return a PlaywrightWrapper; actual browser comes from the warm pool
                return PlaywrightWrapper(None)

            async def __aexit__(self, *args):
                # Close all contexts (finalizes video recordings) but keep the warm browser alive
                for bw in _all_browsers:
                    try:
                        await bw.close()
                    except Exception:
                        pass

        try:
            nonlocal test_status
            # Remove asyncio.run(...) call and all playwright/asyncio imports
            # using regex so any variation of the import line is handled
            modified_code = re.sub(r'asyncio\.run\(\s*\w+\(\)\s*\)', '', code)
            modified_code = re.sub(r'^from playwright\.[^\n]*\n?', '', modified_code, flags=re.MULTILINE)
            modified_code = re.sub(r'^import playwright[^\n]*\n?', '', modified_code, flags=re.MULTILINE)
            modified_code = re.sub(r'^import asyncio\n?', '', modified_code, flags=re.MULTILINE)

            # Log the modified code for debugging
            print("=" * 50)
            print("Modified code to execute:")
            print(modified_code)
            print("=" * 50)

            # Execute user's code with wrapped Playwright
            # Import common Playwright symbols the user code might reference
            from playwright.async_api import (
                expect as _pw_expect,
                Page as _pw_Page,
                Browser as _pw_Browser,
                BrowserContext as _pw_BrowserContext,
                Locator as _pw_Locator,
                ElementHandle as _pw_ElementHandle,
                TimeoutError as _pw_TimeoutError,
            )
            exec_globals = {
                'asyncio': asyncio,
                'async_playwright': async_playwright_wrapper,
                'base64': base64,
                'datetime': datetime,
                'socketio': socketio,
                # Playwright public API
                'expect': _pw_expect,
                'Page': _pw_Page,
                'Browser': _pw_Browser,
                'BrowserContext': _pw_BrowserContext,
                'Locator': _pw_Locator,
                'ElementHandle': _pw_ElementHandle,
                'TimeoutError': _pw_TimeoutError,
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

    async def _run_and_register():
        """Wrap execution so the task can be targeted by the stop handler."""
        global _active_test_task
        _active_test_task = asyncio.current_task()
        try:
            await execute_with_auto_streaming()
        finally:
            _active_test_task = None

    try:
        future = asyncio.run_coroutine_threadsafe(_run_and_register(), loop)
        future.result()  # Block the background thread until the test finishes
    except Exception as e:
        import traceback
        test_status = 'error'
        socketio.emit('log', {'type': 'error', 'message': f'Execution error: {str(e)}'})
        socketio.emit('log', {'type': 'error', 'message': f'Traceback: {traceback.format_exc()}'})
        socketio.emit('test_complete', {'status': 'error'})
    finally:
        active_loop = None
        _active_test_task = None

    # Update test artifacts AFTER loop cleanup (separate block so it always runs)
    print(f"📼 === ARTIFACT SAVE BLOCK REACHED === artifact_dir={artifact_dir}, filename={filename}, workspace_name={workspace_name}")
    if artifact_dir and filename:
        try:
            import time
            time.sleep(5)  # Give browser time to finalize the video file
            print(f"📼 Saving artifacts: filename={filename}, workspace_name={workspace_name}, status={test_status}, dir={artifact_dir}")
            # List all files in artifact dir for debugging
            all_files = list(artifact_dir.iterdir()) if artifact_dir.exists() else []
            print(f"📼 All files in artifact dir: {all_files}")
            video_files = list(artifact_dir.glob("*.webm")) + list(artifact_dir.glob("*.mp4"))
            print(f"📼 Found video files: {video_files}")
            update_test_artifacts(
                filename,
                artifact_dir,
                test_status or 'unknown',
                workspace_name=workspace_name,
            )
            # Tell frontend to refresh now that artifacts are saved
            socketio.emit('artifacts_updated', {'filename': filename})
        except Exception as e:
            import traceback
            print(f"📼 Error saving artifacts: {e}")
            traceback.print_exc()
    else:
        print(f"⚠️ Skipping artifact update: artifact_dir={artifact_dir}, filename={filename}")


def run_playwright_code_headless(code: str, filename: str, workspace_name: str = None):
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


VALID_THEMES = {'mocha', 'macchiato', 'frappe', 'latte'}

@app.route('/')
def index():
    """Render main page."""
    is_cloud = bool(os.environ.get('K_SERVICE') or os.environ.get('CLOUD_RUN_JOB') or os.environ.get('GAE_ENV'))
    # File-backed prefs take priority; cookie is fallback for web deployments
    prefs = _read_prefs()
    theme = prefs.get('theme') or request.cookies.get('theme', 'mocha')
    if theme not in VALID_THEMES:
        theme = 'mocha'
    return render_template('index.html', is_cloud=is_cloud, theme=theme)


@app.route('/api/config/ai-status', methods=['GET'])
@login_required
def ai_status():
    """Return whether an OpenAI API key is configured."""
    has_key = bool(os.environ.get('OPENAI_API_KEY', '').strip())
    return jsonify({'ai_enabled': has_key}), 200


# ========== USER PREFERENCES (file-backed, ~/.autogen/preferences/) ==========

_PREFS_DIR = Path.home() / '.autogen' / 'preferences'
_PREFS_FILE = _PREFS_DIR / 'user_prefs.json'
_ALLOWED_PREF_KEYS = {'theme', 'selectedWorkspaceName', 'editorTabsState',
                      'fileExplorerWidth', 'aiChatWidth'}


def _read_prefs() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_prefs(prefs: dict) -> None:
    _PREFS_DIR.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))


@app.route('/api/preferences', methods=['GET'])
@login_required
def get_preferences():
    return jsonify(_read_prefs()), 200


@app.route('/api/preferences', methods=['PATCH'])
@login_required
def patch_preferences():
    updates = request.get_json(force=True) or {}
    prefs = _read_prefs()
    for key, value in updates.items():
        if key in _ALLOWED_PREF_KEYS:
            prefs[key] = value
    _write_prefs(prefs)
    return jsonify(prefs), 200


# ========== WORKSPACE MANAGEMENT API ENDPOINTS ==========

_WORKSPACE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\- ]+$')


def _validate_workspace_name(name: str) -> str | None:
    """Return cleaned name or None if invalid."""
    name = name.strip()
    if not name:
        return None
    if '..' in name or '/' in name:
        return None
    if not _WORKSPACE_NAME_RE.match(name):
        return None
    return name


@app.route('/api/workspaces', methods=['GET'])
@login_required
def get_workspaces():
    """List workspace subdirectories under AUTOGEN_WORKSPACES_DIR."""
    try:
        base = Config.AUTOGEN_WORKSPACES_DIR
        base.mkdir(parents=True, exist_ok=True)
        workspaces = [
            {'name': d.name}
            for d in sorted(base.iterdir(), key=lambda p: p.name.lower())
            if d.is_dir()
        ]
        return jsonify({'workspaces': workspaces}), 200
    except Exception as e:
        print(f"Error listing workspaces: {e}")
        return jsonify({'error': 'Failed to list workspaces'}), 500


@app.route('/api/workspaces', methods=['POST'])
@login_required
def create_workspace():
    """Create a new workspace directory, optionally cloning from a git URL."""
    try:
        data = request.get_json() or {}
        name = _validate_workspace_name(data.get('name', ''))
        if not name:
            return jsonify({'error': 'Workspace name must be non-empty and may only contain letters, numbers, spaces, hyphens, and underscores'}), 400

        ws_dir = Config.AUTOGEN_WORKSPACES_DIR / name
        if ws_dir.exists():
            return jsonify({'error': 'A workspace with that name already exists'}), 409

        clone_url = data.get('clone_url', '').strip()
        if clone_url:
            try:
                git_ops.clone_repo(clone_url, ws_dir)
            except Exception as e:
                return jsonify({'error': f'Clone failed: {e}'}), 400
            (ws_dir / 'saved_tests').mkdir(exist_ok=True)
            (ws_dir / 'ai_steps').mkdir(exist_ok=True)
        else:
            ws_dir.mkdir(parents=True, exist_ok=True)
            (ws_dir / 'saved_tests').mkdir(exist_ok=True)
            (ws_dir / 'ai_steps').mkdir(exist_ok=True)
            git_ops.init_repo(ws_dir)
        # Ensure .github-config.json is never committed
        gitignore_path = ws_dir / '.gitignore'
        gitignore_entry = '.github-config.json\n'
        if gitignore_path.exists():
            existing = gitignore_path.read_text()
            if '.github-config.json' not in existing:
                gitignore_path.write_text(existing + gitignore_entry)
        else:
            gitignore_path.write_text(gitignore_entry)

        return jsonify({'message': 'Workspace created', 'workspace': {'name': name}}), 201

    except Exception as e:
        print(f"Error creating workspace: {e}")
        return jsonify({'error': 'Failed to create workspace'}), 500


@app.route('/api/workspaces/<workspace_name>', methods=['PUT'])
@login_required
def rename_workspace(workspace_name):
    """Rename a workspace directory."""
    data = request.get_json() or {}
    new_name = _validate_workspace_name(data.get('name', ''))
    if not new_name:
        return jsonify({'error': 'Workspace name must be non-empty and may only contain letters, numbers, spaces, hyphens, and underscores'}), 400

    old_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name
    if not old_dir.is_dir():
        return jsonify({'error': 'Workspace not found'}), 404

    new_dir = Config.AUTOGEN_WORKSPACES_DIR / new_name
    if new_dir.exists():
        return jsonify({'error': 'A workspace with that name already exists'}), 409

    try:
        old_dir.rename(new_dir)
        return jsonify({'workspace': {'name': new_name}}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>', methods=['DELETE'])
@login_required
def delete_workspace(workspace_name):
    """Delete a workspace directory."""
    import shutil
    name = _validate_workspace_name(workspace_name)
    if not name:
        return jsonify({'error': 'Invalid workspace name'}), 400

    ws_dir = Config.AUTOGEN_WORKSPACES_DIR / name
    if not ws_dir.is_dir():
        return jsonify({'error': 'Workspace not found'}), 404

    try:
        shutil.rmtree(ws_dir)
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error deleting workspace: {e}")
        return jsonify({'error': 'Failed to delete workspace'}), 500


# ========== END WORKSPACE MANAGEMENT API ENDPOINTS ==========


# ========== GIT API ENDPOINTS ==========

def _ws_dir(workspace_name: str) -> Path:
    return Config.AUTOGEN_WORKSPACES_DIR / workspace_name


def _ensure_git_repo(workspace_name: str) -> None:
    """Silently initialize a git repo if the workspace dir has no .git/."""
    ws = _ws_dir(workspace_name)
    if ws.is_dir() and not (ws / '.git').exists():
        try:
            git_ops.init_repo(ws)
        except Exception:
            pass


def _enrich_tree_git_status(nodes: list, git_status: dict) -> None:
    """
    Annotate file nodes in-place with git_status: 'M'|'A'|'D'|None.
    git_status is the result of git_ops.get_status().
    """
    staged_map = {item['path']: item['status'] for item in git_status.get('staged', [])}
    unstaged_map = {item['path']: item['status'] for item in git_status.get('unstaged', [])}
    untracked = set(git_status.get('untracked', []))

    _GIT_STATUS_MAP = {'A': 'A', 'M': 'M', 'D': 'D', 'R': 'R'}

    def _annotate(node_list):
        for node in node_list:
            if node.get('type') == 'file':
                p = node.get('path', '')
                if p in staged_map:
                    node['git_status'] = _GIT_STATUS_MAP.get(staged_map[p], 'M')
                elif p in unstaged_map:
                    node['git_status'] = _GIT_STATUS_MAP.get(unstaged_map[p], 'M')
                elif p in untracked:
                    node['git_status'] = 'U'
                else:
                    node['git_status'] = None
            elif node.get('type') == 'folder':
                _annotate(node.get('children', []))

    _annotate(nodes)


@app.route('/api/workspaces/<workspace_name>/git/status', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def git_status(workspace_name):
    try:
        _ensure_git_repo(workspace_name)
        status = git_ops.get_status(_ws_dir(workspace_name))
        return jsonify(status), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("git status error: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/git/stage', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_stage(workspace_name):
    data = request.get_json() or {}
    filepath = data.get('path', '').strip()
    if not filepath:
        return jsonify({'error': 'path is required'}), 400
    try:
        git_ops.stage_file(_ws_dir(workspace_name), filepath)
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/unstage', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_unstage(workspace_name):
    data = request.get_json() or {}
    filepath = data.get('path', '').strip()
    if not filepath:
        return jsonify({'error': 'path is required'}), 400
    try:
        git_ops.unstage_file(_ws_dir(workspace_name), filepath)
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/stage_all', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_stage_all(workspace_name):
    try:
        git_ops.stage_all(_ws_dir(workspace_name))
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/commit', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_commit(workspace_name):
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Commit message is required'}), 400
    try:
        sha = git_ops.commit(_ws_dir(workspace_name), message)
        return jsonify({'success': True, 'sha': sha}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/push', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_push(workspace_name):
    data = request.get_json() or {}
    ws_dir = _ws_dir(workspace_name)
    token = data.get('token') or github_config.decrypt_token(ws_dir)
    try:
        git_ops.push(
            ws_dir,
            remote=data.get('remote', 'origin'),
            branch=data.get('branch') or None,
            token=token,
        )
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/pull', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_pull(workspace_name):
    data = request.get_json() or {}
    try:
        git_ops.pull(
            _ws_dir(workspace_name),
            remote=data.get('remote', 'origin'),
            branch=data.get('branch') or None,
        )
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/branches', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def git_branches(workspace_name):
    try:
        branches = git_ops.get_branches(_ws_dir(workspace_name))
        return jsonify(branches), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/checkout', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def git_checkout(workspace_name):
    data = request.get_json() or {}
    branch = data.get('branch', '').strip()
    if not branch:
        return jsonify({'error': 'branch is required'}), 400
    create = bool(data.get('create', False))
    try:
        git_ops.checkout_branch(_ws_dir(workspace_name), branch, create=create)
        return jsonify({'success': True}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/diff', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def git_diff(workspace_name):
    filepath = request.args.get('path', '').strip()
    staged = request.args.get('staged', '0') == '1'
    if not filepath:
        return jsonify({'error': 'path is required'}), 400
    try:
        diff = git_ops.get_diff(_ws_dir(workspace_name), filepath, staged=staged)
        return jsonify({'diff': diff}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/workspaces/<workspace_name>/git/log', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def git_log(workspace_name):
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        limit = 20
    try:
        commits = git_ops.get_log(_ws_dir(workspace_name), max_count=limit)
        return jsonify({'commits': commits}), 200
    except (ValueError, git.exc.GitCommandError) as e:
        return jsonify({'error': str(e)}), 400


# ========== GITHUB API ENDPOINTS ==========


def _parse_github_repo(remote_url: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a GitHub HTTPS or SSH remote URL, or None."""
    import re
    patterns = [
        r'github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$',
    ]
    for pat in patterns:
        m = re.search(pat, remote_url)
        if m:
            return m.group(1), m.group(2)
    return None


@app.route('/api/workspaces/<workspace_name>/github/config', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_github_config(workspace_name):
    ws_dir = _ws_dir(workspace_name)
    cfg = github_config.get_config(ws_dir)
    if not cfg:
        return jsonify({'connected': False}), 200
    remote_url = cfg.get('remote_url', '')
    parsed = _parse_github_repo(remote_url)
    return jsonify({
        'connected': True,
        'remote_url': remote_url,
        'owner': parsed[0] if parsed else None,
        'repo': parsed[1] if parsed else None,
    }), 200


@app.route('/api/workspaces/<workspace_name>/github/connect', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def github_connect(workspace_name):
    data = request.get_json(force=True) or {}
    remote_url = data.get('remote_url', '').strip()
    pat = data.get('pat', '').strip()
    if not remote_url or not pat:
        return jsonify({'error': 'remote_url and pat are required'}), 400
    if not _parse_github_repo(remote_url):
        return jsonify({'error': 'URL does not look like a GitHub repo'}), 400
    # Verify token against GitHub API
    headers = {'Authorization': f'token {pat}', 'Accept': 'application/vnd.github+json'}
    try:
        r = _requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if r.status_code == 401:
            return jsonify({'error': 'Invalid PAT — authentication failed'}), 400
        r.raise_for_status()
    except _requests.RequestException as exc:
        return jsonify({'error': f'GitHub API error: {exc}'}), 502
    ws_dir = _ws_dir(workspace_name)
    github_config.save_config(ws_dir, remote_url, pat)
    git_ops.add_remote(ws_dir, remote_url)
    parsed = _parse_github_repo(remote_url)
    return jsonify({
        'connected': True,
        'remote_url': remote_url,
        'owner': parsed[0] if parsed else None,
        'repo': parsed[1] if parsed else None,
    }), 200


@app.route('/api/workspaces/<workspace_name>/github/create-repo', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def github_create_repo(workspace_name):
    data = request.get_json(force=True) or {}
    pat = data.get('pat', '').strip()
    repo_name = data.get('repo_name', '').strip()
    private = bool(data.get('private', True))
    description = data.get('description', '').strip()
    if not pat or not repo_name:
        return jsonify({'error': 'pat and repo_name are required'}), 400
    headers = {
        'Authorization': f'token {pat}',
        'Accept': 'application/vnd.github+json',
    }
    payload = {'name': repo_name, 'private': private, 'description': description, 'auto_init': False}
    try:
        r = _requests.post('https://api.github.com/user/repos', json=payload, headers=headers, timeout=15)
        if r.status_code == 401:
            return jsonify({'error': 'Invalid PAT — authentication failed'}), 400
        if r.status_code == 422:
            return jsonify({'error': 'Repository name already exists or is invalid'}), 400
        r.raise_for_status()
        remote_url = r.json().get('clone_url', '')
    except _requests.RequestException as exc:
        return jsonify({'error': f'GitHub API error: {exc}'}), 502
    ws_dir = _ws_dir(workspace_name)
    github_config.save_config(ws_dir, remote_url, pat)
    git_ops.add_remote(ws_dir, remote_url)
    parsed = _parse_github_repo(remote_url)
    return jsonify({
        'connected': True,
        'remote_url': remote_url,
        'owner': parsed[0] if parsed else None,
        'repo': parsed[1] if parsed else None,
    }), 200


@app.route('/api/workspaces/<workspace_name>/github/disconnect', methods=['DELETE'])
@login_required
@workspace_access_required(permission='write')
def github_disconnect(workspace_name):
    ws_dir = _ws_dir(workspace_name)
    git_ops.remove_remote(ws_dir)
    github_config.delete_config(ws_dir)
    return jsonify({'connected': False}), 200


# ========== END GIT API ENDPOINTS ==========


# ========== LOCAL TREE API (Saved Tests / AI Steps under ~/.autogen/workspaces) ==========

def _tree_root(workspace_name: str, tree_type: str) -> Path:
    return Config.AUTOGEN_WORKSPACES_DIR / workspace_name / tree_type


def _remap_git_status_for_subtree(git_status: dict, subtree: str) -> dict:
    """
    Remap git status paths so they are relative to the subtree directory
    (e.g. 'saved_tests/foo.py' → 'foo.py').
    """
    prefix = subtree.rstrip('/') + '/'

    def _remap_items(items):
        result = []
        for item in items:
            path = item.get('path', '')
            if path.startswith(prefix):
                result.append({'path': path[len(prefix):], 'status': item['status']})
        return result

    untracked = [p[len(prefix):] for p in git_status.get('untracked', []) if p.startswith(prefix)]

    return {
        'staged': _remap_items(git_status.get('staged', [])),
        'unstaged': _remap_items(git_status.get('unstaged', [])),
        'untracked': untracked,
    }


def _collect_tree_paths(nodes: list) -> set:
    """Return set of all file paths in tree (for merging DB items)."""
    paths = set()
    for node in nodes:
        if node.get("type") == "file" and node.get("path"):
            paths.add(node["path"])
        if node.get("children"):
            paths.update(_collect_tree_paths(node["children"]))
    return paths


def _enrich_tree_artifacts(nodes: list, workspace_name: str, root: Path) -> None:
    """Mutate file nodes in tree to add artifacts and last_run meta from disk."""
    artifacts_base = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / "saved_tests" / "artifacts"
    for node in nodes:
        if node.get("type") == "folder" and node.get("children"):
            _enrich_tree_artifacts(node["children"], workspace_name, root)
        elif node.get("type") == "file" and node.get("path"):
            path = node["path"]
            test_name = path.replace("/", "_").replace("\\", "_")
            if test_name.endswith(".py"):
                test_name = test_name[:-3]
            art_dir = artifacts_base / test_name
            artifacts = []
            if (art_dir / "recording.webm").exists():
                artifacts.append({
                    "video_path": f"{workspace_name}/saved_tests/artifacts/{test_name}/recording.webm",
                    "trace_path": f"{workspace_name}/saved_tests/artifacts/{test_name}/trace.zip" if (art_dir / "trace.zip").exists() else None,
                })
            elif (art_dir / "trace.zip").exists():
                artifacts.append({"trace_path": f"{workspace_name}/saved_tests/artifacts/{test_name}/trace.zip"})
            if artifacts:
                node["artifacts"] = artifacts
            try:
                meta = local_tree.get_last_run_meta(root, path)
                if meta:
                    node["last_run_status"] = meta.get("last_run_status")
                    node["last_run_time"] = meta.get("last_run_time")
            except Exception:
                pass


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_tree_saved_tests(workspace_name):
    """Get folder tree for Saved Tests (local filesystem only)."""
    try:
        _ensure_git_repo(workspace_name)
        root = _tree_root(workspace_name, "saved_tests")
        root.mkdir(parents=True, exist_ok=True)
        children = local_tree.list_tree(root, "saved_tests")
        _enrich_tree_artifacts(children, workspace_name, root)
        try:
            status = git_ops.get_status(_ws_dir(workspace_name))
            # Remap paths relative to saved_tests/ root
            _enrich_tree_git_status(children, _remap_git_status_for_subtree(status, 'saved_tests'))
        except Exception:
            pass
        return jsonify({"tree": children}), 200
    except Exception as e:
        app.logger.exception("Error listing saved_tests tree: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_tree_ai_steps(workspace_name):
    """Get folder tree for AI Steps (local filesystem only)."""
    try:
        _ensure_git_repo(workspace_name)
        root = _tree_root(workspace_name, "ai_steps")
        root.mkdir(parents=True, exist_ok=True)
        children = local_tree.list_tree(root, "ai_steps")
        try:
            status = git_ops.get_status(_ws_dir(workspace_name))
            _enrich_tree_git_status(children, _remap_git_status_for_subtree(status, 'ai_steps'))
        except Exception:
            pass
        return jsonify({"tree": children}), 200
    except Exception as e:
        app.logger.exception("Error listing ai_steps tree: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def post_tree_saved_tests(workspace_name):
    """Create a folder under Saved Tests. Body: { "path": "folder/sub", "type": "folder" }."""
    try:
        data = request.get_json() or {}
        path = (data.get("path") or "").strip().strip("/")
        if not path or data.get("type") != "folder":
            return jsonify({'error': 'path and type: "folder" required'}), 400
        root = _tree_root(workspace_name, "saved_tests")
        root.mkdir(parents=True, exist_ok=True)
        local_tree.create_folder(root, path)
        return jsonify({"success": True, "path": path}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error creating folder: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def post_tree_ai_steps(workspace_name):
    """Create a folder under AI Steps. Body: { "path": "folder/sub", "type": "folder" }."""
    try:
        data = request.get_json() or {}
        path = (data.get("path") or "").strip().strip("/")
        if not path or data.get("type") != "folder":
            return jsonify({'error': 'path and type: "folder" required'}), 400
        root = _tree_root(workspace_name, "ai_steps")
        root.mkdir(parents=True, exist_ok=True)
        local_tree.create_folder(root, path)
        return jsonify({"success": True, "path": path}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error creating folder: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests/move', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def move_tree_saved_test(workspace_name):
    """Move a file or folder. Body: { "from": "path", "to": "path" }."""
    try:
        data = request.get_json() or {}
        from_path = (data.get("from") or "").strip().strip("/")
        to_path = (data.get("to") or "").strip().strip("/")
        if not from_path or not to_path:
            return jsonify({'error': 'from and to are required'}), 400
        if from_path == to_path:
            return jsonify({'error': 'Source and destination are the same'}), 400
        root = _tree_root(workspace_name, "saved_tests")
        root.mkdir(parents=True, exist_ok=True)
        local_tree.move_path(root, from_path, to_path, "saved_tests")
        return jsonify({"success": True, "to": to_path}), 200
    except FileNotFoundError:
        return jsonify({'error': 'Source not found (only items in the file tree can be moved)'}), 404
    except ValueError as e:
        err = str(e)
        if "already exists" in err.lower():
            return jsonify({'error': err}), 409
        return jsonify({'error': err}), 400
    except Exception as e:
        app.logger.exception("Error moving: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps/move', methods=['POST'])
@login_required
@workspace_access_required(permission='write')
def move_tree_ai_step(workspace_name):
    """Move a file or folder. Body: { "from": "path", "to": "path" }."""
    try:
        data = request.get_json() or {}
        from_path = (data.get("from") or "").strip().strip("/")
        to_path = (data.get("to") or "").strip().strip("/")
        if not from_path or not to_path:
            return jsonify({'error': 'from and to are required'}), 400
        if from_path == to_path:
            return jsonify({'error': 'Source and destination are the same'}), 400
        root = _tree_root(workspace_name, "ai_steps")
        root.mkdir(parents=True, exist_ok=True)
        local_tree.move_path(root, from_path, to_path, "ai_steps")
        return jsonify({"success": True, "to": to_path}), 200
    except FileNotFoundError:
        return jsonify({'error': 'Source not found (only items in the file tree can be moved)'}), 404
    except ValueError as e:
        err = str(e)
        if "already exists" in err.lower():
            return jsonify({'error': err}), 409
        return jsonify({'error': err}), 400
    except Exception as e:
        app.logger.exception("Error moving: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests/<path:filepath>', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_tree_saved_test_file(workspace_name, filepath):
    """Get a single Saved Test file content by path (disk only)."""
    try:
        root = _tree_root(workspace_name, "saved_tests")
        data = local_tree.get_file_content(root, filepath, "saved_tests")
        meta = local_tree.get_last_run_meta(root, filepath)
        if meta:
            data["last_run_status"] = meta.get("last_run_status")
            data["last_run_time"] = meta.get("last_run_time")
        return jsonify(data), 200
    except FileNotFoundError:
        return jsonify({'error': 'Test not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error reading test: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests/<path:filepath>', methods=['PUT'])
@login_required
@workspace_access_required(permission='write')
def put_tree_saved_test_file(workspace_name, filepath):
    """Create or update a Saved Test file. Body: { "name", "code" }."""
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        code = data.get("code", "")
        root = _tree_root(workspace_name, "saved_tests")
        root.mkdir(parents=True, exist_ok=True)
        result = local_tree.create_or_update_file(root, filepath, "saved_tests", name=name, code=code)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error writing test: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/saved_tests/<path:filepath>', methods=['DELETE'])
@login_required
@workspace_access_required(permission='write')
def delete_tree_saved_test(workspace_name, filepath):
    """Delete a Saved Test file or folder."""
    try:
        root = _tree_root(workspace_name, "saved_tests")
        local_tree.delete_path(root, filepath)
        return jsonify({"success": True}), 200
    except FileNotFoundError:
        return jsonify({'error': 'Not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error deleting: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps/<path:filepath>', methods=['GET'])
@login_required
@workspace_access_required(permission='read')
def get_tree_ai_step_file(workspace_name, filepath):
    """Get a single AI Step file content by path (disk only)."""
    try:
        root = _tree_root(workspace_name, "ai_steps")
        data = local_tree.get_file_content(root, filepath, "ai_steps")
        meta = local_tree.get_last_run_meta(root, filepath)
        if meta:
            data["last_run_status"] = meta.get("last_run_status")
            data["last_run_time"] = meta.get("last_run_time")
        return jsonify(data), 200
    except FileNotFoundError:
        return jsonify({'error': 'AI step not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error reading AI step: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps/<path:filepath>', methods=['PUT'])
@login_required
@workspace_access_required(permission='write')
def put_tree_ai_step_file(workspace_name, filepath):
    """Create or update an AI Step file. Body: { "name", "steps" }."""
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        steps = data.get("steps", "")
        root = _tree_root(workspace_name, "ai_steps")
        root.mkdir(parents=True, exist_ok=True)
        result = local_tree.create_or_update_file(root, filepath, "ai_steps", name=name, steps=steps)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error writing AI step: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces/<workspace_name>/tree/ai_steps/<path:filepath>', methods=['DELETE'])
@login_required
@workspace_access_required(permission='write')
def delete_tree_ai_step(workspace_name, filepath):
    """Delete an AI Step file or folder."""
    try:
        root = _tree_root(workspace_name, "ai_steps")
        local_tree.delete_path(root, filepath)
        return jsonify({"success": True}), 200
    except FileNotFoundError:
        return jsonify({'error': 'Not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Error deleting: %s", e)
        return jsonify({'error': str(e)}), 500


# ========== END LOCAL TREE API ==========


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

    # Temp file for codegen output (real Playwright Chromium window + Inspector)
    output_file = str(TEMP_RECORDINGS_DIR / f'codegen_{recording_id}.py')

    # Start real Playwright codegen subprocess in background (opens Chromium + Inspector)
    socketio.start_background_task(
        run_codegen_process,
        recording_id=recording_id,
        url=url,
        output_file=output_file,
        test_name=test_name,
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

    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'No workspace found'}), 400

    try:
        result = db.create_test(ws_id, name, code, source, get_current_user()['id'])
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
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify([])
    tests = db.get_tests(ws_id)
    return jsonify(tests)


@app.route('/api/recent-recordings')
@login_required
def get_recent_recordings():
    """Get recent video recordings for the current workspace."""
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        artifacts_base = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / 'saved_tests' / 'artifacts'
        recordings = []
        if artifacts_base.is_dir():
            for entry in sorted(artifacts_base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if not entry.is_dir():
                    continue
                video = entry / 'recording.webm'
                if not video.exists():
                    continue
                status_file = entry / 'status.json'
                status = 'unknown'
                timestamp = ''
                if status_file.exists():
                    import json as _json
                    try:
                        sd = _json.loads(status_file.read_text(encoding='utf-8'))
                        status = sd.get('status', 'unknown')
                        timestamp = sd.get('timestamp', '')
                    except Exception:
                        pass
                if not timestamp:
                    from datetime import datetime as _dt
                    timestamp = _dt.utcfromtimestamp(video.stat().st_mtime).isoformat()
                test_name = entry.name.replace('_', ' ')
                recordings.append({
                    'test_filename': entry.name,
                    'test_name': test_name,
                    'status': status,
                    'timestamp': timestamp,
                })
        return jsonify(recordings)
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify([])
    recordings = db.get_recent_recordings(ws_id)
    return jsonify(recordings)


@app.route('/api/saved-tests/<filename>', methods=['GET'])
@login_required
def get_saved_test(filename):
    """Get a specific saved test."""
    ws_id = _get_workspace_id()
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
    ws_id = _get_workspace_id()
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'saved_tests')
        local_tree.write_last_run_meta(
            root, filename, status=status, last_run_time=datetime.utcnow().isoformat()
        )
        return jsonify({'success': True})
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

    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'No workspace found'}), 400

    try:
        result = db.create_ai_step(ws_id, name, steps, get_current_user()['id'])
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'ai_steps')
        try:
            data = local_tree.get_file_content(root, filename, 'ai_steps')
            return jsonify(data)
        except FileNotFoundError:
            return jsonify({'error': 'AI step not found'}), 404
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'ai_steps')
        steps = data.get('steps', '')
        name = data.get('name')
        try:
            local_tree.create_or_update_file(root, filename, 'ai_steps', name=name, steps=steps)
            return jsonify({'success': True})
        except (ValueError, FileNotFoundError) as e:
            return jsonify({'error': str(e)}), 400
    ws_id = _get_workspace_id()
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'ai_steps')
        try:
            local_tree.delete_path(root, filename)
            return jsonify({'success': True})
        except FileNotFoundError:
            return jsonify({'error': 'AI step not found'}), 404
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'ai_steps')
        try:
            data = local_tree.get_file_content(root, filename, 'ai_steps')
            return jsonify({'markdown': data.get('steps', ''), 'filename': filename})
        except FileNotFoundError:
            return jsonify({'error': 'AI step not found'}), 404
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
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        root = _tree_root(workspace_name, 'ai_steps')
        try:
            local_tree.create_or_update_file(root, filename, 'ai_steps', steps=markdown_content.strip())
            return jsonify({'success': True})
        except (ValueError, FileNotFoundError) as e:
            return jsonify({'error': str(e)}), 400
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'AI step not found'}), 404
    result = db.update_ai_step(ws_id, filename, steps=markdown_content.strip())
    if not result:
        return jsonify({'error': 'AI step not found'}), 404
    return jsonify({'success': True})


@app.route('/api/artifacts/<path:filepath>')
@login_required
def serve_artifact(filepath):
    """Return the local video URL for a test artifact."""
    return jsonify({'url': f'/api/video/{filepath}'}), 200


@app.route('/api/trace/<path:filepath>')
def serve_trace(filepath):
    """Serve a Playwright trace.zip file from ~/.autogen/workspaces/."""
    from flask import send_file
    from config import Config

    base = Config.AUTOGEN_WORKSPACES_DIR.resolve()
    full_path = (base / filepath).resolve()
    if not str(full_path).startswith(str(base)):
        return jsonify({'error': 'Forbidden'}), 403
    if not full_path.exists():
        return jsonify({'error': 'Trace not found'}), 404
    return send_file(full_path, mimetype='application/zip')


@app.route('/live-viewer/')
@app.route('/live-viewer')
def live_viewer():
    """Serve the embedded live browser viewer page (similar to trace viewer)."""
    return render_template('live_viewer.html')


@app.route('/trace-viewer/')
@app.route('/trace-viewer')
def trace_viewer_index():
    """Serve the Playwright trace viewer index page."""
    from flask import send_from_directory
    return send_from_directory(str(_TRACE_VIEWER_DIR), 'index.html')


@app.route('/trace-viewer/<path:filepath>')
def trace_viewer_static(filepath):
    """Serve Playwright trace viewer static assets from the bundled package."""
    from flask import send_from_directory
    return send_from_directory(str(_TRACE_VIEWER_DIR), filepath)


@app.route('/api/video/<path:filepath>')
def stream_video(filepath):
    """Stream a local artifact file (video or HAR) from ~/.autogen/workspaces/.

    No auth header needed — the browser <video> element fetches this directly.
    Path-traversal is prevented by checking the resolved path stays inside AUTOGEN_WORKSPACES_DIR.
    """
    from flask import send_file
    from config import Config

    base = Config.AUTOGEN_WORKSPACES_DIR.resolve()
    full_path = (base / filepath).resolve()
    # Prevent path traversal outside the workspaces directory
    if not str(full_path).startswith(str(base)):
        return jsonify({'error': 'Forbidden'}), 403
    if not full_path.exists():
        return jsonify({'error': 'Artifact not found'}), 404
    return send_file(full_path)


@app.route('/api/saved-tests/<filename>/artifacts')
@login_required
def get_test_artifacts(filename):
    """Get list of artifacts for a saved test."""
    workspace_name = request.args.get('workspaceName')
    if workspace_name:
        test_name = filename.replace('/', '_').replace('\\', '_')
        if test_name.endswith('.py'):
            test_name = test_name[:-3]
        return jsonify(_get_artifacts_for_test(workspace_name, test_name))
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({'error': 'Test not found'}), 404
    artifacts = db.get_test_artifacts(ws_id, filename)
    if artifacts is None:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify(artifacts)


def _get_artifacts_for_test(workspace_name: str, test_name: str) -> list:
    """Return artifact info list for a test from the local filesystem."""
    art_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / 'saved_tests' / 'artifacts' / test_name
    if not art_dir.is_dir():
        return []
    video = art_dir / 'recording.webm'
    if not video.exists():
        return []
    video_rel = f'{workspace_name}/saved_tests/artifacts/{test_name}/recording.webm'
    trace_rel = f'{workspace_name}/saved_tests/artifacts/{test_name}/trace.zip'
    has_trace = (art_dir / 'trace.zip').exists()
    status = 'unknown'
    timestamp = ''
    status_file = art_dir / 'status.json'
    if status_file.exists():
        import json as _json
        try:
            sd = _json.loads(status_file.read_text(encoding='utf-8'))
            status = sd.get('status', 'unknown')
            timestamp = sd.get('timestamp', '')
        except Exception:
            pass
    if not timestamp:
        from datetime import datetime as _dt
        timestamp = _dt.utcfromtimestamp(video.stat().st_mtime).isoformat()
    size_mb = round(video.stat().st_size / (1024 * 1024), 2)
    return [{
        'video_url': f'/api/video/{video_rel}',
        'video_path': video_rel,
        'trace_path': trace_rel if has_trace else None,
        'timestamp': timestamp,
        'video_size_mb': size_mb,
        'status': status,
    }]


@app.route('/api/workspaces/<workspace_name>/tests/<test_name>/artifacts', methods=['GET'])
@login_required
def get_workspace_test_artifacts(workspace_name, test_name):
    """Get artifacts for a test in a workspace (filesystem-based)."""
    return jsonify(_get_artifacts_for_test(workspace_name, test_name))


@app.route('/api/workspaces/<workspace_name>/tests/<test_name>/artifacts', methods=['DELETE'])
@login_required
def delete_workspace_test_artifacts(workspace_name, test_name):
    """Delete artifact directory for a test."""
    import shutil
    art_dir = Config.AUTOGEN_WORKSPACES_DIR / workspace_name / 'saved_tests' / 'artifacts' / test_name
    if not art_dir.is_dir():
        return jsonify({'success': True})
    try:
        shutil.rmtree(art_dir)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    """Hard-stop the running test by cancelling its asyncio task."""
    global stop_requested, active_loop
    stop_requested = True

    loop = active_loop
    if loop and not loop.is_closed():
        # Cancel only the active test task — the warm browser loop must stay alive.
        def _cancel_test():
            task = _active_test_task
            if task and not task.done():
                task.cancel()

        loop.call_soon_threadsafe(_cancel_test)
        emit('log', {'type': 'info', 'message': '⏹ Test stopped'})
    else:
        emit('log', {'type': 'info', 'message': '⏹ Stop requested (no active test)'})


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
    filename = data.get('filename')  # may be path e.g. "folder/test.py"
    workspace_name = data.get('workspaceName')

    if not filename:
        emit('log', {'type': 'error', 'message': 'No test specified'})
        return

    try:
        test_data = None
        root = _tree_root(workspace_name, "saved_tests") if workspace_name else None
        if root and root.exists():
            try:
                test_data = local_tree.get_file_content(root, filename, "saved_tests")
            except (FileNotFoundError, ValueError):
                pass
        if not test_data:
            emit('log', {'type': 'error', 'message': 'Test not found'})
            return

        code = test_data.get('code')
        emit('log', {'type': 'info', 'message': f'Running saved test: {test_data.get("name")}'})
        emit('log', {'type': 'info', 'message': '🚀 Executing Playwright code with live browser preview...'})

        socketio.start_background_task(
            run_playwright_code_with_streaming,
            code, filename, workspace_name, True
        )

    except Exception as e:
        emit('log', {'type': 'error', 'message': f'Error running saved test: {str(e)}'})


@socketio.on('run_all_tests')
def handle_run_all_tests(data):
    """Handle running all saved tests in parallel."""
    filenames = data.get('filenames', [])
    workspace_name = data.get('workspaceName')
    socketio.start_background_task(run_all_tests_parallel, filenames, workspace_name)


def run_all_tests_parallel(filenames, workspace_name=None):
    """Execute all tests in parallel and collect results."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    start_time = time.time()
    results = []

    def run_single_test(filename):
        """Execute a single test and return result from local tree."""
        try:
            test_data = None
            if workspace_name:
                root = _tree_root(workspace_name, "saved_tests")
                if root.exists():
                    try:
                        test_data = local_tree.get_file_content(root, filename, "saved_tests")
                    except (FileNotFoundError, ValueError):
                        pass
            if not test_data:
                return {
                    'filename': filename,
                    'name': filename,
                    'status': 'error',
                    'error': 'Test not found'
                }

            name = test_data.get('name', filename)
            code = test_data.get('code', '')

            status, error_msg = run_playwright_code_headless(code, filename, workspace_name)

            try:
                local_tree.write_last_run_meta(
                    _tree_root(workspace_name, "saved_tests"), filename,
                    status=status,
                    last_run_time=datetime.utcnow().isoformat(),
                )
            except Exception:
                pass

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
    """Handle running an AI step test from local tree."""
    global current_ai_step

    filename = data.get('filename')  # may be path e.g. "folder/step.md"
    workspace_name = data.get('workspaceName')

    if not filename:
        emit('log', {'type': 'error', 'message': 'No AI step specified'})
        return

    try:
        step_data = None
        if filename and workspace_name:
            root = _tree_root(workspace_name, "ai_steps")
            if root.exists():
                try:
                    step_data = local_tree.get_file_content(root, filename, "ai_steps")
                except (FileNotFoundError, ValueError):
                    pass

        if not step_data:
            emit('log', {'type': 'error', 'message': 'AI step not found'})
            return

        steps = step_data.get('steps')
        name = step_data.get('name')

        if not steps:
            emit('log', {'type': 'error', 'message': 'No steps found in AI step test'})
            return

        emit('log', {'type': 'info', 'message': f'🤖 Running AI steps: {name}'})

        try:
            root = _tree_root(workspace_name, "ai_steps")
            local_tree.write_last_run_meta(
                root, filename,
                last_run_time=datetime.utcnow().isoformat(),
            )
        except Exception:
            pass

        # Track current AI step for code generation prompt
        current_ai_step = {'filename': filename, 'name': name, 'workspace_name': workspace_name}

        socketio.start_background_task(run_test_sync, steps, filename, workspace_name)

    except Exception as e:
        emit('log', {'type': 'error', 'message': f'Error running AI step: {str(e)}'})


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message from AI Chat tab."""
    message = data.get('message', '')
    existing_code = data.get('existing_code')
    image = data.get('image')
    workspace_name = data.get('workspaceName')
    user_id = data.get('user_id')

    if not message and not image:
        emit('chat_error', {'message': 'No message or image provided'})
        return

    if workspace_name and user_id:
        # Use workspace agent with full tool access
        socketio.start_background_task(
            _run_workspace_agent, message, existing_code, image, workspace_name, user_id
        )
    else:
        # Fallback: no workspace context, use simple code agent
        file_type = data.get('file_type', 'unknown')
        socketio.start_background_task(handle_code_chat, message, existing_code, image, file_type)


def _run_workspace_agent(message, existing_code, image, workspace_name, user_id):
    """Background task: run workspace agent with tool-calling loop."""
    try:
        workspace_agent.run(
            message=message,
            workspace_id=workspace_name,
            user_id=user_id,
            emit_fn=socketio.emit,
            image=image,
            existing_code=existing_code,
        )
    except Exception as e:
        socketio.emit('chat_error', {'message': str(e)})


def handle_code_chat(message, existing_code, image=None, file_type='unknown'):
    """Background task to handle code generation chat (fallback, no workspace)."""
    try:
        result = code_agent.generate_response(message, existing_code, image, file_type)

        socketio.emit('chat_response', {
            'role': 'ai',
            'message': result['message'],
            'timestamp': datetime.now().isoformat()
        })

        if result.get('code'):
            socketio.emit('code_suggestion', {
                'code': result['code'],
                'explanation': result.get('explanation', ''),
                'action': 'suggest',
                'content_type': 'code'
            })
        elif result.get('content'):
            socketio.emit('code_suggestion', {
                'code': result['content'],
                'explanation': result.get('explanation', ''),
                'action': 'suggest',
                'content_type': 'steps'
            })

    except Exception as e:
        socketio.emit('chat_error', {'message': str(e)})


@socketio.on('clear_chat')
def handle_clear_chat(data=None):
    """Handle chat history clear request."""
    workspace_name = (data or {}).get('workspaceName')
    if workspace_name:
        workspace_agent.clear_history(workspace_name)
    else:
        code_agent.clear_history()
    emit('log', {'type': 'info', 'message': 'Chat history cleared'})


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    from auth import _LOCAL_MODE, _LOCAL_TOKEN, _LOCAL_USER

    # In local mode, accept any connection
    if _LOCAL_MODE:
        emit('log', {'type': 'info', 'message': 'Connected to AutoGen Web Tester'})
        return

    # Validate JWT from socket auth params
    token = request.args.get('token')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

    if not token:
        emit('log', {'type': 'error', 'message': 'Authentication required'})
        return False  # Reject connection

    # Validate token and get user
    try:
        from supabase_client import get_supabase_client
        sb = get_supabase_client()
        auth_response = sb.auth.get_user(token)
        supabase_user = auth_response.user
        if not supabase_user:
            emit('log', {'type': 'error', 'message': 'Authentication required'})
            return False

        user = db.get_user_by_id(supabase_user.id)
        if not user:
            emit('log', {'type': 'error', 'message': 'Authentication required'})
            return False

        emit('log', {'type': 'info', 'message': f'Connected to AutoGen Web Tester (User: {user["username"]})'})
    except Exception as e:
        print(f"Socket auth error: {e}")
        emit('log', {'type': 'error', 'message': 'Authentication required'})
        return False




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
