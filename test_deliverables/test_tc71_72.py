import sys
import time
import psutil
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
server_proc = psutil.Process(24940)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    # TC-071: Wide Schema Header Mapping & Case Insensitivity
    pq_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet'
    page.fill("input[type='text']", pq_path)
    page.click("button:has-text('Preview File')")
    page.wait_for_selector('table', timeout=30000)
    
    headers = [th.inner_text().strip() for th in page.query_selector_all('table th')]
    print("TC-071: Preview table rendered headers count:", len(headers))
    
    # TC-072: Rapid Tab Switching Stress
    rss_before_switch = server_proc.memory_info().rss / (1024*1024)
    t0_switch = time.time()
    for _ in range(5):
        page.click("button:has-text('2. Compare Similar Deals')")
        page.wait_for_timeout(150)
        page.click("button:has-text('3. Discover Profit Opportunities')")
        page.wait_for_timeout(150)
        page.click("button:has-text('1. Add & Check Data')")
        page.wait_for_timeout(150)
        
    t1_switch = time.time()
    rss_after_switch = server_proc.memory_info().rss / (1024*1024)
    print(f"TC-072: Rapid 15x tab switching completed in {t1_switch - t0_switch:.2f}s | RSS: {rss_before_switch:.1f}MB -> {rss_after_switch:.1f}MB | Errors: {len(console_errors)}")
    
    browser.close()
