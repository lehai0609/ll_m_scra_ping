# targeted_discussion_test.py - Specific test for Discussion tab clicking
import asyncio
import logging
from typing import Dict, Any, List
from config.settings import ScrapingConfig
from core.browser_pool import BrowserPool
from core.llm_agent import LLMNavigationAgent, NavigationAction, ActionType
from core.action_executor import ActionExecutor
from dotenv import load_dotenv

load_dotenv()

async def test_discussion_tab_clicking():
    """Targeted test specifically for Discussion tab interaction"""
    
    print("🎯 TARGETED DISCUSSION TAB CLICKING TEST")
    print("=" * 50)
    
    config = ScrapingConfig.from_env()
    browser_pool = BrowserPool(config)
    action_executor = ActionExecutor(config)
    llm_agent = LLMNavigationAgent(config)
    
    try:
        await browser_pool.initialize()
        
        async with browser_pool.get_page() as page:
            url = "https://www.kaggle.com/competitions/openai-to-z-challenge"
            print(f"📍 Loading: {url}")
            
            await page.goto(url)
            await browser_pool.wait_for_content_loaded(page)
            
            print(f"✅ Page loaded: {await page.title()}")
            
            # Step 1: Find ALL discussion-related elements with detailed analysis
            discussion_elements = await page.evaluate("""
                () => {
                    const results = [];
                    
                    // Find all elements containing "discussion" text
                    const allElements = Array.from(document.querySelectorAll('*'));
                    allElements.forEach((el, index) => {
                        const text = el.textContent?.toLowerCase() || '';
                        if (text.includes('discussion') && text.length < 100) {
                            const rect = el.getBoundingClientRect();
                            results.push({
                                index: index,
                                tagName: el.tagName,
                                text: el.textContent.trim(),
                                className: el.className,
                                id: el.id,
                                href: el.href || '',
                                role: el.getAttribute('role'),
                                tabindex: el.getAttribute('tabindex'),
                                isVisible: rect.width > 0 && rect.height > 0,
                                isInViewport: rect.top >= 0 && rect.left >= 0 && 
                                             rect.bottom <= window.innerHeight && 
                                             rect.right <= window.innerWidth,
                                boundingRect: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height
                                },
                                computedStyle: {
                                    display: window.getComputedStyle(el).display,
                                    visibility: window.getComputedStyle(el).visibility,
                                    opacity: window.getComputedStyle(el).opacity,
                                    pointerEvents: window.getComputedStyle(el).pointerEvents
                                }
                            });
                        }
                    });
                    
                    return results.slice(0, 10); // Limit for readability
                }
            """)
            
            print(f"\n🔍 DISCUSSION ELEMENTS DETAILED ANALYSIS:")
            for i, el in enumerate(discussion_elements, 1):
                print(f"\n   {i}. {el['tagName']} - '{el['text'][:50]}'")
                print(f"      🔗 href: {el['href']}")
                print(f"      🎭 role: {el['role']}")
                print(f"      👁️  visible: {el['isVisible']}, in viewport: {el['isInViewport']}")
                print(f"      📐 size: {el['boundingRect']['width']}x{el['boundingRect']['height']}")
                print(f"      🎨 display: {el['computedStyle']['display']}, visibility: {el['computedStyle']['visibility']}")
                print(f"      🖱️  pointer-events: {el['computedStyle']['pointerEvents']}")
            
            # Step 2: Try multiple clicking strategies
            print(f"\n🎯 TESTING CLICK STRATEGIES:")
            
            # Strategy 1: Direct tab element click
            print(f"\n   Strategy 1: Tab role element")
            tab_click_result = await test_click_strategy(page, "[role='tab']:has-text('Discussion')")
            
            # Strategy 2: Direct href click
            print(f"\n   Strategy 2: Discussion href link")
            href_click_result = await test_click_strategy(page, "a[href*='/discussion']")
            
            # Strategy 3: Text-based click
            print(f"\n   Strategy 3: Text-based selection")
            text_click_result = await test_click_strategy(page, "text='Discussion'")
            
            # Strategy 4: Multiple selector fallback
            print(f"\n   Strategy 4: Multiple selector fallback")
            selectors = [
                "[role='tab']:has-text('Discussion')",
                "a[href*='discussion']:has-text('Discussion')",
                "[data-tab*='discussion']",
                ".tab:has-text('Discussion')",
                "button:has-text('Discussion')",
                "*:has-text('Discussion'):not(body):not(html)"
            ]
            
            multi_click_result = await test_multiple_selectors(page, selectors)
            
            # Step 3: Test LLM-based approach
            print(f"\n🤖 TESTING LLM-BASED APPROACH:")
            
            # Get accessibility tree
            accessibility_tree = await browser_pool.get_accessibility_tree(page)
            
            # Ask LLM to plan action
            action = await llm_agent.analyze_page_and_plan_action(
                accessibility_tree=accessibility_tree,
                current_url=page.url,
                navigation_goal="Click on the Discussion tab to access the discussion section",
                page_content_summary="Kaggle competition page with tabs including Discussion"
            )
            
            print(f"   🧠 LLM Action: {action.action_type.value}")
            print(f"   🎯 Target: {action.target_description}")
            print(f"   📊 Confidence: {action.confidence}")
            print(f"   💭 Reasoning: {action.reasoning}")
            
            # Execute LLM action
            if action.confidence >= 0.3:
                llm_result = await action_executor.execute_action(page, action)
                print(f"   ✅ LLM Result: {llm_result.success} - {llm_result.message}")
                
                if llm_result.success:
                    await asyncio.sleep(2)  # Wait for navigation
                    final_url = page.url
                    print(f"   🏁 Final URL: {final_url}")
                    if 'discussion' in final_url:
                        print(f"   🎉 SUCCESS! Successfully navigated to discussion section")
                        return True
            else:
                print(f"   ❌ LLM confidence too low: {action.confidence}")
            
            # Step 4: Manual JavaScript click as last resort
            print(f"\n🔧 MANUAL JAVASCRIPT APPROACH:")
            js_result = await page.evaluate("""
                () => {
                    // Find discussion tab by multiple methods
                    let discussionElement = null;
                    
                    // Method 1: Role-based
                    const tabElements = Array.from(document.querySelectorAll('[role="tab"]'));
                    discussionElement = tabElements.find(el => 
                        el.textContent.toLowerCase().includes('discussion')
                    );
                    
                    // Method 2: Link-based
                    if (!discussionElement) {
                        const linkElements = Array.from(document.querySelectorAll('a'));
                        discussionElement = linkElements.find(el => 
                            el.href && el.href.includes('discussion') && 
                            el.textContent.toLowerCase().includes('discussion')
                        );
                    }
                    
                    if (discussionElement) {
                        // Try to click
                        try {
                            discussionElement.scrollIntoView();
                            discussionElement.click();
                            return {
                                success: true,
                                element: {
                                    tagName: discussionElement.tagName,
                                    text: discussionElement.textContent.trim(),
                                    href: discussionElement.href
                                }
                            };
                        } catch (e) {
                            return {
                                success: false,
                                error: e.message,
                                element: {
                                    tagName: discussionElement.tagName,
                                    text: discussionElement.textContent.trim()
                                }
                            };
                        }
                    } else {
                        return {
                            success: false,
                            error: "No discussion element found"
                        };
                    }
                }
            """)
            
            print(f"   🔧 JS Click Result: {js_result}")
            
            if js_result.get('success'):
                await asyncio.sleep(3)  # Wait for navigation
                final_url = page.url
                print(f"   🏁 Final URL after JS click: {final_url}")
                
                if 'discussion' in final_url:
                    print(f"   🎉 SUCCESS! JavaScript click worked!")
                    
                    # Test discussion page content
                    discussion_content = await page.text_content('body')
                    print(f"   📄 Discussion page loaded with {len(discussion_content)} characters")
                    return True
            
            return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    finally:
        await browser_pool.cleanup()

