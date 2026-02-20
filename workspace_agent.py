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

    SYSTEM_PROMPT = """You are a workspace assistant for a web testing automation tool. \
You help users create, read, search, and edit their Playwright tests and AI step files.

Available tools:
- list_tests / list_ai_steps — browse workspace files
- read_test / read_ai_step — read file contents
- search_files — find files by content
- create_test — create a new Playwright Python test
- create_ai_step — create a new AI steps file (natural language)
- update_test / update_ai_step — edit existing files

CRITICAL RULES — follow these exactly:
1. When asked to fix, modify, or update an existing test/AI step: call read_test or read_ai_step first to see the current content, then call update_test or update_ai_step with the complete updated file. NEVER just show the code in text — always write it via the tool.
2. When asked to create a new test or AI step: call create_test or create_ai_step directly. Do not describe what you would write — just write it.
3. Only respond with plain text after all tool calls are done. Keep the final reply short: confirm what was done and highlight key changes.
4. When update_test or update_ai_step is called, the change is NOT saved immediately — a diff is shown to the user for review. After the tool call, tell the user to review the proposed diff and accept or reject it.
5. When the user pastes an error/traceback: the file paths in the traceback (e.g. "web_ui.py", "<string>") are SYSTEM internals, NOT workspace test files. Use list_tests to find the actual test that caused the error, then fix it.

When generating Playwright test code always use this structure:
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

When creating AI steps use numbered natural-language instructions, for example:
```
1. Navigate to https://example.com
2. Click the "Login" button
3. Fill in the email field with "user@example.com"
4. Click "Submit"
5. Verify the dashboard heading is visible
```

Be concise and helpful. Use tools proactively when needed to fulfil requests."""

    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = model
        # Per-workspace conversation histories: {workspace_id: [messages]}
        self._histories: dict[int, list[dict]] = {}

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
            if tool_name == "list_tests":
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
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
            ]
        elif existing_code:
            content = f"{message}\n\nCurrent file content:\n```\n{existing_code}\n```"
        else:
            content = message

        history.append({"role": "user", "content": content})

        # Agentic tool-call loop
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": self.SYSTEM_PROMPT}] + history,
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
