import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    page.click("button:has-text('3. Discover Profit Opportunities')")
    time.sleep(1)
    
    adv_btn = page.query_selector("button:has-text('Advanced Technical Details')")
    if adv_btn:
        adv_btn.click()
        time.sleep(1)
        
        # print text of elements near adv_btn
        parent_text = page.evaluate("""() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Advanced Technical Details'));
            return btn && btn.parentElement ? btn.parentElement.innerText : 'None';
        }""")
        print("Parent text:\n", parent_text)

    browser.close()
