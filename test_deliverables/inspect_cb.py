import sys
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
    
    # Check checkbox label
    cb_label = page.evaluate("""() => {
        const cb = document.querySelector('input[type=\"checkbox\"]');
        if (!cb) return 'No checkbox found';
        const parent = cb.closest('label') || cb.parentElement;
        return parent ? parent.innerText : 'No parent label';
    }""")
    print("Checkbox label:\n", cb_label)

    browser.close()
