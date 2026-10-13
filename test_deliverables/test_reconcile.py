import time
import psutil
from playwright.sync_api import sync_playwright

server_proc = psutil.Process(24940)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=10000)
    
    # Enter control totals:
    # 1M CSV Total Gross List = 31,643,595,200.00, Net Invoiced = 27,842,500,000.00
    number_inputs = page.query_selector_all("input[type='number']")
    print("Found number inputs:", len(number_inputs))
    number_inputs[0].fill("31643595200.00")
    number_inputs[1].fill("27842500000.00")
    
    # Inspect buttons after entering numbers
    time.sleep(1)
    btns = [b.inner_text().strip() for b in page.query_selector_all('button')]
    print("Buttons after entering totals:", btns)
    
    # Find reconciliation button
    reconcile_btn = None
    for b in page.query_selector_all('button'):
        txt = b.inner_text().strip()
        if 'RECONCIL' in txt.upper() or 'AUDIT' in txt.upper() or 'CHECK' in txt.upper() or 'CONFIRM' in txt.upper():
            if 'PREVIEW' not in txt.upper() and 'SCENARIO' not in txt.upper() and 'STEP' not in txt.upper():
                reconcile_btn = b
                print("Found candidate reconcile button:", txt)
                break
                
    if reconcile_btn:
        t0 = time.time()
        rss_before = server_proc.memory_info().rss / (1024*1024)
        reconcile_btn.click()
        print("Clicked button! Waiting for response...")
        time.sleep(5)
        rss_after = server_proc.memory_info().rss / (1024*1024)
        print(f"Elapsed: {time.time() - t0:.2f}s, RSS: {rss_before:.1f}MB -> {rss_after:.1f}MB")
        
        # Check verification status text
        status_text = page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText && e.innerText.includes('VERIFICATION STATUS'));
            return el ? el.innerText : 'Not found';
        }""")
        print("Status text:\n", status_text[:400])
    
    browser.close()
