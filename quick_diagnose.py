# quick_diagnose_fixed.py - Fixed version without JavaScript errors
import asyncio
import logging
import json
from pathlib import Path
from config.settings import ScrapingConfig
from core.browser_pool import BrowserPool
from dotenv import load_dotenv

load_dotenv()

async def diagnose_kaggle_issue_fixed():
    """Fixed diagnosis of the Kaggle scraping issue"""
    
    print("🔍 FIXED KAGGLE SCRAPING ISSUE DIAGNOSIS")
    print("=" * 50)
    
    config = ScrapingConfig.from_env()
    browser_pool = BrowserPool(config)
    
    try:
        await browser_pool.initialize()
        
        async with browser_pool.get_page() as page:
            # Test the exact URL that was failing
            url = "https://www.kaggle.com/competitions/openai-to-z-challenge"
            print(f"📍 Testing URL: {url}")
            
            await page.goto(url)
            await browser_pool.wait_for_content_loaded(page)
            
            # Basic page info
            title = await page.title()
            final_url = page.url
            
            print(f"📄 Page Title: {title}")
            print(f"🔗 Final URL: {final_url}")
            
            # Check if we got redirected or blocked
            if final_url != url:
                print(f"⚠️  REDIRECTED! Original: {url}")
                print(f"   Final: {final_url}")
            
            # Check for error messages and login requirements
            page_analysis = await page.evaluate("""
                () => {
                    const pageText = document.body.textContent.toLowerCase();
                    
                    // Check for various indicators
                    const loginIndicators = [
                        'sign in', 'log in', 'login', 'register', 'sign up',
                        'authentication required', 'please log in'
                    ];
                    
                    const errorIndicators = [
                        '404', 'not found', 'error', 'blocked', 'forbidden', 'access denied'
                    ];
                    
                    const competitionIndicators = [
                        'competition', 'overview', 'data', 'discussion', 'leaderboard'
                    ];
                    
                    return {
                        pageTextPreview: pageText.substring(0, 500),
                        loginRequired: loginIndicators.some(indicator => pageText.includes(indicator)),
                        hasErrors: errorIndicators.some(indicator => pageText.includes(indicator)),
                        isCompetitionPage: competitionIndicators.some(indicator => pageText.includes(indicator)),
                        foundLoginIndicators: loginIndicators.filter(indicator => pageText.includes(indicator)),
                        foundErrorIndicators: errorIndicators.filter(indicator => pageText.includes(indicator)),
                        foundCompetitionIndicators: competitionIndicators.filter(indicator => pageText.includes(indicator))
                    };
                }
            """)
            
            print(f"\n🔍 PAGE ANALYSIS:")
            print(f"   🔐 Login Required: {page_analysis['loginRequired']}")
            print(f"   ❌ Has Errors: {page_analysis['hasErrors']}")
            print(f"   🏆 Is Competition Page: {page_analysis['isCompetitionPage']}")
            
            if page_analysis['loginRequired']:
                print(f"   🔑 Login indicators found: {page_analysis['foundLoginIndicators']}")
            
            if page_analysis['hasErrors']:
                print(f"   ⚠️  Error indicators found: {page_analysis['foundErrorIndicators']}")
            
            print(f"   ✅ Competition features found: {page_analysis['foundCompetitionIndicators']}")
            
            print(f"\n📖 Page Content Preview:")
            print(f"   {page_analysis['pageTextPreview'][:200]}...")
            
            # Find ALL clickable elements (fixed version)
            all_clickable = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('a, button, [role="button"], [role="tab"], [onclick]'));
                    return elements
                        .filter(el => el.offsetParent !== null) // visible only
                        .map(el => ({
                            tagName: el.tagName,
                            text: (el.textContent || '').trim().substring(0, 50),
                            href: el.href || '',
                            className: el.className || '',
                            id: el.id || '',
                            role: el.getAttribute('role') || ''
                        }))
                        .filter(el => el.text || el.href)
                        .slice(0, 25); // limit for readability
                }
            """)
            
            print(f"\n🎯 CLICKABLE ELEMENTS FOUND: {len(all_clickable)}")
            if all_clickable:
                for i, el in enumerate(all_clickable[:15], 1):
                    role_info = f" (role: {el['role']})" if el['role'] else ""
                    href_info = f" → {el['href'][:30]}..." if el['href'] else ""
                    print(f"   {i}. {el['tagName']}: '{el['text']}'{role_info}{href_info}")
            else:
                print("   ❌ NO CLICKABLE ELEMENTS FOUND!")
            
            # Specific search for discussion elements (fixed version)
            discussion_search = await page.evaluate("""
                () => {
                    const results = {};
                    
                    // Manual text search for discussion elements
                    const allElements = Array.from(document.querySelectorAll('*'));
                    const discussionElements = allElements.filter(el => {
                        const text = el.textContent?.toLowerCase() || '';
                        return (text.includes('discussion') || text.includes('discuss')) && text.length < 200;
                    }).slice(0, 5).map(el => ({
                        tagName: el.tagName,
                        text: (el.textContent || '').trim().substring(0, 50),
                        className: el.className || ''
                    }));
                    
                    results.textSearch = discussionElements;
                    
                    // Href search for discussion links
                    const hrefElements = Array.from(document.querySelectorAll('a')).filter(a => {
                        return a.href && a.href.toLowerCase().includes('discussion');
                    }).map(el => ({
                        text: (el.textContent || '').trim(),
                        href: el.href
                    }));
                    results.hrefSearch = hrefElements;
                    
                    // Tab elements search
                    const tabElements = Array.from(document.querySelectorAll('[role="tab"]')).map(el => ({
                        text: (el.textContent || '').trim(),
                        role: el.getAttribute('role')
                    }));
                    results.tabSearch = tabElements;
                    
                    // Look for navigation menus that might contain discussion links
                    const navElements = Array.from(document.querySelectorAll('nav a, .nav a, [role="navigation"] a')).filter(a => {
                        const text = a.textContent?.toLowerCase() || '';
                        return text.includes('discuss') || text.includes('comment') || text.includes('forum');
                    }).map(el => ({
                        text: (el.textContent || '').trim(),
                        href: el.href
                    }));
                    results.navSearch = navElements;
                    
                    return results;
                }
            """)
            
            print(f"\n🔎 DISCUSSION ELEMENT SEARCH:")
            
            if discussion_search['textSearch']:
                print(f"   📝 Text-based search found {len(discussion_search['textSearch'])} elements:")
                for el in discussion_search['textSearch']:
                    print(f"      - {el['tagName']}: '{el['text']}'")
            else:
                print(f"   📝 Text-based search: No elements found")
            
            if discussion_search['hrefSearch']:
                print(f"   🔗 Href-based search found {len(discussion_search['hrefSearch'])} elements:")
                for el in discussion_search['hrefSearch']:
                    print(f"      - '{el['text']}' → {el['href']}")
            else:
                print(f"   🔗 Href-based search: No elements found")
            
            if discussion_search['tabSearch']:
                print(f"   📋 Tab-based search found {len(discussion_search['tabSearch'])} elements:")
                for el in discussion_search['tabSearch']:
                    print(f"      - Tab: '{el['text']}'")
            else:
                print(f"   📋 Tab-based search: No tab elements found")
            
            if discussion_search['navSearch']:
                print(f"   🧭 Navigation search found {len(discussion_search['navSearch'])} elements:")
                for el in discussion_search['navSearch']:
                    print(f"      - Nav: '{el['text']}' → {el['href']}")
            else:
                print(f"   🧭 Navigation search: No discussion nav elements found")
            
            # Check if we can see the page structure at all
            page_structure = await page.evaluate("""
                () => {
                    return {
                        hasNav: !!document.querySelector('nav'),
                        hasMain: !!document.querySelector('main'),
                        hasHeader: !!document.querySelector('header'),
                        navElements: Array.from(document.querySelectorAll('nav')).length,
                        totalLinks: Array.from(document.querySelectorAll('a')).length,
                        totalButtons: Array.from(document.querySelectorAll('button')).length,
                        bodyText: document.body.textContent.length
                    };
                }
            """)
            
            print(f"\n🏗️ PAGE STRUCTURE:")
            for key, value in page_structure.items():
                print(f"   {key}: {value}")
            
            # Final diagnosis and recommendations
            print(f"\n💡 DIAGNOSIS SUMMARY:")
            
            if page_analysis['loginRequired']:
                print("   🔐 PRIMARY ISSUE: Authentication/Login Required")
                print("   🔧 SOLUTION: Need to implement Kaggle login or use competitions that don't require login")
                print("   📝 DETAILS: The page shows login prompts, indicating restricted access")
            
            elif not page_analysis['isCompetitionPage']:
                print("   ❌ This doesn't appear to be a valid competition page")
                print("   🔧 Try a different competition URL")
            
            elif not all_clickable:
                print("   ⚠️  No clickable elements found - possible JavaScript loading issue")
                print("   🔧 Increase wait times or check for dynamic content loading")
            
            elif not any([discussion_search['textSearch'], discussion_search['hrefSearch'], discussion_search['tabSearch']]):
                print("   📝 No discussion section found - may be hidden behind login")
                print("   🔧 Try logging in first or use a different competition")
            
            else:
                print("   ✅ Page loaded successfully with content")
                print("   🔧 Discussion elements may be present but hidden behind authentication")
            
            # Specific recommendations
            print(f"\n🎯 RECOMMENDED NEXT STEPS:")
            print("   1. 🔓 Use the public competitions that work (Titanic, House Prices, etc.)")
            print("   2. 🔐 Implement Kaggle authentication if you need this specific competition")
            print("   3. 🧪 Test with the working URLs found in the alternative competitions test")
            print("   4. 📊 Use the debug screenshots to visually confirm what the scraper sees")
            
            return {
                'url': final_url,
                'title': title,
                'redirected': final_url != url,
                'page_analysis': page_analysis,
                'clickable_count': len(all_clickable),
                'discussion_search': discussion_search,
                'page_structure': page_structure
            }
            
    except Exception as e:
        print(f"❌ DIAGNOSIS FAILED: {e}")
        return {'error': str(e)}
    
    finally:
        await browser_pool.cleanup()


if __name__ == "__main__":
    print("🚀 Starting FIXED Kaggle Scraping Diagnosis...")
    
    # Run fixed diagnosis
    result = asyncio.run(diagnose_kaggle_issue_fixed())
    
    # Save results
    output_dir = Path("debug_output")
    output_dir.mkdir(exist_ok=True)
    
    result_file = output_dir / "fixed_diagnosis_result.json"
    result_file.write_text(json.dumps(result, indent=2, default=str))
    
    print(f"\n💾 Fixed diagnosis results saved to: {result_file}")
    print(f"\n🏁 FIXED DIAGNOSIS COMPLETE!")