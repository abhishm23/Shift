import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765')
    page.wait_for_selector('input[placeholder*="Select or enter path"]')
    
    # 1. Dataset 1
    page.fill('input[placeholder*="Select or enter path"]', 'c:/Shift/test_deliverables/datasets/dataset_01_single_category_leakage.csv')
    page.click('button:has-text("Preview File")')
    print('Clicked preview 1...')
    page.wait_for_selector('button:has-text("Preview File")', timeout=10000)
    print('Button back to Preview File after d01')
    
    # 2. Dataset 5
    page.fill('input[placeholder*="Select or enter path"]', 'c:/Shift/test_deliverables/datasets/dataset_05_missing_null_columns.csv')
    btn_before_click = page.locator('button:has-text("Preview File"), button:has-text("Scanning...")').inner_text()
    print('Button before click 2:', repr(btn_before_click))
    page.click('button:has-text("Preview File")')
    print('Clicked preview 2...')
    time.sleep(1)
    btn_during = page.locator('button:has-text("Preview File"), button:has-text("Scanning...")').inner_text()
    print('Button during 2:', repr(btn_during))
    page.wait_for_selector('button:has-text("Preview File")', timeout=10000)
    print('Button back to Preview File after d05')
    
    # 3. Dataset 1 again
    page.fill('input[placeholder*="Select or enter path"]', 'c:/Shift/test_deliverables/datasets/dataset_01_single_category_leakage.csv')
    btn_3 = page.locator('button:has-text("Preview File"), button:has-text("Scanning...")').inner_text()
    print('Button before click 3:', repr(btn_3))
    page.click('button:has-text("Preview File")')
    print('Clicked preview 3...')
    page.wait_for_selector('button:has-text("Preview File")', timeout=10000)
    print('Button back to Preview File after d01 again')
    browser.close()
