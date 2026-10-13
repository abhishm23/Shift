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
    
    number_inputs = page.query_selector_all("input[type='number']")
    number_inputs[0].fill("31167260.63")
    number_inputs[1].fill("27124792.43")
    
    btn = page.query_selector("button:has-text('CONFIRM TOTALS')")
    print("Found confirm button:", bool(btn))
    if btn:
        btn.click()
        time.sleep(2)
        
    print("Active step/headings after clicking confirm:")
    headings = [h.inner_text().strip() for h in page.query_selector_all('h1, h2, h3, h4')]
    print(headings)
    
    # Check current active tab
    active_tab = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('nav button, header button, .flex button'));
        return btns.map(b => ({ text: b.innerText.split('\\n')[0], class: b.className }));
    }""")
    print("Tabs/buttons:", active_tab[:5])
    
    # Check body text snippet
    body_text = page.inner_text('main') if page.query_selector('main') else page.inner_text('body')
    print("Body snippet:\n", body_text[:600])

    browser.close()
