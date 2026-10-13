import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('http://127.0.0.1:8765')
    path_4gb = 'c:/Shift/test_deliverables/datasets/dataset_stress_4gb_plus_wide.csv'
    pg.locator('input[placeholder*="Select or enter path"]').fill(path_4gb)
    t0 = time.time()
    pg.locator('button:has-text("Preview File")').click()
    print("Clicked Preview File, waiting for table rows...")
    pg.wait_for_selector('table tbody tr', timeout=30000)
    dt = time.time() - t0
    rows = pg.locator('table tbody tr').count()
    print(f"SUCCESS: Preview rendered in {dt:.2f}s with {rows} rows!")
    b.close()
