from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765')
    page.wait_for_selector('input[placeholder*="Select or enter path"]')
    
    page.fill('input[placeholder*="Select or enter path"]', 'c:/Shift/test_deliverables/datasets/dataset_01_single_category_leakage.csv')
    page.click('button:has-text("Preview File")')
    page.wait_for_timeout(2500)
    
    t1_card = page.locator('div:has(> div > div:text("Tier 1: Price Realization"))').first
    print('Initial T1 text:', repr(t1_card.inner_text()))
    
    dropdowns = page.locator('.column-mapping select')
    print('Line ID dropdown orig value:', repr(dropdowns.nth(0).input_value()))
    
    dropdowns.nth(0).select_option('')
    page.wait_for_timeout(500)
    print('Line ID dropdown after unmap:', repr(dropdowns.nth(0).input_value()))
    print('T1 text after unmap:', repr(t1_card.inner_text()))
    browser.close()
