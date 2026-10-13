import sys
import time
import psutil
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
server_proc = psutil.Process(24940)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
    net_logs = []
    page.on("request", lambda req: net_logs.append(f"REQ {req.method} {req.url}"))
    page.on("response", lambda resp: net_logs.append(f"RESP {resp.status} {resp.url}"))
    page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
    
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    # Upload 1M CSV
    input_path = page.query_selector("input[type='text']")
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=10000)
    
    # Navigate to View 3
    page.click("button:has-text('3. Discover Profit Opportunities')")
    time.sleep(1)
    
    # Click scan button
    scan_btn = page.query_selector("button:has-text('Scan for High-Priority Profit Leaks')")
    print("Found scan button:", bool(scan_btn))
    
    t0 = time.time()
    rss_before = server_proc.memory_info().rss / (1024*1024)
    scan_btn.click()
    print("Clicked scan button! Waiting...")
    
    time.sleep(5)
    t1 = time.time()
    rss_after = server_proc.memory_info().rss / (1024*1024)
    print(f"Elapsed: {t1-t0:.2f}s, RSS: {rss_before:.1f}MB -> {rss_after:.1f}MB")
    
    print("Network logs during scan:")
    for log in net_logs[-10:]:
        print("  ", log)
        
    # Check if table or message changed
    body = page.inner_text('main') if page.query_selector('main') else page.inner_text('body')
    print("Body snippet after scan:\n", body[body.find('Step 3') if 'Step 3' in body else 0 : body.find('Step 3') + 1200 if 'Step 3' in body else 1200])

    browser.close()
