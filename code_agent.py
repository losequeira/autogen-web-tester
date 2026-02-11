"""
Code Generation Agent for AutoGen Web Tester
Provides conversational AI-powered Playwright code generation.
"""

from openai import OpenAI
from typing import Optional, List, Dict
import re


class CodeGenerationAgent:
    """
    Conversational AI agent for generating and modifying Playwright code.
    Uses OpenAI API to generate Python Playwright code based on user requests.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """
        Initialize the Code Generation Agent.

        Args:
            api_key: OpenAI API key
            model: OpenAI model name (default: gpt-4o)
        """
        self.api_key = api_key
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

        # System prompt for code generation
        self.system_prompt = """You are a Playwright code generation assistant. Generate and modify Python Playwright automation code.

RULES:
1. Output ONLY Python Playwright code using async/await
2. Always use this structure:
   from playwright.async_api import async_playwright
   import asyncio

   async def run():
       async with async_playwright() as p:
           browser = await p.chromium.launch(headless=False)
           page = await browser.new_page()
           # ... code here ...
           await browser.close()

   asyncio.run(run())

3. Code style: 4-space indentation, double quotes, descriptive names
4. Common patterns:
   - Navigate: await page.goto("url")
   - Click: await page.get_by_text("text").click()
   - Fill: await page.fill("selector", "value")
   - Wait: await page.wait_for_selector("selector")

5. When modifying code: preserve structure, only change requested parts

6. Response format:
   - Brief explanation (1-2 sentences)
   - Complete code in ```python blocks
   - Summary of what the code does

7. Be concise and helpful. Focus on generating working, clean code.
"""

        # System prompt for AI Steps (use case generation)
        self.steps_system_prompt = """You are a test case design assistant. Help users create detailed, step-by-step test cases for web applications.

RULES:
1. Generate clear, numbered step-by-step test scenarios
2. Each step should be actionable and specific
3. Include verification/validation steps where appropriate
4. Format as plain text or markdown

5. Test case structure:
   - Clear test case name/description
   - Numbered steps (1., 2., 3., etc.)
   - Each step describes ONE action or validation
   - Include expected results where relevant

6. Common test patterns:
   - User flows (signup, login, checkout, etc.)
   - Form validation scenarios
   - Navigation and UI interactions
   - Data entry and submission
   - Error handling and edge cases

7. Example format:
   Test Case: User Signup Flow

   1. Navigate to the signup page
   2. Fill in the email field with "test@example.com"
   3. Fill in the password field with a valid password
   4. Click the "Sign Up" button
   5. Verify that the user is redirected to the dashboard
   6. Verify that a welcome message is displayed

8. Be specific about selectors, text, and actions
9. Include validation steps to ensure the test is working correctly
10. Consider edge cases and error scenarios when relevant
"""

    def _get_system_prompt(self, file_type: str) -> str:
        """
        Get the appropriate system prompt based on file type.

        Args:
            file_type: Type of file being edited ('test', 'ai-step', or 'unknown')

        Returns:
            System prompt string
        """
        if file_type == 'ai-step':
            return self.steps_system_prompt
        else:
            # For 'test', 'unknown', or any other type, use the code generation prompt
            return self.system_prompt

    def generate_response(self, user_message: str, existing_code: Optional[str] = None, image_data: Optional[str] = None, file_type: str = 'unknown') -> Dict:
        """
        Generate AI response and code based on user message.

        Args:
            user_message: User's request or question
            existing_code: Optional existing code to modify
            image_data: Optional base64 encoded image data
            file_type: Type of file being edited ('test', 'ai-step', or 'unknown')

        Returns:
            Dictionary with:
                - message: Full AI response
                - code: Extracted Python code (if any)
                - explanation: Brief explanation of what was done
        """
        try:
            # Build context with existing content if provided
            context = ""
            if existing_code:
                if file_type == 'ai-step':
                    # For AI steps, treat existing content as test steps
                    context = f"Current test steps:\n{existing_code}\n\n"
                else:
                    # For test files, treat existing content as code
                    context = f"Current code:\n```python\n{existing_code}\n```\n\n"

            full_message = context + user_message

            # Prepare message content (text or text + image)
            if image_data:
                # For vision requests, send image along with text
                user_content = [
                    {"type": "text", "text": full_message},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data
                        }
                    }
                ]
            else:
                user_content = full_message

            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_content
            })

            # Get the appropriate system prompt based on file type
            system_prompt = self._get_system_prompt(file_type)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + self.conversation_history,
                temperature=0.7,
                max_tokens=2000
            )

            ai_message = response.choices[0].message.content

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": ai_message
            })

            # Extract content based on file type
            code = None
            content = None
            explanation = None

            if file_type == 'ai-step':
                # For AI steps, extract the full response as content (steps)
                content = self._extract_steps_from_response(ai_message)
                explanation = self._extract_explanation_from_response(ai_message)
            else:
                # For test files, extract code blocks
                code = self._extract_code_from_response(ai_message)
                explanation = self._extract_explanation_from_response(ai_message)

            return {
                "message": ai_message,
                "code": code,
                "content": content,
                "explanation": explanation,
                "file_type": file_type
            }

        except Exception as e:
            raise Exception(f"Error generating code: {str(e)}")

    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """
        Extract Python code from markdown code blocks in the response.

        Args:
            response: AI response text

        Returns:
            Extracted code or None if no code block found
        """
        # Look for ```python code blocks
        pattern = r'```python\n(.*?)\n```'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Return the first code block (usually the main one)
            return matches[0].strip()

        # Try generic code blocks (```)
        pattern = r'```\n(.*?)\n```'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Check if it looks like Python code
            code = matches[0].strip()
            if 'async def' in code or 'await' in code or 'playwright' in code:
                return code

        return None

    def _extract_steps_from_response(self, response: str) -> Optional[str]:
        """
        Extract test steps content from the response.
        For AI Steps files, we want the full response content (which should be steps).

        Args:
            response: AI response text

        Returns:
            Extracted steps content or the full response if it looks like steps
        """
        # Clean up the response
        content = response.strip()

        # If the response contains numbered steps, return it as-is
        # Look for patterns like "1.", "2.", etc.
        if re.search(r'^\d+\.', content, re.MULTILINE):
            return content

        # If it contains "Test Case:" or similar headers, return it
        if re.search(r'Test Case:|Steps:|Scenario:', content, re.IGNORECASE):
            return content

        # Otherwise, return the full response
        return content

    def _extract_explanation_from_response(self, response: str) -> str:
        """
        Extract explanation text (non-code) from the response.

        Args:
            response: AI response text

        Returns:
            Explanation text
        """
        # Remove code blocks
        explanation = re.sub(r'```.*?```', '', response, flags=re.DOTALL)

        # Clean up whitespace
        explanation = explanation.strip()

        # Take first 2-3 sentences as explanation
        sentences = explanation.split('.')
        if len(sentences) > 3:
            explanation = '. '.join(sentences[:3]) + '.'

        return explanation.strip()

    def clear_history(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []
