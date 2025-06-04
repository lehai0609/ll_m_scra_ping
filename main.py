"""Entry point and integration test."""
# main.py - Core Integration Test & Orchestration
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from config.settings import ScrapingConfig
from utils.logger import setup_logging  # Fixed import
from core.browser_pool import BrowserPool
from core.llm_agent import LLMNavigationAgent, ActionType
from core.action_executor import ActionExecutor

logger = logging.getLogger("layout_aware_scraper.main")

@dataclass
class ScrapingSession:
    """Represents a scraping session with state management"""
    url: str
    goal: str
    max_actions: int = 10
    current_action: int = 0
    results: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = {
                'actions_taken': [],
                'extracted_content': {},
                'navigation_path': [],
                'errors': []
            }

class LayoutAwareScraper:
    """Main orchestrator for LLM-driven web scraping"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.browser_pool = BrowserPool(config)
        self.llm_agent = LLMNavigationAgent(config)
        self.action_executor = ActionExecutor(config)
        
    async def initialize(self) -> None:
        """Initialize all components"""
        logger.info("Initializing Layout-Aware Scraper...")
        await self.browser_pool.initialize()
        logger.info("Scraper initialization complete")
    
    async def cleanup(self) -> None:
        """Clean up all resources"""
        logger.info("Cleaning up scraper resources...")
        await self.browser_pool.cleanup()
        logger.info("Scraper cleanup complete")
    
    async def scrape_page(self, session: ScrapingSession) -> Dict[str, Any]:
        """Execute a complete scraping session for a single page"""
        
        logger.info(f"Starting scraping session: {session.url}")
        logger.info(f"Goal: {session.goal}")
        
        async with self.browser_pool.get_page() as page:
            try:
                # Navigate to target URL
                await page.goto(session.url)
                await self.browser_pool.wait_for_content_loaded(page)
                
                session.results['navigation_path'].append(session.url)
                
                # Main scraping loop
                while session.current_action < session.max_actions:
                    session.current_action += 1
                    
                    logger.info(f"Action {session.current_action}/{session.max_actions}")
                    
                    # Analyze current page state
                    page_state = await self._analyze_current_page(page, session)
                    
                    # Get LLM recommendation
                    action = await self.llm_agent.analyze_page_and_plan_action(
                        accessibility_tree=page_state['accessibility_tree'],
                        current_url=page.url,
                        navigation_goal=session.goal,
                        page_content_summary=page_state['content_summary']
                    )
                    
                    # Record action
                    session.results['actions_taken'].append(action.to_dict())
                    
                    # Handle extraction vs navigation
                    if action.action_type == ActionType.EXTRACT:
                        content = await self._extract_content(page, action)
                        session.results['extracted_content'].update(content)
                        logger.info("Content extraction completed")
                        break
                    
                    elif action.action_type == ActionType.ERROR:
                        session.results['errors'].append(action.reasoning)
                        logger.error(f"LLM reported error: {action.reasoning}")
                        break
                    
                    else:
                        # Execute navigation action
                        result = await self.action_executor.execute_action(page, action)
                        
                        if not result.success:
                            session.results['errors'].append(result.message)
                            logger.warning(f"Action failed: {result.message}")
                            # Continue with next action rather than breaking
                        else:
                            logger.info(f"Action successful: {result.message}")
                            
                            # Add delay between actions
                            await self.browser_pool.add_random_delay()
                            
                            # Wait for page to settle
                            await self.browser_pool.wait_for_content_loaded(page)
                
                # Final content extraction if we haven't done it yet
                if not session.results['extracted_content']:
                    final_content = await self._extract_final_content(page)
                    session.results['extracted_content'].update(final_content)
                
                session.results['final_url'] = page.url
                session.results['total_actions'] = session.current_action
                
                logger.info(f"Scraping session completed: {session.current_action} actions taken")
                return session.results
                
            except Exception as e:
                logger.error(f"Scraping session failed: {e}")
                session.results['errors'].append(str(e))
                return session.results
    
    async def _analyze_current_page(self, page, session: ScrapingSession) -> Dict[str, Any]:
        """Analyze current page state for LLM decision making"""
        
        # Get accessibility tree
        accessibility_tree = await self.browser_pool.get_accessibility_tree(page)
        
        # Get basic page info
        title = await page.title()
        url = page.url
        
        # Get content summary (first part of visible text)
        try:
            content = await page.text_content('body')
            content_summary = content[:500] + "..." if len(content) > 500 else content
        except:
            content_summary = "Could not extract page content"
        
        page_state = {
            'title': title,
            'url': url,
            'accessibility_tree': accessibility_tree,
            'content_summary': content_summary,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        logger.debug(f"Page analysis complete: {title} ({len(str(accessibility_tree))} chars in a11y tree)")
        return page_state
    
    async def _extract_content(self, page, action) -> Dict[str, Any]:
        """Extract content based on LLM action parameters"""
        
        extracted = {}
        params = action.parameters
        
        try:
            # Extract different types of content
            if params.get('extract_title', True):
                title = await page.title()
                extracted['title'] = title
            
            if params.get('extract_text', True):
                text_content = await page.text_content('body')
                extracted['text_content'] = text_content
            
            if params.get('extract_links', False):
                links = await page.evaluate("""
                    Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: a.textContent.trim(),
                        href: a.href
                    })).filter(link => link.text && link.href)
                """)
                extracted['links'] = links
            
            # Extract specific selectors if provided
            if 'selectors' in params:
                for name, selector in params['selectors'].items():
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            extracted[name] = await element.text_content()
                    except Exception as e:
                        logger.debug(f"Could not extract {name} with selector {selector}: {e}")
            
            logger.info(f"Extracted {len(extracted)} content items")
            return extracted
            
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return {'extraction_error': str(e)}
    
    async def _extract_final_content(self, page) -> Dict[str, Any]:
        """Extract final content when session ends without explicit extraction"""
        
        try:
            final_content = {
                'final_title': await page.title(),
                'final_url': page.url,
                'final_text_preview': (await page.text_content('body'))[:1000]
            }
            
            # Try to extract any structured data visible
            try:
                # Look for lists, tables, etc.
                lists = await page.evaluate("""
                    Array.from(document.querySelectorAll('ul, ol')).map(list => 
                        Array.from(list.querySelectorAll('li')).map(li => li.textContent.trim())
                    ).filter(list => list.length > 0)
                """)
                if lists:
                    final_content['lists'] = lists
                    
            except Exception as e:
                logger.debug(f"Could not extract structured data: {e}")
            
            return final_content
            
        except Exception as e:
            logger.error(f"Final content extraction failed: {e}")
            return {'final_extraction_error': str(e)}

# Integration Test Function
async def test_kaggle_navigation():
    """Test the core system with a simple Kaggle page navigation"""
    
    # Setup
    config = ScrapingConfig.from_env()
    config.validate()
    
    # Initialize logging with the corrected import
    logger = setup_logging(config.log_level, config.log_file)
    
    scraper = LayoutAwareScraper(config)
    
    try:
        await scraper.initialize()
        
        # Test session: Navigate to Kaggle competition and find discussion section
        session = ScrapingSession(
            url="https://www.kaggle.com/competitions/openai-to-z-challenge",
            goal="Navigate to a OpenAI to Z competition page and find the discussion section",
            max_actions=5
        )
        
        results = await scraper.scrape_page(session)
        
        # Print results
        print("\n" + "="*50)
        print("SCRAPING RESULTS")
        print("="*50)
        print(f"Final URL: {results.get('final_url', 'N/A')}")
        print(f"Actions taken: {results.get('total_actions', 0)}")
        print(f"Errors: {len(results.get('errors', []))}")
        
        if results.get('extracted_content'):
            print(f"Content extracted: {list(results['extracted_content'].keys())}")
            
        if results.get('actions_taken'):
            print("\nActions taken:")
            for i, action in enumerate(results['actions_taken'], 1):
                print(f"  {i}. {action['action_type']} -> {action['target_description']}")
        
        if results.get('errors'):
            print("\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")
        
        print("\nLLM Conversation Summary:")
        print(scraper.llm_agent.get_conversation_summary())
        
        return results
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await scraper.cleanup()

if __name__ == "__main__":
    # Run the integration test
    print("Starting Layout-Aware Scraper Integration Test...")
    print("This will test navigation on Kaggle using LLM decision-making")
    
    results = asyncio.run(test_kaggle_navigation())
    
    print(f"\nTest completed! Check logs for detailed execution trace.")