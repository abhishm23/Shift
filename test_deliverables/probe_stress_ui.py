import time
import psutil
from playwright.sync_api import sync_playwright

server_proc = psutil.Process(24940)
print('Initial Server RSS Memory (MB):', server_proc.memory_info().rss / (1024*1024))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:8765', wait_until='networkidle')
    
    input_path = page.query_selector("input[type='text']")
    preview_btn = page.query_selector("button:has-text('Preview File')")
    print('Found input_path:', bool(input_path), 'preview_btn:', bool(preview_btn))
    
    csv_path = 'c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv'
    input_path.fill(csv_path)
    
    t0 = time.time()
    rss_before = server_proc.memory_info().rss / (1024*1024)
    preview_btn.click()
    
    try:
        page.wait_for_selector('table', timeout=30000)
        t1 = time.time()
        rss_after = server_proc.memory_info().rss / (1024*1024)
        print(f'1M CSV Preview SUCCESS in {t1 - t0:.2f}s! Server RSS: {rss_before:.1f}MB -> {rss_after:.1f}MB')
        
        th_elements = page.query_selector_all('table th')
        print(f'Rendered table header count: {len(th_elements)}')
        if th_elements:
            print('Sample headers:', [th.inner_text().strip().split('\n')[0] for th in th_elements[:10]])
            
        badges = page.query_selector_all('table th span')
        print(f'Total badges in headers: {len(badges)}')
    except Exception as e:
        print('Preview failed or timed out:', e)
        
    browser.close()
