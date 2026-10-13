from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('http://127.0.0.1:8765')
    print("Initial guide button text:")
    btn = pg.locator('button:has-text("Explore Scenarios"), button:has-text("Collapse Guide")').first
    print(btn.inner_text())
    btn.click()
    pg.wait_for_timeout(500)
    print("After clicking, visible buttons:")
    for b_elem in pg.locator('button').all():
        txt = b_elem.inner_text().replace('\n', ' ')
        if len(txt) < 80:
            print(f" - {txt}")
    b.close()
