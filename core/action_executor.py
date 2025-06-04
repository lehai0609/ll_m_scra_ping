# core/action_executor.py - Enhanced version with semantic selector generation
import asyncio
import logging
import json
from typing import Dict, Any, Optional, Tuple, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
import openai

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

class SelectorStrategy:
    """Represents a selector with confidence and reasoning"""
    
    def __init__(self, selector: str, confidence: float, reasoning: str, category: str = "general"):
        self.selector = selector
        self.confidence = confidence
        self.reasoning = reasoning
        self.category = category
    
    def __repr__(self):
        return f"SelectorStrategy('{self.selector}', confidence={self.confidence:.2f}, category='{self.category}')"

class EnhancedActionExecutor:
    """Enhanced action executor with semantic selector generation using LLM"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.last_action_time = 0
        self.llm_client = openai.AsyncOpenAI(api_key=config.openai_api_key)
        
    async def execute_action(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute a navigation action with enhanced semantic selector generation"""
        
        logger.info(f"Executing action: {action.action_type.value} - {action.target_description}")
        
        # Validate action confidence
        if action.confidence < 0.3:
            logger.warning(f"Low confidence action ({action.confidence:.2f}): {action.reasoning}")
            return ActionExecutionResult(False, f"Action confidence too low: {action.confidence:.2f}")
        
        try:
            # Route to appropriate handler
            if action.action_type == ActionType.CLICK:
                return await self._execute_enhanced_click(page, action)
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
    
    async def _execute_enhanced_click(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute click action with enhanced semantic selector generation"""
        
        logger.info(f"Enhanced click execution for: {action.target_description}")
        
        # Step 1: Generate semantic selector strategies
        selector_strategies = await self._generate_semantic_selectors(
            action.target_description, 
            action.parameters,
            action_type="click"
        )
        
        logger.debug(f"Generated {len(selector_strategies)} selector strategies")
        
        # Step 2: Try each strategy in order of confidence
        sorted_strategies = sorted(selector_strategies, key=lambda x: x.confidence, reverse=True)
        
        for i, strategy in enumerate(sorted_strategies):
            try:
                logger.debug(f"Trying strategy {i+1}/{len(sorted_strategies)}: {strategy}")
                
                # Wait for element with shorter timeout for each attempt
                timeout = max(2000, 8000 - (i * 1000))  # Decreasing timeout
                element = await page.wait_for_selector(strategy.selector, timeout=timeout)
                
                if not element:
                    logger.debug(f"Element not found with selector: {strategy.selector}")
                    continue
                
                # Check if element is interactive
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()
                
                if not is_visible or not is_enabled:
                    logger.debug(f"Element not interactive: visible={is_visible}, enabled={is_enabled}")
                    continue
                
                # Get element info for logging
                element_info = await self._get_element_info(element)
                logger.info(f"Found interactive element: {element_info}")
                
                # Scroll element into view if needed
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)  # Brief pause for scroll
                
                # Perform click with options
                click_options = {
                    'timeout': 10000,
                    'force': action.parameters.get('force', False)
                }
                
                await element.click(**click_options)
                
                # Wait after click
                wait_after = action.parameters.get('wait_after', 2000)
                await asyncio.sleep(wait_after / 1000)
                
                logger.info(f"Successfully clicked using strategy: {strategy.category}")
                return ActionExecutionResult(
                    True, 
                    f"Click executed successfully using {strategy.category} strategy", 
                    {
                        "selector": strategy.selector,
                        "strategy": strategy.category,
                        "confidence": strategy.confidence,
                        "element_info": element_info
                    }
                )
                
            except PlaywrightTimeoutError:
                logger.debug(f"Timeout with selector: {strategy.selector}")
                continue
            except Exception as e:
                logger.debug(f"Error with selector {strategy.selector}: {e}")
                continue
        
        # If all strategies failed, provide detailed failure analysis
        failure_info = {
            "strategies_tried": len(selector_strategies),
            "strategies": [{"selector": s.selector, "confidence": s.confidence, "category": s.category} for s in sorted_strategies[:5]]
        }
        
        return ActionExecutionResult(
            False, 
            f"Could not find clickable element after trying {len(selector_strategies)} strategies", 
            failure_info
        )
    
    async def _generate_semantic_selectors(
        self, 
        description: str, 
        params: Dict[str, Any],
        action_type: str = "click"
    ) -> List[SelectorStrategy]:
        """Generate semantically intelligent selectors using LLM parsing + rule-based generation"""
        
        strategies = []
        
        # Step 1: Use provided selector if available (highest confidence)
        if 'selector' in params:
            strategies.append(SelectorStrategy(
                selector=params['selector'],
                confidence=1.0,
                reasoning="Explicitly provided selector",
                category="explicit"
            ))
        
        # Step 2: Parse description using LLM
        try:
            parsed_components = await self._parse_description_with_llm(description)
            logger.debug(f"Parsed components: {parsed_components}")
            
            # Step 3: Generate selectors from parsed components
            semantic_strategies = self._generate_selectors_from_components(parsed_components)
            strategies.extend(semantic_strategies)
            
        except Exception as e:
            logger.warning(f"LLM parsing failed, falling back to rule-based: {e}")
        
        # Step 4: Add rule-based fallback strategies
        fallback_strategies = self._generate_fallback_selectors(description)
        strategies.extend(fallback_strategies)
        
        return strategies
    
    async def _parse_description_with_llm(self, description: str) -> Dict[str, Any]:
        """Use LLM to parse action description into semantic components"""
        
        context = f"""
Parse this UI element description into structured components for web automation:

Description: "{description}"

Extract the following components and respond with JSON:
{{
  "target_text": "The actual clickable text (e.g., 'Discussion', 'Login', 'Submit')",
  "element_type": "The type of element (button, link, tab, input, etc.)",
  "context_area": "Where the element is located (navigation, header, sidebar, main, footer)",
  "modifiers": ["Additional descriptive words like 'main', 'primary', 'top'"],
  "action_hint": "What clicking this element should do",
  "alternative_text": ["Other possible text variations for the same element"]
}}

Examples:
- "Login button in header" → {{"target_text": "Login", "element_type": "button", "context_area": "header"}}
- "Discussions link in the main navigation" → {{"target_text": "Discussions", "element_type": "link", "context_area": "navigation", "modifiers": ["main"]}}
- "Submit form button" → {{"target_text": "Submit", "element_type": "button", "context_area": "form"}}

Be concise and focus on the most likely interpretation.
        """
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at parsing UI element descriptions for web automation. Always respond with valid JSON."},
                    {"role": "user", "content": context}
                ],
                max_tokens=300,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content.strip())
            
        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            # Return minimal parsed structure as fallback
            return {
                "target_text": description.split()[0] if description.split() else "unknown",
                "element_type": "unknown",
                "context_area": "page",
                "modifiers": [],
                "action_hint": "click",
                "alternative_text": []
            }
    
    def _generate_selectors_from_components(self, components: Dict[str, Any]) -> List[SelectorStrategy]:
        """Generate intelligent selectors from parsed semantic components"""
        
        strategies = []
        target_text = components.get("target_text", "")
        element_type = components.get("element_type", "")
        context_area = components.get("context_area", "")
        modifiers = components.get("modifiers", [])
        alternative_texts = components.get("alternative_text", [])
        
        if not target_text:
            return strategies
        
        # Context-based selectors (highest confidence for specific contexts)
        context_selectors = self._get_context_selectors(context_area, modifiers)
        
        # Element type mapping
        element_selectors = self._get_element_type_selectors(element_type)
        
        # Strategy 1: Context + Element + Exact Text (highest confidence)
        for ctx_sel in context_selectors[:2]:  # Top 2 context selectors
            for elem_sel in element_selectors[:2]:  # Top 2 element selectors
                selector = f"{ctx_sel} {elem_sel}:has-text('{target_text}')"
                strategies.append(SelectorStrategy(
                    selector=selector,
                    confidence=0.95,
                    reasoning=f"Context-specific {element_type} with exact text",
                    category="semantic_precise"
                ))
        
        # Strategy 2: Element + Exact Text (high confidence)
        for elem_sel in element_selectors:
            selector = f"{elem_sel}:has-text('{target_text}')"
            strategies.append(SelectorStrategy(
                selector=selector,
                confidence=0.85,
                reasoning=f"Element type with exact text",
                category="semantic_element"
            ))
        
        # Strategy 3: Context + Any Element + Text (medium-high confidence)
        for ctx_sel in context_selectors:
            selector = f"{ctx_sel} *:has-text('{target_text}')"
            strategies.append(SelectorStrategy(
                selector=selector,
                confidence=0.75,
                reasoning=f"Context area with any element containing text",
                category="semantic_context"
            ))
        
        # Strategy 4: Alternative text variations (medium confidence)
        for alt_text in alternative_texts:
            for elem_sel in element_selectors[:2]:
                selector = f"{elem_sel}:has-text('{alt_text}')"
                strategies.append(SelectorStrategy(
                    selector=selector,
                    confidence=0.70,
                    reasoning=f"Alternative text variation: {alt_text}",
                    category="semantic_alternative"
                ))
        
        # Strategy 5: Partial text matching (medium confidence)
        if len(target_text) > 3:  # Only for longer text
            for elem_sel in element_selectors:
                selector = f"{elem_sel}:has-text('{target_text[:len(target_text)//2]}')"
                strategies.append(SelectorStrategy(
                    selector=selector,
                    confidence=0.65,
                    reasoning=f"Partial text match",
                    category="semantic_partial"
                ))
        
        # Strategy 6: Attribute-based selectors (medium confidence)
        if element_type == "link":
            # For links, try href-based selectors
            href_keywords = target_text.lower().replace(" ", "").replace("-", "")
            selector = f"a[href*='{href_keywords}']"
            strategies.append(SelectorStrategy(
                selector=selector,
                confidence=0.70,
                reasoning=f"Link href containing keyword",
                category="semantic_attribute"
            ))
        
        return strategies
    
    def _get_context_selectors(self, context_area: str, modifiers: List[str]) -> List[str]:
        """Get context-specific selectors based on page area"""
        
        context_map = {
            "navigation": ["nav", "[role='navigation']", ".navigation", ".nav", "header nav"],
            "header": ["header", ".header", "[role='banner']", "header nav", ".site-header"],
            "sidebar": [".sidebar", ".side-nav", "[role='complementary']", "aside"],
            "main": ["main", "[role='main']", ".main-content", ".content"],
            "footer": ["footer", ".footer", "[role='contentinfo']", ".site-footer"],
            "form": ["form", ".form", "[role='form']"],
            "menu": [".menu", "[role='menu']", ".dropdown-menu", ".nav-menu"],
            "tab": [".tabs", "[role='tablist']", ".tab-container"],
            "page": ["body", "main", ".page"]  # Fallback for general page context
        }
        
        selectors = context_map.get(context_area.lower(), ["body"])
        
        # Apply modifiers
        if "main" in modifiers and context_area != "main":
            # Add main-specific variants
            selectors = [f"main {sel}" for sel in selectors] + selectors
        
        return selectors
    
    def _get_element_type_selectors(self, element_type: str) -> List[str]:
        """Get element-specific selectors based on element type"""
        
        type_map = {
            "button": ["button", "[role='button']", "input[type='button']", "input[type='submit']"],
            "link": ["a", "[role='link']"],
            "tab": ["[role='tab']", ".tab", "a[role='tab']"],
            "input": ["input", "textarea", "[contenteditable]"],
            "checkbox": ["input[type='checkbox']", "[role='checkbox']"],
            "radio": ["input[type='radio']", "[role='radio']"],
            "select": ["select", "[role='listbox']"],
            "menu": ["[role='menuitem']", ".menu-item"],
            "unknown": ["*"]  # Fallback for unknown types
        }
        
        return type_map.get(element_type.lower(), ["*"])
    
    def _generate_fallback_selectors(self, description: str) -> List[SelectorStrategy]:
        """Generate rule-based fallback selectors (legacy approach as backup)"""
        
        strategies = []
        desc_lower = description.lower()
        
        # Extract potential clickable text from description
        words = description.split()
        potential_texts = []
        
        # Look for quoted text or capitalized words
        for word in words:
            clean_word = word.strip('.,!?;:"()[]{}')
            if len(clean_word) > 2 and (clean_word[0].isupper() or clean_word in ['Discussion', 'Discussions']):
                potential_texts.append(clean_word)
        
        # Common element types based on keywords
        if any(keyword in desc_lower for keyword in ['tab', 'tabs']):
            for text in potential_texts:
                strategies.append(SelectorStrategy(
                    selector=f"[role='tab']:has-text('{text}')",
                    confidence=0.60,
                    reasoning=f"Tab role with text: {text}",
                    category="fallback_tab"
                ))
        
        if any(keyword in desc_lower for keyword in ['button', 'btn']):
            for text in potential_texts:
                strategies.append(SelectorStrategy(
                    selector=f"button:has-text('{text}')",
                    confidence=0.60,
                    reasoning=f"Button with text: {text}",
                    category="fallback_button"
                ))
        
        if any(keyword in desc_lower for keyword in ['link', 'href']):
            for text in potential_texts:
                strategies.append(SelectorStrategy(
                    selector=f"a:has-text('{text}')",
                    confidence=0.60,
                    reasoning=f"Link with text: {text}",
                    category="fallback_link"
                ))
        
        # Generic text-based fallbacks (lowest confidence)
        for text in potential_texts:
            strategies.append(SelectorStrategy(
                selector=f"*:has-text('{text}'):not(body):not(html)",
                confidence=0.40,
                reasoning=f"Any element with text: {text}",
                category="fallback_generic"
            ))
        
        return strategies
    
    async def _get_element_info(self, element) -> Dict[str, Any]:
        """Get detailed information about an element for logging"""
        try:
            return {
                "tag": await element.evaluate("el => el.tagName"),
                "text": (await element.text_content() or "")[:50],
                "href": await element.evaluate("el => el.href || ''"),
                "role": await element.evaluate("el => el.getAttribute('role') || ''")
            }
        except:
            return {"info": "Could not retrieve element details"}
    
    # Keep all the other methods unchanged (_execute_type, _execute_scroll, etc.)
    async def _execute_type(self, page: Page, action: NavigationAction) -> ActionExecutionResult:
        """Execute typing action in input fields"""
        
        params = action.parameters
        text = params.get('text', '')
        if not text:
            return ActionExecutionResult(False, "No text specified for typing action")
        
        # Use semantic selector generation for input fields too
        selector_strategies = await self._generate_semantic_selectors(
            action.target_description, 
            params,
            action_type="type"
        )
        
        for strategy in sorted(selector_strategies, key=lambda x: x.confidence, reverse=True):
            try:
                logger.debug(f"Trying input selector: {strategy.selector}")
                
                element = await page.wait_for_selector(strategy.selector, timeout=5000)
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
                
                logger.info(f"Successfully typed text using {strategy.category}: {action.target_description}")
                return ActionExecutionResult(True, "Text input successful", {"selector": strategy.selector, "text": text})
                
            except Exception as e:
                logger.debug(f"Error typing with selector {strategy.selector}: {e}")
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