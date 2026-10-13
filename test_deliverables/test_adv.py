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
    print("Found adv_btn:", bool(adv_btn))
    if adv_btn:
        adv_btn.click()
        time.sleep(1)
        
        # Check inputs or selects inside advanced details
        inputs = [(inp.get_attribute('placeholder'), inp.get_attribute('name'), inp.get_attribute('type')) for inp in page.query_selector_all('input, select, textarea')]
        print("Inputs in adv details:", inputs)
        
        body = page.inner_text('main') if page.query_selector('main') else page.inner_text('body')
        print("Body snippet:\n", body[body.find('Advanced') : body.find('Advanced') + 800])

    browser.close()
