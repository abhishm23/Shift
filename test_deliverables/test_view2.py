import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=10000)
    
    # Click tab 2: Compare Similar Deals
    tab2 = page.query_selector("button:has-text('2. Compare Similar Deals')")
    print("Found tab 2:", bool(tab2))
    tab2.click()
    time.sleep(1)
    
    headings = [h.inner_text().strip() for h in page.query_selector_all('h1, h2, h3, h4')]
    print("Headings in View 2:", headings)
    
    # Check sections in View 2
    body = page.inner_text('main') if page.query_selector('main') else page.inner_text('body')
    print("View 2 body snippet:\n", body[body.find('Step 2') if 'Step 2' in body else 0 : body.find('Step 2') + 1200 if 'Step 2' in body else 1200])

    browser.close()
