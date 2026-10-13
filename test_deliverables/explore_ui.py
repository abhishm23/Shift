from playwright.sync_api import sync_playwright
import sys
sys.stdout.reconfigure(encoding='utf-8')

def explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://127.0.0.1:8765', wait_until='networkidle')
        page.locator('input[placeholder*="Select or enter path"]').fill('c:/Shift/test_deliverables/datasets/dataset_04_zero_and_negative_margins.csv')
        page.locator('button:has-text("Preview File")').click()
        page.wait_for_timeout(2000)
        
        page.locator('input[placeholder*="Total Gross List Revenue"]').fill('20053799.04')
        page.locator('input[placeholder*="Total Net Invoiced Revenue"]').fill('14897961.28')
        page.wait_for_timeout(1000)
        
        confirm_btn = page.locator('button:has-text("CONFIRM TOTALS")')
        confirm_btn.click()
        page.wait_for_timeout(3000)
        
        collapse_btn = page.locator('button:has-text("Collapse Guide")')
        if collapse_btn.is_visible():
            collapse_btn.click()
            page.wait_for_timeout(500)
            
        col_sec = page.locator('text=WHAT FACTORS GOVERN DEAL PRICING').locator('xpath=ancestor::div[contains(@class, "rounded") or contains(@class, "border")][1]')
        print("Grouping container inner text on dataset_04:\n", col_sec.inner_text())
        browser.close()

if __name__ == '__main__':
    explore()
