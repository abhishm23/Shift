import time
import psutil
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    preview_btn = page.query_selector("button:has-text('Preview File')")
    
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    preview_btn.click()
    page.wait_for_selector('table', timeout=10000)
    
    # Check all headings and text blocks
    headings = [h.inner_text().strip() for h in page.query_selector_all('h1, h2, h3, h4, h5')]
    print("Headings:", headings)
    
    # Check readiness tiers
    tiers = [t.inner_text().strip() for t in page.query_selector_all('.grid > div')]
    print("Tiers/Cards:", tiers[:6])
    
    # Check table headers and column mapping
    ths = [th.inner_text().strip() for th in page.query_selector_all('table th')]
    print("TH count:", len(ths))
    print("TH values:", ths)
    
    # Check if there are other columns or badges or scroll container
    table_container = page.query_selector('.overflow-x-auto')
    print("Has overflow-x-auto:", bool(table_container))
    
    # Check buttons
    btns = [b.inner_text().strip() for b in page.query_selector_all('button')]
    print("Buttons:", btns)
    
    browser.close()
