import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    page.click("button:has-text('3. Discover Profit Opportunities')")
    
    btns = page.query_selector_all('button')
    for b in btns:
        t = b.inner_text().strip()
        if 'Detail' in t or 'Adv' in t:
            print(f"Button: '{t}'")
    browser.close()
