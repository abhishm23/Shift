import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
    reqs = []
    page.on("request", lambda r: reqs.append((r.method, r.url, r.post_data)))
    
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    pq_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet'
    input_path = page.query_selector("input[type='text']")
    input_path.fill(pq_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=30000)
    
    number_inputs = page.query_selector_all("input[type='number']")
    number_inputs[0].fill("474653928000.00")
    number_inputs[1].fill("417637500000.00")
    
    page.click("input[type='checkbox']")
    time.sleep(1)
    
    reqs.clear()
    page.click("button:has-text('QUARANTINE DISCREPANCIES')")
    time.sleep(3)
    
    print("Requests sent on clicking QUARANTINE:")
    for r in reqs:
        print("  ", r[0], r[1], r[2][:100] if r[2] else '')

    browser.close()
