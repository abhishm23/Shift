import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path = page.query_selector("input[type='text']")
    input_path.fill(csv_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=30000)
    
    number_inputs = page.query_selector_all("input[type='number']")
    number_inputs[0].fill("31643595200.00")
    number_inputs[1].fill("27842500000.00")
    
    page.click("input[type='checkbox']")
    time.sleep(1)
    
    t0 = time.time()
    with page.expect_response("**/api/ingest/reconcile", timeout=60000) as resp_info:
        page.click("button:has-text('QUARANTINE DISCREPANCIES')")
    
    elapsed = time.time() - t0
    resp = resp_info.value
    print(f"1M CSV Pass 2 Ingest & Reconcile elapsed: {elapsed:.2f}s | Status: {resp.status}")
    print("Response JSON:", resp.text()[:500])

    browser.close()
