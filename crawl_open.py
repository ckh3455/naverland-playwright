from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(locale="ko-KR", viewport={"width":1400,"height":900})
    ctx.set_extra_http_headers({"Referer":"https://land.naver.com"})
    page = ctx.new_page()
    page.goto("https://land.naver.com", wait_until="domcontentloaded")
    try:
        page.get_by_role("link", name="지도", exact=False).click(timeout=2000)
    except Exception:
        page.goto("https://new.land.naver.com/map", referer="https://land.naver.com", wait_until="domcontentloaded")
    page.wait_for_selector("canvas", timeout=15000)
    page.mouse.wheel(0,-600); page.wait_for_timeout(400)
    page.mouse.wheel(0,-600); page.wait_for_timeout(400)
    page.screenshot(path="state.png", full_page=True)
    ctx.close(); browser.close()
