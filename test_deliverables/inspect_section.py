from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    preview_btn = page.query_selector("button:has-text('Preview File')")
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    preview_btn.click()
    page.wait_for_selector('table', timeout=10000)
    
    # Check text around "SALES DATA PREVIEW & COLUMN ALIGNMENT"
    section = page.evaluate("""() => {
        const el = Array.from(document.querySelectorAll('h3')).find(e => e.innerText.includes('SALES DATA PREVIEW'));
        return el ? el.parentElement.innerText : null;
    }""")
    print("Preview section text:\n", section[:1000] if section else "None")
    
    # Check if there are any chips, spans, or badges outside the table
    badges = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('span')).map(s => s.innerText.trim()).filter(t => t.length > 0 && t.length < 50);
    }""")
    print("Unique short spans:", set(badges))
    
    browser.close()
