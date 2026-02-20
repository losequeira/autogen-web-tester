"""
Workspace Agent for AutoGen Web Tester.

An OpenAI function-calling agent with tools to interact with the workspace:
list, read, search, create, and update tests and AI steps.
"""

import json
import traceback
from datetime import datetime
from typing import Any, Callable

from openai import OpenAI

import config
import db


class WorkspaceAgent:
    """
    Agent with workspace tools for managing tests and AI step files.
    Uses OpenAI function calling in an agentic loop until a final answer is produced.
    """

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "get_workspace_context",
                "description": (
                    "Return ALL tests and AI steps in the workspace with their full content. "
                    "Use this for analysis, metrics, 'what does this test do', or any question "
                    "that requires understanding the content of workspace files."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_tests",
                "description": "List all Playwright tests in the workspace. Returns names, filenames, and last-run status.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_ai_steps",
                "description": "List all AI step files in the workspace. Returns names, filenames, and last-run status.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_test",
                "description": "Read the full Python code of a specific Playwright test file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The filename of the test (e.g. 'my_test.py')",
                        },
                    },
                    "required": ["filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_ai_step",
                "description": "Read the full natural-language steps of a specific AI step file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The filename of the AI step file (e.g. 'my_steps.json')",
                        },
                    },
                    "required": ["filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search for text across all tests and AI step files in the workspace. Returns matching files with context snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for (case-insensitive)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_test",
                "description": "Create a new Playwright test file in the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Human-readable display name for the test",
                        },
                        "code": {
                            "type": "string",
                            "description": "Complete Python Playwright code using async/await style",
                        },
                    },
                    "required": ["name", "code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_ai_step",
                "description": "Create a new AI step file in the workspace. AI steps are natural-language instructions that guide the AI browser agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Human-readable display name for the AI step file",
                        },
                        "steps": {
                            "type": "string",
                            "description": "Numbered natural-language steps for the AI browser agent to follow",
                        },
                    },
                    "required": ["name", "steps"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_test",
                "description": "Update the code of an existing Playwright test file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename of the test to update",
                        },
                        "code": {
                            "type": "string",
                            "description": "New complete Python Playwright code",
                        },
                    },
                    "required": ["filename", "code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_ai_step",
                "description": "Update the steps of an existing AI step file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename of the AI step file to update",
                        },
                        "steps": {
                            "type": "string",
                            "description": "New natural-language steps content",
                        },
                    },
                    "required": ["filename", "steps"],
                },
            },
        },
    ]

    BASE_SYSTEM_PROMPT = """You are a workspace assistant for a web testing automation tool. \
You help users create, read, search, analyse, and edit their Playwright tests and AI step files.

━━ FILE TYPE DISTINCTION (CRITICAL) ━━
• TESTS — Playwright Python scripts (.py or .json filenames from list_tests). \
Read with read_test. Edit with update_test.
• AI STEPS — Natural-language numbered steps (.json filenames from list_ai_steps). \
Read with read_ai_step. Edit with update_ai_step.
NEVER call read_ai_step for a filename that came from list_tests. \
NEVER call read_test for a filename that came from list_ai_steps.

━━ TOOLS ━━
- get_workspace_context — returns ALL tests and AI steps with their full content. \
Call this first for any analysis, metrics, or "what does X test" question.
- list_tests / list_ai_steps — lightweight listing (names + status, no content)
- read_test(filename) — full Python code for ONE test (filename from list_tests)
- read_ai_step(filename) — full steps for ONE AI step file (filename from list_ai_steps)
- search_files(query) — keyword search across all file contents
- create_test / create_ai_step — create new files
- update_test / update_ai_step — propose edits (shown as diff for user review)

━━ SEMANTIC QUERY HANDLING ━━
Before answering, extract the intent from the user's message:
- "show me / tell me / what does / details about / metrics / analyse" → call get_workspace_context
- "create / generate / write" → call create_test or create_ai_step
- "fix / update / change / modify" → read the file first, then call the update tool
- "find / search / which test" → call search_files(query)
- Vague pronoun references ("it", "that test", "them") → infer from conversation history

━━ CRITICAL RULES ━━
1. Fix/update: always read_test or read_ai_step FIRST, then update. NEVER output code as text only.
2. Create: call the tool directly — don't describe what you would write.
3. Update diff: tell user to review the proposed diff shown in the UI and accept or reject it.
4. Error tracebacks: "web_ui.py", "<string>" are system internals — the actual test is in the workspace.
5. Never guess filenames — always use filenames returned by list_tests or list_ai_steps tools.
6. Be concise. After tool calls, give a short plain-text summary of what was done.

━━ CODE TEMPLATE ━━
```python
from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        # ... actions ...
        await browser.close()

asyncio.run(run())
```

━━ AI STEPS TEMPLATE ━━
```
1. Navigate to https://example.com
2. Click the "Login" button
3. Fill in the email field with "user@example.com"
4. Click "Submit"
5. Verify the dashboard heading is visible
```"""

    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = model
        # Per-workspace conversation histories: {workspace_id: [messages]}
        self._histories: dict[int, list[dict]] = {}

    def _build_system_prompt(self, workspace_id: int) -> str:
        """Build the system prompt with a live workspace snapshot injected."""
        tests = db.get_tests(workspace_id)
        ai_steps_list = db.get_ai_steps(workspace_id)

        snapshot_lines = ["\n\n━━ CURRENT WORKSPACE SNAPSHOT ━━"]
        if tests:
            snapshot_lines.append(f"Tests ({len(tests)}):")
            for t in tests:
                status = t.get("last_run_status") or "never run"
                snapshot_lines.append(f"  • {t['name']}  [filename: {t['filename']}]  status: {status}")
        else:
            snapshot_lines.append("Tests: none")

        if ai_steps_list:
            snapshot_lines.append(f"AI Steps ({len(ai_steps_list)}):")
            for s in ai_steps_list:
                snapshot_lines.append(f"  • {s['name']}  [filename: {s['filename']}]")
        else:
            snapshot_lines.append("AI Steps: none")

        snapshot_lines.append(
            "\nUse these exact filenames when calling read_test / read_ai_step / update_test / update_ai_step."
        )

        return self.BASE_SYSTEM_PROMPT + "\n".join(snapshot_lines)

    def _history(self, workspace_id: int) -> list[dict]:
        if workspace_id not in self._histories:
            self._histories[workspace_id] = []
        return self._histories[workspace_id]

    def clear_history(self, workspace_id: int) -> None:
        self._histories.pop(workspace_id, None)

    def _execute_tool(
        self,
        tool_name: str,
        tool_args: dict,
        workspace_id: int,
        user_id: str,
        emit_fn: Callable,
    ) -> str:
        """Execute a single tool call and return the result as a string."""
        try:
            if tool_name == "get_workspace_context":
                tests = db.get_tests(workspace_id)
                ai_steps_list = db.get_ai_steps(workspace_id)
                lines = []

                lines.append(f"=== WORKSPACE CONTEXT ({len(tests)} test(s), {len(ai_steps_list)} AI step file(s)) ===\n")

                if tests:
                    lines.append("── TESTS (Playwright Python code) ──")
                    for t in tests:
                        status = t.get("last_run_status") or "never run"
                        lines.append(f"\n[TEST] {t['name']} | file: {t['filename']} | status: {status}")
                        full = db.get_test(workspace_id, t["filename"])
                        code = full.get("code", "") if full else ""
                        lines.append(f"```python\n{code}\n```")
                else:
                    lines.append("No tests found.")

                if ai_steps_list:
                    lines.append("\n── AI STEPS (natural language) ──")
                    for s in ai_steps_list:
                        lines.append(f"\n[AI STEPS] {s['name']} | file: {s['filename']}")
                        full = db.get_ai_step(workspace_id, s["filename"])
                        steps = full.get("steps", "") if full else ""
                        lines.append(steps)
                else:
                    lines.append("\nNo AI step files found.")

                return "\n".join(lines)

            elif tool_name == "list_tests":
                tests = db.get_tests(workspace_id)
                if not tests:
                    return "No tests found in this workspace."
                lines = [f"Found {len(tests)} test(s):"]
                for t in tests:
                    status = t.get("last_run_status") or "never run"
                    lines.append(f"  - {t['name']} ({t['filename']}) — {status}")
                return "\n".join(lines)

            elif tool_name == "list_ai_steps":
                steps = db.get_ai_steps(workspace_id)
                if not steps:
                    return "No AI step files found in this workspace."
                lines = [f"Found {len(steps)} AI step file(s):"]
                for s in steps:
                    status = s.get("last_run_status") or "never run"
                    lines.append(f"  - {s['name']} ({s['filename']}) — {status}")
                return "\n".join(lines)

            elif tool_name == "read_test":
                filename = tool_args["filename"]
                test = db.get_test(workspace_id, filename)
                if not test:
                    return f"Test '{filename}' not found."
                return (
                    f"Test: {test['name']}\n"
                    f"Filename: {test['filename']}\n"
                    f"Last run: {test.get('last_run_status') or 'never'}\n\n"
                    f"```python\n{test['code']}\n```"
                )

            elif tool_name == "read_ai_step":
                filename = tool_args["filename"]
                step = db.get_ai_step(workspace_id, filename)
                if not step:
                    return f"AI step file '{filename}' not found."
                return (
                    f"AI Steps: {step['name']}\n"
                    f"Filename: {step['filename']}\n\n"
                    f"{step['steps']}"
                )

            elif tool_name == "search_files":
                query = tool_args["query"].lower()
                tests = db.get_tests(workspace_id)
                ai_steps_list = db.get_ai_steps(workspace_id)

                results = []

                for t in tests:
                    code = (t.get("code") or "").lower()
                    name = (t.get("name") or "").lower()
                    if query in code or query in name:
                        idx = code.find(query)
                        snippet = ""
                        if idx >= 0:
                            raw = t.get("code", "")
                            start = max(0, idx - 60)
                            end = min(len(raw), idx + len(query) + 60)
                            snippet = raw[start:end].strip().replace("\n", " ")
                        results.append(
                            f"[TEST] {t['name']} ({t['filename']})"
                            + (f"\n  …{snippet}…" if snippet else "")
                        )

                for s in ai_steps_list:
                    name = (s.get("name") or "").lower()
                    if query in name:
                        results.append(f"[AI STEPS] {s['name']} ({s['filename']})")
                    else:
                        # Load full steps only when name didn't match
                        full = db.get_ai_step(workspace_id, s["filename"])
                        if full:
                            content = (full.get("steps") or "").lower()
                            if query in content:
                                idx = content.find(query)
                                raw = full.get("steps", "")
                                start = max(0, idx - 60)
                                end = min(len(raw), idx + len(query) + 60)
                                snippet = raw[start:end].strip().replace("\n", " ")
                                results.append(
                                    f"[AI STEPS] {s['name']} ({s['filename']})"
                                    + f"\n  …{snippet}…"
                                )

                if not results:
                    return f"No files found matching '{query}'."
                return f"Found {len(results)} match(es) for '{query}':\n" + "\n".join(results)

            elif tool_name == "create_test":
                name = tool_args["name"]
                code = tool_args["code"]
                result = db.create_test(workspace_id, name, code, source="ai", user_id=user_id)
                filename = result.get("filename", "")
                emit_fn("file_created", {"type": "test", "filename": filename, "name": name})
                return f"Test '{name}' created as '{filename}'."

            elif tool_name == "create_ai_step":
                name = tool_args["name"]
                steps = tool_args["steps"]
                result = db.create_ai_step(workspace_id, name, steps, user_id=user_id)
                filename = result.get("filename", "")
                emit_fn("file_created", {"type": "ai_step", "filename": filename, "name": name})
                return f"AI step file '{name}' created as '{filename}'."

            elif tool_name == "update_test":
                filename = tool_args["filename"]
                code = tool_args["code"]
                current = db.get_test(workspace_id, filename)
                if not current:
                    return f"Test '{filename}' not found."
                emit_fn("propose_change", {
                    "filename": filename,
                    "type": "test",
                    "old_content": current.get("code", ""),
                    "new_content": code,
                    "workspace_id": workspace_id,
                })
                return f"Change proposed for '{filename}'. The diff is now shown to the user for review."

            elif tool_name == "update_ai_step":
                filename = tool_args["filename"]
                steps = tool_args["steps"]
                current = db.get_ai_step(workspace_id, filename)
                if not current:
                    return f"AI step file '{filename}' not found."
                emit_fn("propose_change", {
                    "filename": filename,
                    "type": "ai_step",
                    "old_content": current.get("steps", ""),
                    "new_content": steps,
                    "workspace_id": workspace_id,
                })
                return f"Change proposed for '{filename}'. The diff is now shown to the user for review."

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            traceback.print_exc()
            return f"Tool '{tool_name}' failed: {str(e)}"

    def run(
        self,
        message: str,
        workspace_id: int,
        user_id: str,
        emit_fn: Callable,
        image: str | None = None,
        existing_code: str | None = None,
    ) -> None:
        """
        Run the agentic loop for a single user message.
        Calls emit_fn with socket events as the agent works.
        """
        history = self._history(workspace_id)

        # Build user message content
        if image:
            content: Any = [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": image}},
            ]
        elif existing_code:
            content = f"{message}\n\nCurrent file content:\n```\n{existing_code}\n```"
        else:
            content = message

        history.append({"role": "user", "content": content})

        # Build dynamic system prompt with live workspace snapshot
        system_prompt = self._build_system_prompt(workspace_id)

        # Agentic tool-call loop
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + history,
                tools=self.TOOLS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message
            history.append(msg.model_dump(exclude_unset=True))

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)

                    # Notify the frontend about the tool call
                    emit_fn("agent_tool_call", {
                        "tool": tool_name,
                        "args": tool_args,
                        "timestamp": datetime.now().isoformat(),
                    })

                    result = self._execute_tool(
                        tool_name, tool_args, workspace_id, user_id, emit_fn
                    )

                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # Final text response
                emit_fn("chat_response", {
                    "role": "ai",
                    "message": msg.content or "",
                    "timestamp": datetime.now().isoformat(),
                })
                break
