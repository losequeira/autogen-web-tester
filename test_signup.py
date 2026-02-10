"""
AutoGen Web Tester - Signup Flow Example

Demonstrates using AutoGen v0.4 agents with Playwright browser automation
to complete a website signup flow using natural language instructions.
"""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

from browser_tool import BrowserTool
import config


async def main():
    """Run the signup automation test."""

    print("🚀 AutoGen Web Tester - Starting signup automation\n")

    # Initialize browser tool with context manager for automatic cleanup
    async with BrowserTool(headless=config.HEADLESS_MODE, timeout=config.TIMEOUT) as browser:

        # Wrap browser methods as AutoGen FunctionTools
        navigate_tool = FunctionTool(
            browser.navigate,
            description="Navigate to a URL. Provide the full URL as a string."
        )

        fill_tool = FunctionTool(
            browser.fill_form,
            description="Fill a form field. Provide CSS selector and value. Example: selector='input[name=\"email\"]', value='test@example.com'"
        )

        click_tool = FunctionTool(
            browser.click,
            description="Click an element. Provide CSS selector. Example: selector='button[type=\"submit\"]'"
        )

        click_text_tool = FunctionTool(
            browser.click_text,
            description="Click element by visible text. Parameters: text (required), role (optional: 'button' to ensure clicking button not link). Example: text='Sign Up', role='button'"
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
            description="Find all input fields on page with their exact selectors. USE THIS before filling forms!"
        )

        get_html_tool = FunctionTool(
            browser.get_html,
            description="Get the raw HTML of the page."
        )

        # Create OpenAI model client
        model_client = OpenAIChatCompletionClient(
            model=config.MODEL_NAME,
            api_key=config.OPENAI_API_KEY
        )

        # Create agent with browser tools
        system_message = """You are a web testing automation agent. Your job is to interact with websites using the provided browser tools.

TOOL USAGE RULES (CRITICAL - ALWAYS FOLLOW):

1. **Clicking Buttons/Links:**
   - For ANY button or link with visible text (e.g., "Sign Up", "Submit", "Login"), ALWAYS use click_text with the exact text
   - When clicking submit buttons, use role='button' parameter to avoid clicking header/navigation links with same text
   - Example: click_text(text='Sign Up', role='button') for submit buttons
   - Only use click(selector) as last resort if click_text fails

2. **Filling Forms:**
   - BEFORE filling ANY form, you MUST use find_inputs to discover all input fields and their exact selectors
   - find_inputs returns name, id, type, placeholder for each field - use these exact selectors
   - Example: If find_inputs shows "name: email → selector: input[name='email']", use input[name='email']
   - NEVER guess selectors - always use find_inputs first

3. **Navigation:**
   - Use navigate(url) to go to pages
   - After navigation, wait for page to load (automatic)

4. **Verification:**
   - Use get_page_content to check current page text and URL
   - Use get_current_url to verify you're on the right page

Available tools:
- navigate, click_text, click, fill_form, find_inputs, get_page_content, get_current_url, get_text, screenshot, get_html

These rules apply to ALL tasks. Users will give you natural language instructions - translate them using these rules."""

        agent = AssistantAgent(
            name="web_tester",
            model_client=model_client,
            tools=[
                navigate_tool,
                click_text_tool,  # Best for clicking buttons with visible text
                click_tool,
                fill_tool,
                find_inputs_tool,  # Critical for discovering form selectors
                get_content_tool,
                get_url_tool,
                get_text_tool,
                screenshot_tool,
                get_html_tool
            ],
            system_message=system_message
        )

        # Define the signup task - NATURAL LANGUAGE ONLY (no technical instructions)
        task = f"""Complete the signup process on {config.WEBSITE_URL}:

1. Go to the website
2. Click the "Sign Up" button at the header to open the form
3. Fill out the signup form with:
   - Full Name: Sarah Agent
   - Email: loesequeira05+(random 4 characters)@gmail.com
4. Submit the form by clicking the "Sign Up" button at the bottom
5. Verify the success page contains ALL of these elements:
   - Heading: "Just a couple of questions to save you time"
   - Subheading: "Bedrooms help us find your perfect fit. Choose at least one to continue"
   - 4 bedroom option cards: "Studio", "1 Bed", "2 Beds", "3+ Beds"
"""

        print(f"📋 Task: {task}\n")
        print("="*80)
        print()

        # Run the agent - use a team for multi-turn conversations
        try:
            from autogen_agentchat.teams import RoundRobinGroupChat
            from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
            from autogen_agentchat.ui import Console

            # Create termination condition - stop after 20 messages or when task is complete
            termination = MaxMessageTermination(max_messages=20)

            # Create a team with the agent
            team = RoundRobinGroupChat(
                [agent],
                termination_condition=termination
            )

            # Run the team
            result = await Console(team.run_stream(task=task))

            print("\n" + "="*80)
            print("✅ Agent execution completed!")
            print("="*80)
            print(f"\nFinal result:\n{result}")

        except Exception as e:
            print(f"\n❌ Error during execution: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
