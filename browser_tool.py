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
        self.original_page: Optional[Page] = None

    async def __aenter__(self):
        """Initialize Playwright and browser on context entry."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

        # Create context with recording options if specified
        import config as _config
        context_options = {
            'viewport': {'width': _config.VIDEO_SIZE_WIDTH, 'height': _config.VIDEO_SIZE_HEIGHT},
        }
        if self.record_video_dir:
            context_options['record_video_dir'] = self.record_video_dir
            context_options['record_video_size'] = {'width': _config.VIDEO_SIZE_WIDTH, 'height': _config.VIDEO_SIZE_HEIGHT}

        if self.record_har and self.record_video_dir:
            context_options['record_har_path'] = f"{self.record_video_dir}/network.har"

        # Create context with or without recording
        if context_options:
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
        else:
            self.page = await self.browser.new_page()
            self.context = self.page.context

        if _config.ENABLE_TRACE_RECORDING and self.record_video_dir:
            await self.context.tracing.start(screenshots=True, snapshots=True)

        self.page.set_default_timeout(self.timeout)
        self.original_page = self.page
        return self

    async def __aexit__(self, *args):
        """Cleanup resources on context exit."""
        # Close popup page if it differs from original
        if self.page and self.page != self.original_page:
            try:
                await self.page.close()
            except Exception:
                pass  # Popup may already be closed

        # Close original page
        if self.original_page:
            try:
                await self.original_page.close()
            except Exception:
                pass

        # Stop trace recording before closing context
        import config as _config
        from pathlib import Path
        if _config.ENABLE_TRACE_RECORDING and self.record_video_dir:
            try:
                trace_path = Path(self.record_video_dir) / "trace.zip"
                await self.context.tracing.stop(path=str(trace_path))
            except Exception:
                pass

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

    async def click_and_wait_for_popup(self, selector: str) -> str:
        """
        Click an element by CSS selector that opens a popup/new tab, then switch to it.

        Args:
            selector: CSS selector for the element that opens a popup

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        try:
            async with self.page.expect_popup(timeout=10000) as popup_info:
                await self.page.click(selector, timeout=5000)
            popup = await popup_info.value
            await popup.wait_for_load_state("domcontentloaded")
            self.page = popup
            return f"Clicked '{selector}' and switched to popup: {popup.url}"
        except Exception as e:
            return f"Error clicking '{selector}' for popup: {str(e)}"

    async def click_text_and_wait_for_popup(self, text: str) -> str:
        """
        Click an element by visible text that opens a popup/new tab, then switch to it.
        Use this for buttons like "Sign in with Google" that open OAuth popups.

        Args:
            text: The visible text of the element that opens a popup

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        import asyncio
        errors = []

        # Build click strategies: direct page clicks + iframe clicks
        async def _click_in_iframes(page, text):
            """Try clicking inside iframes (e.g. Google Sign-In button is in an iframe)."""
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    btn = frame.get_by_role("button", name=text)
                    if await btn.count() > 0:
                        await btn.click(timeout=3000)
                        return
                except Exception:
                    pass
                try:
                    btn = frame.locator(f"text={text}")
                    if await btn.count() > 0:
                        await btn.click(timeout=3000)
                        return
                except Exception:
                    pass
            # Also try frame_locator for common OAuth iframes
            for selector in [
                'iframe[title*="Sign in"]',
                'iframe[title*="sign in"]',
                'iframe[title*="Google"]',
                'iframe[data-provider]',
                'iframe[src*="accounts.google"]',
            ]:
                try:
                    fl = page.frame_locator(selector)
                    btn = fl.get_by_role("button").first
                    await btn.click(timeout=3000)
                    return
                except Exception:
                    pass
            raise Exception("No matching element found in any iframe")

        strategies = [
            ("iframe", lambda: _click_in_iframes(self.page, text)),
            ("getByText", lambda: self.page.get_by_text(text).click(timeout=5000)),
            ("getByRole button", lambda: self.page.get_by_role("button", name=text).click(timeout=5000)),
            ("text selector", lambda: self.page.click(f"text={text}", timeout=5000)),
        ]

        for strategy_name, click_fn in strategies:
            try:
                async with self.page.expect_popup(timeout=10000) as popup_info:
                    await click_fn()
                popup = await popup_info.value
                await popup.wait_for_load_state("domcontentloaded")
                self.page = popup
                return f"Clicked '{text}' (via {strategy_name}) and switched to popup: {popup.url}"
            except Exception as e:
                errors.append(f"{strategy_name}: {str(e)}")

        # Last resort: context-level page event listener
        try:
            popup_future = asyncio.get_event_loop().create_future()

            def on_page(page):
                if not popup_future.done():
                    popup_future.set_result(page)

            self.context.on("page", on_page)
            for _, click_fn in strategies:
                try:
                    await click_fn()
                    break
                except Exception:
                    continue

            popup = await asyncio.wait_for(popup_future, timeout=10)
            self.context.remove_listener("page", on_page)
            await popup.wait_for_load_state("domcontentloaded")
            self.page = popup
            return f"Clicked '{text}' (via context listener) and switched to popup: {popup.url}"
        except Exception as e:
            errors.append(f"context listener: {str(e)}")

        return f"Error: Could not click '{text}' and get popup. Attempts: {'; '.join(errors)}"

    async def switch_to_original_page(self) -> str:
        """
        Switch back to the original/main page after interacting with a popup.

        Returns:
            Confirmation message
        """
        if not self.original_page:
            return "Error: No original page to switch to"

        self.page = self.original_page
        try:
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return f"Switched back to original page: {self.page.url}"

    async def close_current_page(self) -> str:
        """
        Close the current popup page and switch back to the original page.
        Use this if a popup did not auto-close after completing an action.

        Returns:
            Confirmation message
        """
        if not self.page:
            return "Error: Browser not initialized"

        if self.page == self.original_page:
            return "Error: Cannot close the original page. Use this only for popups."

        try:
            await self.page.close()
        except Exception:
            pass  # Popup may already be closed

        self.page = self.original_page
        return f"Closed popup and switched back to original page: {self.page.url}"
