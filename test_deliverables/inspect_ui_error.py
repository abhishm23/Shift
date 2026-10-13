import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
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
    
    with page.expect_response("**/api/ingest/reconcile", timeout=60000):
        page.click("button:has-text('QUARANTINE DISCREPANCIES')")
    
    time.sleep(2)
    
    # Check for alert, toast, or error message in UI
    error_alerts = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.text-rose-400, .bg-rose-950, .border-rose-800, [role=\"alert\"], .text-red-500, .bg-red-900')).map(e => e.innerText);
    }""")
    print("Error alerts in UI:", error_alerts)
    
    # Check what button says now
    btn = page.query_selector("button:has-text('QUARANTINE')") or page.query_selector("button:has-text('Failed')")
    print("Button text now:", btn.inner_text().strip() if btn else "None")

    browser.close()
