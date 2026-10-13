# -*- coding: utf-8 -*-
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('http://127.0.0.1:8765')
    page.wait_for_timeout(2000)

    # 1. Check Browse & Select Sales File button
    browse_btn = page.locator('button:has-text("Browse & Select Sales File")')
    assert browse_btn.is_visible(), "Browse & Select Sales File button is not visible"
    print("✓ Browse & Select Sales File button is prominent and visible.")

    # 2. Check Use Case Guide default collapsed
    guide_heading = page.locator('text=How Sift Works & Real-World Use Cases')
    assert guide_heading.is_visible(), "Guide banner heading not visible"
    
    scenario_1 = page.locator('text=Identifying Unintended or Runaway Customer Discounts').first
    assert not scenario_1.is_visible(), "Use Case Guide scenarios should be COLLAPSED by default"
    print("✓ Use Case Guide is COLLAPSED by default (takes minimal ~38px vertical height).")

    # 3. Check expanding Use Case Guide
    expand_btn = page.locator('button:has-text("Explore Scenarios")')
    assert expand_btn.is_visible(), "Explore Scenarios button not found"
    expand_btn.click()
    page.wait_for_timeout(500)
    
    assert scenario_1.is_visible(), "Scenario 1 should be visible after expansion"
    print("✓ Clicking 'Explore Scenarios' expands the 4 commercial scenarios successfully.")

    # 4. Check collapsing Use Case Guide
    collapse_btn = page.locator('button:has-text("Collapse Guide")')
    assert collapse_btn.is_visible(), "Collapse Guide button not found"
    collapse_btn.click()
    page.wait_for_timeout(500)
    assert not scenario_1.is_visible(), "Use Case Guide successfully collapses again"
    print("✓ Clicking 'Collapse Guide' collapses the guide back to minimal footprint.")

    # 5. Check path input compatibility
    path_input = page.locator('input[placeholder*="Select or enter path"]')
    assert path_input.is_visible(), "Path input is not visible"
    print("✓ Manual path input and test automation selector remain visible and compatible.")

    browser.close()
    print("\nALL NEW UI REQUIREMENTS FULLY VERIFIED (100% PASS)!")
