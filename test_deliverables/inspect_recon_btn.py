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
    
    # Inspect button details
    btn_info = page.evaluate("""() => {
        const btn = document.querySelector('button.w-full') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('QUARANTINE') || b.innerText.includes('CONFIRM'));
        if (!btn) return 'No button found';
        return {
            text: btn.innerText,
            disabled: btn.disabled,
            className: btn.className,
            attributes: Array.from(btn.attributes).map(a => `${a.name}=\"${a.value}\"`).join(' ')
        };
    }""")
    print("Button info:", btn_info)
    
    # Check all inputs and checkboxes on entire page
    all_inputs = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input, select, textarea')).map(el => ({
            type: el.type,
            checked: el.checked,
            disabled: el.disabled,
            value: el.value,
            placeholder: el.placeholder
        }));
    }""")
    print("All inputs on page:", all_inputs)

    browser.close()
