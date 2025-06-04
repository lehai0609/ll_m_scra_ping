"""Browser automation with stealth."""
# core/browser_pool.py
import asyncio
import random
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, AsyncGenerator
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
import logging

from config.settings import ScrapingConfig

logger = logging.getLogger("layout_aware_scraper.browser_pool")

class BrowserPool:
    """Manages a pool of stealth-configured browser instances for web scraping"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self._context_semaphore = asyncio.Semaphore(config.max_concurrent_browsers)
        
    async def initialize(self) -> None:
        """Initialize the browser pool with stealth configuration"""
        logger.info("Initializing browser pool...")
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth configuration
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        logger.info(f"Browser pool initialized with max {self.config.max_concurrent_browsers} contexts")
    
    async def cleanup(self) -> None:
        """Clean up all browser resources"""
        logger.info("Cleaning up browser pool...")
        
        # Close all contexts
        for context_id, context in self.contexts.items():
            try:
                await context.close()
                logger.debug(f"Closed context: {context_id}")
            except Exception as e:
                logger.warning(f"Error closing context {context_id}: {e}")
        
        self.contexts.clear()
        
        # Close browser
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("Browser pool cleanup completed")
    
    @asynccontextmanager
    async def get_page(self, context_id: str = "default") -> AsyncGenerator[Page, None]:
        """Get a page with stealth configuration and automatic cleanup"""
        async with self._context_semaphore:
            context = await self._get_or_create_context(context_id)
            page = await context.new_page()
            
            try:
                # Configure stealth settings
                await self._configure_stealth(page)
                logger.debug(f"Created new page in context: {context_id}")
                yield page
                
            finally:
                await page.close()
                logger.debug(f"Closed page in context: {context_id}")
    
    async def _get_or_create_context(self, context_id: str) -> BrowserContext:
        """Get existing context or create new one with stealth configuration"""
        if context_id not in self.contexts:
            logger.debug(f"Creating new browser context: {context_id}")
            
            context = await self.browser.new_context(
                viewport={
                    'width': self.config.viewport_width,
                    'height': self.config.viewport_height
                },
                user_agent=self.config.user_agent,
                # Additional stealth options
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=True,
                bypass_csp=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0'
                }
            )
            
            self.contexts[context_id] = context
        
        return self.contexts[context_id]
    
    async def _configure_stealth(self, page: Page) -> None:
        """Apply stealth configuration to a page"""
        # Override navigator properties to appear more human-like
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state:'denied' }) :
                    originalQuery(parameters)
            );
            
            // Mock chrome runtime
            if (!window.chrome) {
                window.chrome = {};
            }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {};
            }
        """)
        
        # Set reasonable timeouts
        page.set_default_timeout(self.config.action_timeout * 1000)
        page.set_default_navigation_timeout(self.config.action_timeout * 1000)
        
        logger.debug("Applied stealth configuration to page")
    
    async def add_random_delay(self) -> None:
        """Add human-like random delay between actions"""
        delay = random.uniform(self.config.request_delay_min, self.config.request_delay_max)
        await asyncio.sleep(delay)
        logger.debug(f"Applied random delay: {delay:.2f}s")
    
    async def get_accessibility_tree(self, page: Page) -> Dict[str, Any]:
        """Extract accessibility tree for LLM analysis"""
        try:
            # Get accessibility tree snapshot
            accessibility_tree = await page.accessibility.snapshot(
                interesting_only=True,
                root=None
            )
            
            if not accessibility_tree:
                logger.warning("No accessibility tree available")
                return {}
            
            # Simplify tree structure for LLM consumption
            simplified_tree = self._simplify_accessibility_tree(accessibility_tree)
            logger.debug("Extracted accessibility tree")
            
            return simplified_tree
            
        except Exception as e:
            logger.error(f"Error extracting accessibility tree: {e}")
            return {}
    
    def _simplify_accessibility_tree(self, tree: Dict[str, Any], max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Simplify accessibility tree for LLM analysis"""
        if current_depth >= max_depth:
            return {"truncated": True}
        
        simplified = {}
        
        # Extract key properties
        for key in ['role', 'name', 'value', 'description', 'keyshortcuts', 'roledescription']:
            if key in tree:
                simplified[key] = str(tree[key])[:100]  # Truncate long values
        
        # Process children recursively
        if 'children' in tree and tree['children']:
            simplified['children'] = []
            for child in tree['children'][:10]:  # Limit children to prevent overwhelming LLM
                simplified_child = self._simplify_accessibility_tree(child, max_depth, current_depth + 1)
                if simplified_child:
                    simplified['children'].append(simplified_child)
        
        return simplified if simplified else None
    
    async def wait_for_content_loaded(self, page: Page, timeout: int = 30) -> bool:
        """Wait for page content to be fully loaded"""
        try:
            # Wait for network to be idle
            await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
            
            # Additional wait for dynamic content
            await page.wait_for_timeout(1000)
            
            logger.debug("Page content loaded successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Timeout waiting for content to load: {e}")
            return False