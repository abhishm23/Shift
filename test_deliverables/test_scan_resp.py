import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
    responses = {}
    page.on("response", lambda resp: responses.update({resp.url: (resp.status, resp.text() if 'api' in resp.url else '')}))
    
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=10000)
    
    page.click("button:has-text('3. Discover Profit Opportunities')")
    time.sleep(1)
    
    scan_btn = page.query_selector("button:has-text('Scan for High-Priority Profit Leaks')")
    scan_btn.click()
    time.sleep(5)
    
    for url, (status, body) in responses.items():
        if 'beam-search' in url:
            print(f"URL: {url}, Status: {status}")
            print(f"Body: {body[:500]}")

    browser.close()
