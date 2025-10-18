# crawl_open.py — 홈 열기 → 지도 진입 → 리스트 감지 → 404/상태 DIAG + 스샷/HTML
from playwright.sync_api import sync_playwright
from pathlib import Path

ART_DIR = Path(".artifacts")
ART_DIR.mkdir(exist_ok=True)

LIST_SELECTORS = [
    "[data-testid*=SaleItem]",
    "[data-testid*=List]",
    "div[class*='list'] [role='listitem']",
    "aside [role='listitem']",
]

def has_404(page) -> bool:
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    body = ""
    try:
        if page.locator("body").count():
            body = page.inner_text("body")
    except Exception:
        body = ""
    return ("찾을 수 없습니다" in title) or ("찾을 수 없습니다" in body)

def wait_any(page, selectors, timeout_ms=12000, poll_ms=400):
    steps = int(timeout_ms / poll_ms)
    for _ in range(steps):
        for s in selectors:
            try:
                if page.locator(s).count() > 0:
                    return s
            except:
                pass
        page.wait_for_timeout(poll_ms)
    return None

def save_artifacts(page):
    png = ART_DIR / "state.png"
    html = ART_DIR / "state.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    print(f"PNG: {png}")
    print(f"HTML: {html}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Actions는 xvfb로 감싸서 실행
    ctx = browser.new_context(
        locale="ko-KR",
        viewport={"width": 1400, "height": 900},
        device_scale_factor=1,
    )
    # 딥링크 404 예방
    ctx.set_extra_http_headers({"Referer": "https://land.naver.com"})
    page = ctx.new_page()

    # 1) 홈
    page.goto("https://land.naver.com", wait_until="domcontentloaded")
    if has_404(page):
        print("DIAG: FOUND_404_AT_HOME")
        # 간단 복구
        recovered = False
        for sel in ["text=부동산 홈 바로가기", "text=이전페이지", "a[href*='land.naver.com']"]:
            try:
                page.locator(sel).first.click(timeout=1200)
                page.wait_for_load_state("domcontentloaded")
                if not has_404(page):
                    recovered = True
                    print("DIAG: RECOVERED_VIA_LINK")
                    break
            except Exception:
                pass
        if not recovered:
            page.goto("https://land.naver.com",
                      referer="https://www.naver.com", wait_until="domcontentloaded")
            print("DIAG: RETRY_WITH_REFERER")
    else:
        print("DIAG: NO_404_AT_HOME")

    # 2) 지도 진입 (내부 클릭 우선, 실패 시 referer 달고 맵 URL)
    try:
        page.get_by_role("link", name="지도", exact=False).click(timeout=2500)
        page.wait_for_load_state("domcontentloaded")
        print("DIAG: MAP_VIA_MENU")
    except Exception:
        page.goto("https://new.land.naver.com/map",
                  referer="https://land.naver.com", wait_until="domcontentloaded")
        print("DIAG: MAP_VIA_DIRECT_REFERER")

    # 3) 지도 레이어 후보 대기 + 가벼운 줌으로 로드 유도
    map_ready = wait_any(
        page,
        selectors=["canvas", "#map, [id*=map], [class*=map] canvas",
                   "[aria-label*='지도']", "div[class*='map']"],
        timeout_ms=15000
    )
    print("DIAG: MAP_READY_SELECTOR:", map_ready)
    if map_ready:
        page.mouse.wheel(0, -600); page.wait_for_timeout(400)
        page.mouse.wheel(0, -600); page.wait_for_timeout(600)

    # 4) 리스트 감지 (있으면 OK)
    list_ready = wait_any(page, LIST_SELECTORS, timeout_ms=8000)
    print("DIAG: LIST_READY_SELECTOR:", list_ready)

    # 5) 아티팩트 저장 + 최종 요약
    save_artifacts(page)
    print("FINAL_URL:", page.url)
    print("RESULT:",
          "OK_LIST" if list_ready else
          ("OK_NO_LIST" if not has_404(page) else "STILL_404"))

    ctx.close(); browser.close()
