# test_enhanced_executor.py - Specific test for the enhanced action executor
import asyncio
import logging
from typing import Dict, Any
from config.settings import ScrapingConfig
from core.browser_pool import BrowserPool
from core.llm_agent import LLMNavigationAgent, NavigationAction, ActionType
from core.action_executor import EnhancedActionExecutor
from dotenv import load_dotenv

load_dotenv()

async def test_enhanced_executor_on_kaggle():
    """Test the enhanced action executor specifically on Kaggle discussion navigation"""
    
    print("🧪 TESTING ENHANCED ACTION EXECUTOR")
    print("=" * 50)
    
    config = ScrapingConfig.from_env()
    browser_pool = BrowserPool(config)
    enhanced_executor = EnhancedActionExecutor(config)
    llm_agent = LLMNavigationAgent(config)
    
    try:
        await browser_pool.initialize()
        
        async with browser_pool.get_page() as page:
            url = "https://www.kaggle.com/competitions/openai-to-z-challenge"
            print(f"📍 Loading: {url}")
            
            await page.goto(url)
            await browser_pool.wait_for_content_loaded(page)
            
            print(f"✅ Page loaded: {await page.title()}")
            
            # Test 1: LLM Action Generation
            print(f"\n🧠 Test 1: LLM Action Generation")
            accessibility_tree = await browser_pool.get_accessibility_tree(page)
            
            action = await llm_agent.analyze_page_and_plan_action(
                accessibility_tree=accessibility_tree,
                current_url=page.url,
                navigation_goal="Click on the Discussion tab to access the discussion section",
                page_content_summary="Kaggle competition page with navigation tabs"
            )
            
            print(f"   LLM Action: {action.action_type.value}")
            print(f"   Target: {action.target_description}")
            print(f"   Confidence: {action.confidence:.2f}")
            print(f"   Reasoning: {action.reasoning}")
            
            # Test 2: Enhanced Executor - Semantic Selector Generation
            print(f"\n🔧 Test 2: Enhanced Semantic Selector Generation")
            
            # Create a test action that mimics the LLM output
            test_action = NavigationAction(
                action_type=ActionType.CLICK,
                target_description="Discussions link in the main navigation",
                parameters={},
                confidence=0.95,
                reasoning="Test action for enhanced executor"
            )
            
            print(f"   Testing enhanced executor with: '{test_action.target_description}'")
            
            # Execute with enhanced executor
            result = await enhanced_executor.execute_action(page, test_action)
            
            print(f"   🎯 Execution Result: {result.success}")
            print(f"   📝 Message: {result.message}")
            
            if result.data:
                print(f"   📊 Execution Data:")
                if 'strategy' in result.data:
                    print(f"      Strategy used: {result.data['strategy']}")
                    print(f"      Selector used: {result.data['selector']}")
                    print(f"      Confidence: {result.data.get('confidence', 'N/A')}")
                
                if 'element_info' in result.data:
                    print(f"      Element info: {result.data['element_info']}")
                
                if 'strategies_tried' in result.data:
                    print(f"      Total strategies tried: {result.data['strategies_tried']}")
                    print(f"      Strategy details:")
                    for i, strategy in enumerate(result.data.get('strategies', [])[:3], 1):
                        print(f"         {i}. {strategy['category']}: {strategy['selector'][:50]}...")
            
            # Test 3: Verify Navigation Success
            if result.success:
                print(f"\n✅ Test 3: Verifying Navigation Success")
                await asyncio.sleep(3)  # Wait for navigation
                
                final_url = page.url
                final_title = await page.title()
                
                print(f"   Final URL: {final_url}")
                print(f"   Final Title: {final_title}")
                
                if 'discussion' in final_url.lower():
                    print(f"   🎉 SUCCESS! Successfully navigated to discussion section")
                    
                    # Extract some discussion content
                    discussion_content = await page.text_content('body')
                    print(f"   📄 Discussion page content length: {len(discussion_content)} characters")
                    
                    # Look for discussion-specific elements
                    discussion_elements = await page.evaluate("""
                        () => {
                            const hasNewButton = Array.from(document.querySelectorAll('button'))
                                .some(el => el.textContent.trim().includes('New'));
                            const hasNewDataTestId = !!document.querySelector('[data-testid*="new"]');
                            const elements = {
                                discussion_threads: document.querySelectorAll('[data-testid*="discussion"], .discussion, .thread').length,
                                post_elements: document.querySelectorAll('.post, .comment, [data-testid*="post"]').length,
                                new_discussion_button: hasNewButton || hasNewDataTestId,
                                has_discussion_content: document.body.textContent.toLowerCase().includes('discussion')
                            };
                            return elements;
                        }
                    """) 
                    print(f"   📋 Discussion page analysis:")
                    for key, value in discussion_elements.items():
                        print(f"      {key}: {value}")
                    
                    return True
                else:
                    print(f"   ⚠️ Navigation occurred but not to discussion section")
                    print(f"   Expected: URL containing 'discussion'")
                    print(f"   Actual: {final_url}")
                    return False
            else:
                print(f"\n❌ Test 3: Navigation Failed")
                print(f"   The enhanced executor could not click the discussion element")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await browser_pool.cleanup()

async def test_semantic_parsing():
    """Test the semantic parsing component independently"""
    
    print(f"\n🔬 TESTING SEMANTIC PARSING COMPONENT")
    print("=" * 50)
    
    config = ScrapingConfig.from_env()
    enhanced_executor = EnhancedActionExecutor(config)
    
    test_descriptions = [
        "Discussions link in the main navigation",
        "Login button in header",
        "Submit form button",
        "Search input field",
        "Discussion tab in navigation menu",
        "Next page button at bottom"
    ]
    
    for i, description in enumerate(test_descriptions, 1):
        print(f"\n   Test {i}: '{description}'")
        try:
            parsed = await enhanced_executor._parse_description_with_llm(description)
            print(f"      Target text: {parsed.get('target_text', 'N/A')}")
            print(f"      Element type: {parsed.get('element_type', 'N/A')}")
            print(f"      Context area: {parsed.get('context_area', 'N/A')}")
            print(f"      Modifiers: {parsed.get('modifiers', [])}")
            
            # Test selector generation from parsed components
            strategies = enhanced_executor._generate_selectors_from_components(parsed)
            print(f"      Generated {len(strategies)} strategies:")
            for j, strategy in enumerate(strategies[:3], 1):  # Show top 3
                print(f"         {j}. {strategy.category}: {strategy.selector} (conf: {strategy.confidence:.2f})")
                
        except Exception as e:
            print(f"      ❌ Parsing failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Enhanced Action Executor Test...")
    
    # Test the enhanced executor
    success = asyncio.run(test_enhanced_executor_on_kaggle())
    
    # Test semantic parsing independently
    asyncio.run(test_semantic_parsing())
    
    print(f"\n🏁 Enhanced Executor Test Result: {'SUCCESS' if success else 'FAILED'}")
    print(f"The enhanced action executor {'should now work' if success else 'needs further debugging'}")