async def test_click_strategy(page, selector: str) -> Dict[str, Any]:
    """Test a specific click strategy"""
    try:
        print(f"      🎯 Trying selector: {selector}")
        
        # Check if element exists
        element = await page.query_selector(selector)
        if not element:
            print(f"      ❌ Element not found")
            return {"success": False, "reason": "Element not found"}
        
        # Check visibility
        is_visible = await element.is_visible()
        is_enabled = await element.is_enabled()
        
        print(f"      👁️  Visible: {is_visible}, Enabled: {is_enabled}")
        
        if not is_visible or not is_enabled:
            print(f"      ❌ Element not interactive")
            return {"success": False, "reason": "Element not interactive"}
        
        # Try click
        await element.scroll_into_view_if_needed()
        await element.click(timeout=5000)
        
        await asyncio.sleep(2)  # Wait for potential navigation
        
        print(f"      ✅ Click successful")
        return {"success": True, "final_url": page.url}
        
    except Exception as e:
        print(f"      ❌ Click failed: {e}")
        return {"success": False, "reason": str(e)}

async def test_multiple_selectors(page, selectors: List[str]) -> Dict[str, Any]:
    """Test multiple selectors in order"""
    for i, selector in enumerate(selectors, 1):
        print(f"      {i}/{len(selectors)} - {selector}")
        result = await test_click_strategy(page, selector)
        if result["success"]:
            return result
    
    print(f"      ❌ All selectors failed")
    return {"success": False, "reason": "All selectors failed"}

if __name__ == "__main__":
    print("🚀 Starting Targeted Discussion Tab Test...")
    success = asyncio.run(test_discussion_tab_clicking())
    print(f"\n🏁 Test Result: {'SUCCESS' if success else 'FAILED'}")