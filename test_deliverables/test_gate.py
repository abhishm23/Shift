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
    
    number_inputs = page.query_selector_all("input[type='number']")
    # Enter exact sample totals:
    number_inputs[0].fill("31167260.63")
    number_inputs[1].fill("27124792.43")
    
    # Check button text
    btn = page.query_selector("button:has-text('CONFIRM')") or page.query_selector("button:has-text('CERTIFIED')") or page.query_selector("button:has-text('QUARANTINE')")
    print("Reconciliation button text:", btn.inner_text().strip() if btn else "None")
    
    # Check variance display
    variance_div = page.evaluate("""() => {
        const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes('VERIFICATION STATUS'));
        return el ? el.innerText : 'None';
    }""")
    print("Variance text:\n", variance_div[:300])

    browser.close()
