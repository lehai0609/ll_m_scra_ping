"""Entry point and integration test - Updated with Enhanced Action Executor."""
# main.py - Updated with Enhanced Action Executor
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from config.settings import ScrapingConfig
from utils.logger import setup_logging
from core.browser_pool import BrowserPool
from core.llm_agent import LLMNavigationAgent, ActionType
from core.action_executor import EnhancedActionExecutor  # Updated import
from dotenv import load_dotenv
load_dotenv()

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
                'errors': [],
                'selector_strategies_used': []  # Track successful strategies
            }

class LayoutAwareScraper:
    """Main orchestrator for LLM-driven web scraping with enhanced action execution"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.browser_pool = BrowserPool(config)
        self.llm_agent = LLMNavigationAgent(config)
        self.action_executor = EnhancedActionExecutor(config)  # Updated to use enhanced version
        
    async def initialize(self) -> None:
        """Initialize all components"""
        logger.info("Initializing Layout-Aware Scraper with Enhanced Action Executor...")
        await self.browser_pool.initialize()
        logger.info("Enhanced scraper initialization complete")
    
    async def cleanup(self) -> None:
        """Clean up all resources"""
        logger.info("Cleaning up scraper resources...")
        await self.browser_pool.cleanup()
        logger.info("Scraper cleanup complete")
    
    async def scrape_page(self, session: ScrapingSession) -> Dict[str, Any]:
        """Execute a complete scraping session for a single page with enhanced action execution"""
        
        logger.info(f"Starting enhanced scraping session: {session.url}")
        logger.info(f"Goal: {session.goal}")
        
        async with self.browser_pool.get_page() as page:
            try:
                # Navigate to target URL
                await page.goto(session.url)
                await self.browser_pool.wait_for_content_loaded(page)
                
                session.results['navigation_path'].append(session.url)
                
                # Main scraping loop with enhanced action execution
                while session.current_action < session.max_actions:
                    session.current_action += 1
                    
                    logger.info(f"Enhanced Action {session.current_action}/{session.max_actions}")
                    
                    # Analyze current page state
                    page_state = await self._analyze_current_page(page, session)
                    
                    # Get LLM recommendation
                    action = await self.llm_agent.analyze_page_and_plan_action(
                        accessibility_tree=page_state['accessibility_tree'],
                        current_url=page.url,
                        navigation_goal=session.goal,
                        page_content_summary=page_state['content_summary']
                    )
                    
                    # Record action with enhanced details
                    action_record = action.to_dict()
                    action_record['page_title'] = page_state['title']
                    action_record['page_url'] = page_state['url']
                    session.results['actions_taken'].append(action_record)
                    
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
                        # Execute navigation action with enhanced executor
                        result = await self.action_executor.execute_action(page, action)
                        
                        # Record detailed execution results
                        execution_record = {
                            'action_type': action.action_type.value,
                            'target_description': action.target_description,
                            'success': result.success,
                            'message': result.message,
                            'execution_data': result.data
                        }
                        
                        if not result.success:
                            session.results['errors'].append(execution_record)
                            logger.warning(f"Enhanced action failed: {result.message}")
                            
                            # For enhanced executor, we can analyze failure details
                            if result.data and 'strategies_tried' in result.data:
                                strategies_info = result.data['strategies']
                                logger.info(f"Tried {result.data['strategies_tried']} strategies:")
                                for strategy in strategies_info:
                                    logger.debug(f"  - {strategy['category']}: {strategy['selector']} (confidence: {strategy['confidence']:.2f})")
                            
                            # Continue with next action rather than breaking for potential recovery
                        else:
                            logger.info(f"Enhanced action successful: {result.message}")
                            
                            # Track successful strategy for learning
                            if result.data and 'strategy' in result.data:
                                session.results['selector_strategies_used'].append({
                                    'action': action.target_description,
                                    'strategy': result.data['strategy'],
                                    'selector': result.data['selector'],
                                    'confidence': result.data.get('confidence', 0.0)
                                })
                            
                            # Add delay between actions
                            await self.browser_pool.add_random_delay()
                            
                            # Wait for page to settle after navigation
                            await self.browser_pool.wait_for_content_loaded(page)
                            
                            # Check if URL changed (successful navigation)
                            new_url = page.url
                            if new_url != page_state['url']:
                                session.results['navigation_path'].append(new_url)
                                logger.info(f"Navigation detected: {page_state['url']} → {new_url}")
                
                # Final content extraction if we haven't done it yet
                if not session.results['extracted_content']:
                    final_content = await self._extract_final_content(page)
                    session.results['extracted_content'].update(final_content)
                
                # Enhanced session results
                session.results['final_url'] = page.url
                session.results['total_actions'] = session.current_action
                session.results['successful_navigation'] = len(session.results['navigation_path']) > 1
                session.results['strategies_learned'] = len(session.results['selector_strategies_used'])
                
                logger.info(f"Enhanced scraping session completed: {session.current_action} actions taken")
                logger.info(f"Navigation success: {session.results['successful_navigation']}")
                logger.info(f"Strategies learned: {session.results['strategies_learned']}")
                
                return session.results
                
            except Exception as e:
                logger.error(f"Enhanced scraping session failed: {e}")
                session.results['errors'].append({
                    'type': 'session_failure',
                    'error': str(e),
                    'action_number': session.current_action
                })
                return session.results
    
    async def _analyze_current_page(self, page, session: ScrapingSession) -> Dict[str, Any]:
        """Analyze current page state for LLM decision making with enhanced details"""
        
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
        
        # Enhanced page analysis for better LLM context
        try:
            page_metrics = await page.evaluate("""
                () => {
                    return {
                        clickable_elements: document.querySelectorAll('a, button, [role="button"], [role="tab"]').length,
                        form_elements: document.querySelectorAll('input, textarea, select').length,
                        navigation_elements: document.querySelectorAll('nav, [role="navigation"]').length,
                        has_tabs: document.querySelectorAll('[role="tab"]').length > 0,
                        has_discussions: document.body.textContent.toLowerCase().includes('discussion'),
                        viewport_height: window.innerHeight,
                        scroll_position: window.pageYOffset,
                        total_height: document.body.scrollHeight
                    };
                }
            """)
        except:
            page_metrics = {}
        
        page_state = {
            'title': title,
            'url': url,
            'accessibility_tree': accessibility_tree,
            'content_summary': content_summary,
            'page_metrics': page_metrics,
            'timestamp': asyncio.get_event_loop().time(),
            'action_number': session.current_action
        }
        
        logger.debug(f"Enhanced page analysis complete: {title}")
        logger.debug(f"Page metrics: {page_metrics}")
        
        return page_state
    
    async def _extract_content(self, page, action) -> Dict[str, Any]:
        """Extract content based on LLM action parameters with enhanced extraction"""
        
        extracted = {}
        params = action.parameters
        
        try:
            # Standard extractions
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
            
            # Enhanced extraction for discussion pages
            if 'discussion' in page.url.lower():
                try:
                    discussion_data = await page.evaluate("""
                        () => {
                            const discussions = [];
                            
                            // Look for discussion thread elements
                            const threadElements = document.querySelectorAll('[data-testid*="discussion"], .discussion-item, .thread-item');
                            threadElements.forEach(el => {
                                const title = el.querySelector('h1, h2, h3, .title, [data-testid*="title"]');
                                const author = el.querySelector('.author, [data-testid*="author"]');
                                const date = el.querySelector('.date, [data-testid*="date"]');
                                
                                if (title) {
                                    discussions.push({
                                        title: title.textContent.trim(),
                                        author: author ? author.textContent.trim() : null,
                                        date: date ? date.textContent.trim() : null
                                    });
                                }
                            });
                            
                            return {
                                discussion_threads: discussions,
                                total_threads: discussions.length,
                                page_type: 'discussion_listing'
                            };
                        }
                    """)
                    extracted['discussion_data'] = discussion_data
                    logger.info(f"Extracted discussion data: {discussion_data['total_threads']} threads found")
                except Exception as e:
                    logger.debug(f"Could not extract discussion-specific data: {e}")
            
            # Extract specific selectors if provided
            if 'selectors' in params:
                for name, selector in params['selectors'].items():
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            extracted[name] = await element.text_content()
                    except Exception as e:
                        logger.debug(f"Could not extract {name} with selector {selector}: {e}")
            
            # Enhanced metadata extraction
            extracted['extraction_metadata'] = {
                'url': page.url,
                'timestamp': asyncio.get_event_loop().time(),
                'extraction_method': 'enhanced_llm_guided'
            }
            
            logger.info(f"Enhanced extraction completed: {len(extracted)} content items")
            return extracted
            
        except Exception as e:
            logger.error(f"Enhanced content extraction failed: {e}")
            return {'extraction_error': str(e)}
    
    async def _extract_final_content(self, page) -> Dict[str, Any]:
        """Extract final content when session ends without explicit extraction"""
        
        try:
            final_content = {
                'final_title': await page.title(),
                'final_url': page.url,
                'final_text_preview': (await page.text_content('body'))[:1000]
            }
            
            # Enhanced structured data extraction
            try:
                structured_data = await page.evaluate("""
                    () => {
                        const data = {
                            lists: [],
                            tables: [],
                            headings: [],
                            navigation_elements: []
                        };
                        
                        // Extract lists
                        document.querySelectorAll('ul, ol').forEach(list => {
                            const items = Array.from(list.querySelectorAll('li')).map(li => li.textContent.trim());
                            if (items.length > 0) {
                                data.lists.push(items);
                            }
                        });
                        
                        // Extract tables
                        document.querySelectorAll('table').forEach(table => {
                            const rows = Array.from(table.querySelectorAll('tr')).map(row => 
                                Array.from(row.querySelectorAll('td, th')).map(cell => cell.textContent.trim())
                            );
                            if (rows.length > 0) {
                                data.tables.push(rows);
                            }
                        });
                        
                        // Extract headings
                        document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
                            data.headings.push({
                                level: heading.tagName,
                                text: heading.textContent.trim()
                            });
                        });
                        
                        // Extract navigation elements
                        document.querySelectorAll('nav a, [role="navigation"] a').forEach(link => {
                            data.navigation_elements.push({
                                text: link.textContent.trim(),
                                href: link.href
                            });
                        });
                        
                        return data;
                    }
                """)
                
                final_content['structured_data'] = structured_data
                logger.info(f"Enhanced final extraction: {len(structured_data['lists'])} lists, {len(structured_data['tables'])} tables, {len(structured_data['headings'])} headings")
                    
            except Exception as e:
                logger.debug(f"Could not extract enhanced structured data: {e}")
            
            return final_content
            
        except Exception as e:
            logger.error(f"Enhanced final content extraction failed: {e}")
            return {'final_extraction_error': str(e)}

# Enhanced Integration Test Function
async def test_enhanced_kaggle_navigation():
    """Test the enhanced system with semantic selector generation"""
    
    # Setup
    config = ScrapingConfig.from_env()
    config.validate()
    
    # Initialize logging
    logger = setup_logging(config.log_level, config.log_file)
    
    scraper = LayoutAwareScraper(config)
    
    try:
        await scraper.initialize()
        
        # Enhanced test session: Navigate to Kaggle competition and find discussion section
        session = ScrapingSession(
            url="https://www.kaggle.com/competitions/openai-to-z-challenge",
            goal="Navigate to the Discussion section of the OpenAI to Z Challenge competition",
            max_actions=5
        )
        
        results = await scraper.scrape_page(session)
        
        # Enhanced results display
        print("\n" + "="*60)
        print("ENHANCED SCRAPING RESULTS")
        print("="*60)
        print(f"Final URL: {results.get('final_url', 'N/A')}")
        print(f"Actions taken: {results.get('total_actions', 0)}")
        print(f"Successful navigation: {results.get('successful_navigation', False)}")
        print(f"Errors: {len(results.get('errors', []))}")
        print(f"Strategies learned: {results.get('strategies_learned', 0)}")
        
        if results.get('navigation_path'):
            print(f"\nNavigation path:")
            for i, url in enumerate(results['navigation_path'], 1):
                print(f"  {i}. {url}")
        
        if results.get('extracted_content'):
            print(f"\nContent extracted: {list(results['extracted_content'].keys())}")
            
            # Show discussion-specific data if available
            if 'discussion_data' in results['extracted_content']:
                disc_data = results['extracted_content']['discussion_data']
                print(f"Discussion threads found: {disc_data.get('total_threads', 0)}")
        
        if results.get('actions_taken'):
            print(f"\nActions taken:")
            for i, action in enumerate(results['actions_taken'], 1):
                print(f"  {i}. {action['action_type']} -> {action['target_description']}")
                if action.get('confidence'):
                    print(f"     Confidence: {action['confidence']:.2f}")
        
        if results.get('selector_strategies_used'):
            print(f"\nSuccessful selector strategies:")
            for strategy in results['selector_strategies_used']:
                print(f"  - {strategy['strategy']}: {strategy['selector']}")
                print(f"    For: {strategy['action']} (confidence: {strategy['confidence']:.2f})")
        
        if results.get('errors'):
            print(f"\nErrors:")
            for error in results['errors']:
                if isinstance(error, dict):
                    print(f"  - {error.get('message', error.get('error', 'Unknown error'))}")
                else:
                    print(f"  - {error}")
        
        print(f"\nLLM Conversation Summary:")
        print(scraper.llm_agent.get_conversation_summary())
        
        # Success evaluation
        success_indicators = [
            results.get('successful_navigation', False),
            'discussion' in results.get('final_url', '').lower(),
            len(results.get('selector_strategies_used', [])) > 0,
            len(results.get('errors', [])) == 0
        ]
        
        overall_success = sum(success_indicators) >= 2
        print(f"\n🎯 OVERALL SUCCESS: {'✅ YES' if overall_success else '❌ NO'}")
        print(f"Success indicators: {sum(success_indicators)}/4")
        
        return results
        
    except Exception as e:
        logger.error(f"Enhanced test failed: {e}")
        raise
    finally:
        await scraper.cleanup()

if __name__ == "__main__":
    # Run the enhanced integration test
    print("🚀 Starting Enhanced Layout-Aware Scraper Integration Test...")
    print("This will test navigation on Kaggle using enhanced LLM decision-making and semantic selector generation")
    
    results = asyncio.run(test_enhanced_kaggle_navigation())
    
    print(f"\n🏁 Enhanced test completed! Check logs for detailed execution trace.")