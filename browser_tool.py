"""BrowserTool: Playwright wrapper for AutoGen agents."""

from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright, BrowserContext


class BrowserTool:
    """
    Async browser automation tool using Playwright.

    Provides simple methods for web interaction that can be exposed
    as AutoGen tools for LLM-driven browser automation.
    """

    def __init__(self, headless: bool = False, timeout: int = 30000,
                 record_video_dir: str = None, record_har: bool = False):
        """
        Initialize BrowserTool.

        Args:
            headless: Run browser in headless mode (no UI)
            timeout: Default timeout for operations in milliseconds
            record_video_dir: Directory to save video recordings (None = no recording)
            record_har: Whether to record HTTP Archive (HAR) file
        """
        self.headless = headless
        self.timeout = timeout
        self.record_video_dir = record_video_dir
        self.record_har = record_har
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """Initialize Playwright and browser on context entry."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

        # Create context with recording options if specified
        context_options = {}
        if self.record_video_dir:
            context_options['record_video_dir'] = self.record_video_dir
            context_options['record_video_size'] = {"width": 1280, "height": 720}

        if self.record_har and self.record_video_dir:
            context_options['record_har_path'] = f"{self.record_video_dir}/network.har"

        # Create context with or without recording
        if context_options:
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
        else:
            self.page = await self.browser.new_page()

        self.page.set_default_timeout(self.timeout)
        return self

    async def __aexit__(self, *args):
        """Cleanup resources on context exit."""
        # Close page first
        if self.page:
            await self.page.close()

        # Close context to save video recording
        if self.context:
            await self.context.close()

        # Close browser and playwright
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str) -> str:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to

        Returns:
            Confirmation message with final URL
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            # Use 'domcontentloaded' which is more reliable than 'networkidle' for modern SPAs
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Wait a bit for dynamic content to load
            await self.page.wait_for_timeout(2000)
            final_url = self.page.url
            title = await self.page.title()
            return f"Navigated to {final_url} - Page title: '{title}'"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"

    async def fill_form(self, selector: str, value: str) -> str:
        """
        Fill a form field with a value.

        Args:
            selector: CSS selector for the input field
            value: Value to enter

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            await self.page.wait_for_selector(selector, state="visible")
            await self.page.fill(selector, value)
            return f"Successfully filled '{selector}' with the provided value"
        except Exception as e:
            return f"Error filling form field '{selector}': {str(e)}"

    async def click(self, selector: str) -> str:
        """
        Click an element.

        Args:
            selector: CSS selector for the element to click

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            await self.page.wait_for_selector(selector, state="visible")
            await self.page.click(selector)
            # Wait a moment for any navigation or dynamic content
            await self.page.wait_for_timeout(1000)
            return f"Successfully clicked '{selector}'"
        except Exception as e:
            return f"Error clicking element '{selector}': {str(e)}"

    async def click_text(self, text: str, role: str = None) -> str:
        """
        Click an element by its visible text content.

        Args:
            text: The visible text of the element to click (e.g., "Sign Up", "Submit")
            role: Optional role to filter by (e.g., "button", "link")

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            # Try multiple strategies to find and click the element
            clicked = False
            error_messages = []

            # Strategy 1: If role specified, try role-specific selector
            if role == "button":
                try:
                    await self.page.click(f"button:has-text('{text}')", timeout=5000)
                    clicked = True
                except Exception as e:
                    error_messages.append(f"button selector failed: {str(e)}")

            # Strategy 2: Try Playwright's getByRole (most reliable for buttons)
            if not clicked:
                try:
                    await self.page.get_by_role("button", name=text).click(timeout=5000)
                    clicked = True
                except Exception as e:
                    error_messages.append(f"getByRole failed: {str(e)}")

            # Strategy 3: Try generic text selector (last resort)
            if not clicked:
                try:
                    await self.page.click(f"text={text}", timeout=5000)
                    clicked = True
                except Exception as e:
                    error_messages.append(f"text selector failed: {str(e)}")

            if not clicked:
                return f"Error: Could not click '{text}'. Attempts: {'; '.join(error_messages)}"

            # Wait longer for form submissions (buttons) to process and navigate
            if role == "button":
                await self.page.wait_for_timeout(6000)  # 6 seconds for form processing & navigation
            else:
                await self.page.wait_for_timeout(2000)

            return f"Successfully clicked element with text '{text}'"

        except Exception as e:
            return f"Error clicking element with text '{text}': {str(e)}"

    async def get_text(self, selector: str) -> str:
        """
        Get text content from an element.

        Args:
            selector: CSS selector for the element

        Returns:
            Text content or error message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            await self.page.wait_for_selector(selector, state="visible")
            text = await self.page.text_content(selector)
            return f"Text from '{selector}': {text}"
        except Exception as e:
            return f"Error getting text from '{selector}': {str(e)}"

    async def screenshot(self, path: str) -> str:
        """
        Take a screenshot of the current page.

        Args:
            path: File path to save screenshot

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            await self.page.screenshot(path=path, full_page=True)
            return f"Screenshot saved to {path}"
        except Exception as e:
            return f"Error taking screenshot: {str(e)}"

    async def get_page_content(self) -> str:
        """
        Get the full text content of the current page.

        Returns:
            Page content or error message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            content = await self.page.content()
            # Extract visible text (simplified)
            text = await self.page.evaluate("() => document.body.innerText")
            current_url = self.page.url
            return f"Current URL: {current_url}\n\nPage content (first 1000 chars):\n{text[:1000]}"
        except Exception as e:
            return f"Error getting page content: {str(e)}"

    async def get_current_url(self) -> str:
        """
        Get the current page URL.

        Returns:
            Current URL
        """
        if not self.page:
            return "Error: Browser not initialized"

        return f"Current URL: {self.page.url}"

    async def get_html(self) -> str:
        """
        Get the full HTML content of the current page.

        Returns:
            HTML content (truncated to 5000 chars for readability)
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            html = await self.page.content()
            # Truncate for readability
            if len(html) > 5000:
                return f"HTML (first 5000 chars):\n{html[:5000]}\n\n... (truncated)"
            return f"HTML:\n{html}"
        except Exception as e:
            return f"Error getting HTML: {str(e)}"

    async def find_inputs(self) -> str:
        """
        Find all input fields on the page and return their attributes.

        Returns:
            List of input fields with their selectors and attributes
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            inputs = await self.page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input, textarea, select, button[type="submit"]');
                    return Array.from(inputs).map((el, index) => ({
                        index: index,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || 'text',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        className: el.className || '',
                        value: el.value || '',
                        visible: el.offsetParent !== null
                    }));
                }
            """)

            result = "Found input fields:\n\n"
            for inp in inputs:
                result += f"[{inp['index']}] <{inp['tag']}>\n"
                result += f"    Type: {inp['type']}\n"
                if inp['name']:
                    result += f"    Name: {inp['name']} → selector: input[name='{inp['name']}']\n"
                if inp['id']:
                    result += f"    ID: {inp['id']} → selector: #{inp['id']}\n"
                if inp['placeholder']:
                    result += f"    Placeholder: {inp['placeholder']}\n"
                if inp['className']:
                    result += f"    Class: {inp['className']}\n"
                result += f"    Visible: {inp['visible']}\n\n"

            return result
        except Exception as e:
            return f"Error finding inputs: {str(e)}"
