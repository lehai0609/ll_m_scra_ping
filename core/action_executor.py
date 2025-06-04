# core/action_executor.py
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.llm_agent import NavigationAction, ActionType
from config.settings import ScrapingConfig

logger = logging.getLogger("layout_aware_scraper.action_executor")

class ActionExecutionResult:
    """Result of an action execution"""
    
    def __init__(self, success: bool, message: str, data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        
    def __bool__(self) -> bool:
        return self.success

class ActionExecutor:
    """Executes navigation actions safely with comprehensive error handling"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.last_action_time = 0
        
    async def execute_action(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute a navigation action with appropriate error handling and validation"""
        
        logger.info(f"Executing action: {action.action_type.value} - {action.target_description}")
        
        # Validate action confidence
        if action.confidence < 0.3:
            logger.warning(f"Low confidence action ({action.confidence:.2f}): {action.reasoning}")
            return ActionExecutionResult(False, f"Action confidence too low: {action.confidence:.2f}")
        
        try:
            # Route to appropriate handler
            if action.action_type == ActionType.CLICK:
                return await self._execute_click(page, action)
            elif action.action_type == ActionType.TYPE:
                return await self._execute_type(page, action)
            elif action.action_type == ActionType.SCROLL:
                return await self._execute_scroll(page, action)
            elif action.action_type == ActionType.WAIT:
                return await self._execute_wait(page, action)
            elif action.action_type == ActionType.NAVIGATE:
                return await self._execute_navigate(page, action)
            elif action.action_type == ActionType.EXTRACT:
                return await self._execute_extract(page, action)
            else:
                return ActionExecutionResult(False, f"Unsupported action type: {action.action_type}")
                
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return ActionExecutionResult(False, f"Execution error: {str(e)}")
    
    async def _execute_click(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute click action with multiple fallback strategies"""
        
        params = action.parameters
        
        # Try multiple selector strategies
        selectors = self._generate_click_selectors(action.target_description, params)
        
        for i, selector in enumerate(selectors):
            try:
                logger.debug(f"Trying click selector {i+1}/{len(selectors)}: {selector}")
                
                # Wait for element to be available
                element = await page.wait_for_selector(selector, timeout=5000)
                if not element:
                    continue
                
                # Check if element is visible and enabled
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()
                
                if not is_visible or not is_enabled:
                    logger.debug(f"Element not interactive: visible={is_visible}, enabled={is_enabled}")
                    continue
                
                # Scroll element into view if needed
                await element.scroll_into_view_if_needed()
                
                # Perform click with options
                click_options = {
                    'timeout': self.config.action_timeout * 1000,
                    'force': params.get('force', False)
                }
                
                await element.click(**click_options)
                
                # Wait after click if specified
                wait_after = params.get('wait_after', 1000)
                await asyncio.sleep(wait_after / 1000)
                
                logger.info(f"Successfully clicked: {action.target_description}")
                return ActionExecutionResult(True, "Click executed successfully", {"selector": selector})
                
            except PlaywrightTimeoutError:
                logger.debug(f"Timeout with selector: {selector}")
                continue
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return ActionExecutionResult(False, f"Could not find clickable element: {action.target_description}")
    
    async def _execute_type(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute typing action in input fields"""
        
        params = action.parameters
        text = params.get('text', '')
        if not text:
            return ActionExecutionResult(False, "No text specified for typing action")
        
        selectors = self._generate_input_selectors(action.target_description, params)
        
        for selector in selectors:
            try:
                logger.debug(f"Trying type selector: {selector}")
                
                element = await page.wait_for_selector(selector, timeout=5000)
                if not element:
                    continue
                
                # Clear existing content if requested
                if params.get('clear', True):
                    await element.fill('')
                
                # Type text
                await element.type(text, delay=params.get('delay', 100))
                
                # Press enter if requested
                if params.get('press_enter', False):
                    await element.press('Enter')
                
                logger.info(f"Successfully typed text: {action.target_description}")
                return ActionExecutionResult(True, "Text input successful", {"selector": selector, "text": text})
                
            except Exception as e:
                logger.debug(f"Error typing with selector {selector}: {e}")
                continue
        
        return ActionExecutionResult(False, f"Could not find input element: {action.target_description}")
    
    async def _execute_scroll(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute scroll action"""
        
        params = action.parameters
        direction = params.get('direction', 'down')
        amount = params.get('amount', 500)
        
        try:
            if direction.lower() == 'down':
                await page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction.lower() == 'up':
                await page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction.lower() == 'to_bottom':
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction.lower() == 'to_top':
                await page.evaluate("window.scrollTo(0, 0)")
            else:
                return ActionExecutionResult(False, f"Invalid scroll direction: {direction}")
            
            # Wait for scroll to complete
            await asyncio.sleep(params.get('wait_after', 1000) / 1000)
            
            logger.info(f"Successfully scrolled {direction}: {amount}px")
            return ActionExecutionResult(True, "Scroll executed successfully", {"direction": direction, "amount": amount})
            
        except Exception as e:
            return ActionExecutionResult(False, f"Scroll failed: {str(e)}")
    
    async def _execute_wait(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute wait action"""
        
        params = action.parameters
        wait_type = params.get('type', 'timeout')
        
        try:
            if wait_type == 'timeout':
                duration = params.get('duration', 2000)
                await asyncio.sleep(duration / 1000)
                return ActionExecutionResult(True, f"Waited for {duration}ms")
                
            elif wait_type == 'element':
                selector = params.get('selector', '')
                timeout = params.get('timeout', 10000)
                await page.wait_for_selector(selector, timeout=timeout)
                return ActionExecutionResult(True, f"Element appeared: {selector}")
                
            elif wait_type == 'load_state':
                state = params.get('state', 'networkidle')
                timeout = params.get('timeout', 30000)
                await page.wait_for_load_state(state, timeout=timeout)
                return ActionExecutionResult(True, f"Load state reached: {state}")
                
            else:
                return ActionExecutionResult(False, f"Invalid wait type: {wait_type}")
                
        except PlaywrightTimeoutError:
            return ActionExecutionResult(False, f"Wait timeout: {wait_type}")
        except Exception as e:
            return ActionExecutionResult(False, f"Wait failed: {str(e)}")
    
    async def _execute_navigate(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute navigation to a URL"""
        
        params = action.parameters
        url = params.get('url', '')
        
        if not url:
            return ActionExecutionResult(False, "No URL specified for navigation")
        
        try:
            await page.goto(url, timeout=self.config.action_timeout * 1000)
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            logger.info(f"Successfully navigated to: {url}")
            return ActionExecutionResult(True, "Navigation successful", {"url": url})
            
        except Exception as e:
            return ActionExecutionResult(False, f"Navigation failed: {str(e)}")
    
    async def _execute_extract(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute content extraction"""
        
        params = action.parameters
        extraction_type = params.get('type', 'text')
        
        try:
            if extraction_type == 'text':
                content = await page.text_content('body')
                return ActionExecutionResult(True, "Text extracted", {"content": content})
                
            elif extraction_type == 'html':
                content = await page.content()
                return ActionExecutionResult(True, "HTML extracted", {"content": content})
                
            elif extraction_type == 'element':
                selector = params.get('selector', '')
                if selector:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        content = await element.text_content()
                        return ActionExecutionResult(True, "Element text extracted", {"content": content, "selector": selector})
                
            return ActionExecutionResult(False, f"Invalid extraction type or missing selector: {extraction_type}")
            
        except Exception as e:
            return ActionExecutionResult(False, f"Extraction failed: {str(e)}")
    
    def _generate_click_selectors(self, description: str, params: Dict[str, Any]) -> list[str]:
        """Generate multiple selector strategies for clicking elements"""
        
        selectors = []
        
        # Use provided selector if available
        if 'selector' in params:
            selectors.append(params['selector'])
        
        # Generate selectors based on description keywords
        desc_lower = description.lower()
        
        # Common patterns for navigation elements
        if 'tab' in desc_lower:
            selectors.extend([
                f"[role='tab']:has-text('{description}')",
                f"a:has-text('{description}')",
                f"button:has-text('{description}')",
                "[role='tab']",
                ".tab",
                "[data-tab]"
            ])
        
        if 'button' in desc_lower or 'click' in desc_lower:
            selectors.extend([
                f"button:has-text('{description}')",
                f"[role='button']:has-text('{description}')",
                f"input[type='button']:has-text('{description}')",
                f"a:has-text('{description}')"
            ])
        
        if 'link' in desc_lower:
            selectors.extend([
                f"a:has-text('{description}')",
                f"[href]:has-text('{description}')"
            ])
        
        # Generic fallbacks
        selectors.extend([
            f"*:has-text('{description}'):not(body):not(html)",
            f"[aria-label*='{description}']",
            f"[title*='{description}']",
            f"[alt*='{description}']"
        ])
        
        return selectors
    
    def _generate_input_selectors(self, description: str, params: Dict[str, Any]) -> list[str]:
        """Generate selectors for input elements"""
        
        selectors = []
        
        if 'selector' in params:
            selectors.append(params['selector'])
        
        desc_lower = description.lower()
        
        # Input-specific selectors
        selectors.extend([
            f"input[placeholder*='{description}']",
            f"input[name*='{desc_lower}']",
            f"textarea[placeholder*='{description}']",
            f"[contenteditable='true']",
            "input[type='text']",
            "input[type='search']",
            "textarea"
        ])
        
        return selectors
    
    async def validate_page_state(self, page: Page) -> Tuple[bool, str]:
        """Validate that the page is in a good state for actions"""
        
        try:
            # Check if page is loaded
            ready_state = await page.evaluate("document.readyState")
            if ready_state != 'complete':
                return False, f"Page not fully loaded: {ready_state}"
            
            # Check for common error indicators
            error_indicators = [
                "[class*='error']",
                "[class*='404']",
                "[class*='not-found']",
                "text='Access Denied'",
                "text='Page Not Found'"
            ]
            
            for indicator in error_indicators:
                try:
                    error_element = await page.query_selector(indicator)
                    if error_element and await error_element.is_visible():
                        error_text = await error_element.text_content()
                        return False, f"Page error detected: {error_text}"
                except:
                    continue
            
            return True, "Page state is valid"
            
        except Exception as e:
            return False, f"Could not validate page state: {str(e)}"