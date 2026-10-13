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
    
    # Check checkbox
    cb = page.query_selector("input[type='checkbox']")
    cb.check()
    time.sleep(1)
    
    # Check button state now
    btn = page.query_selector("button:has-text('QUARANTINE DISCREPANCIES')")
    print("Button disabled after check?", btn.is_disabled())
    print("Button text:", btn.inner_text().strip())
    
    # Click button
    btn.click()
    time.sleep(2)
    
    # Check for quarantine banner/watermark on screen
    watermark = page.evaluate("""() => {
        const els = Array.from(document.querySelectorAll('*')).filter(e => e.innerText && e.innerText.includes('UNRECONCILED RESIDUAL'));
        return els.map(e => e.innerText);
    }""")
    print("Quarantine watermark elements:", watermark[:3])
    
    # Check if navigation to View 2 and View 3 preserves watermark
    page.click("button:has-text('2. Compare Similar Deals')")
    time.sleep(1)
    v2_watermark = page.evaluate("""() => {
        const els = Array.from(document.querySelectorAll('*')).filter(e => e.innerText && e.innerText.includes('UNRECONCILED RESIDUAL'));
        return els.map(e => e.innerText);
    }""")
    print("View 2 watermark:", bool(v2_watermark))
    
    page.click("button:has-text('3. Discover Profit Opportunities')")
    time.sleep(1)
    v3_watermark = page.evaluate("""() => {
        const els = Array.from(document.querySelectorAll('*')).filter(e => e.innerText && e.innerText.includes('UNRECONCILED RESIDUAL'));
        return els.map(e => e.innerText);
    }""")
    print("View 3 watermark:", bool(v3_watermark))

    browser.close()
