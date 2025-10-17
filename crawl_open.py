# crawl_open.py (robust wait + rich logs)
from playwright.sync_api import sync_playwright, TimeoutError as TE
from pathlib import Path

MAP_URL = "https://new.land.naver.com/map"

LIST_SELECTORS = [
    "[data-testid*=SaleItem]",
    "[data-testid*=List]",
    "div[class*='list'] [role='listitem']",
    "aside [role='listitem']",
]

def wait_any(page, selectors, timeout_ms=20000, poll_ms=500):
    """selectors 중 하나라도 나타나면 True"""
    steps = int(timeout_ms / poll_ms)
    for _ in range(steps):
        for sel in selectors:
            try:
                if page.locator(sel).count() > 0:
                    return sel
            except:
                pass
        page.wait_for_timeout(poll_ms)
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Actions에서는 xvfb로 감싸 실행
    ctx = browser.new_context(
        locale="ko-KR",
        viewport={"width": 1400, "height": 900},
        device_scale_factor=1,
    )
    # 딥링크 NotFound 예방: 모든 요청에 Referer 부여
    ctx.set_extra_http_headers({"Referer": "https://land.naver.com"})
    page = ctx.new_page()

    # 1) 대문 → 내부 이동(안 되면 referer 달고 맵으로)
    page.goto("https://land.naver.com", wait_until="domcontentloaded")
    try:
        page.get_by_role("link", name="지도", exact=False).click(timeout=2500)
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        page.goto(MAP_URL, referer="https://land.naver.com", wait_until="domcontentloaded")

    # 2) 지도/레이어 대기(여러 후보)
    #    - 일부 환경에서는 초기에 canvas가 늦게 붙거나 가려질 수 있음
    first_ok = wait_any(
        page,
        selectors=[
            "canvas",
            "#map, [id*=map], [class*=map] canvas",
            "[aria-label*='지도']",
            "div[class*='map']",
        ],
        timeout_ms=30000,
    )

    # 3) 레이어 로드 유도(줌인 2회 + 잠깐 대기)
    if first_ok:
        page.mouse.wheel(0, -700); page.wait_for_timeout(500)
        page.mouse.wheel(0, -700); page.wait_for_timeout(700)

    # 4) 리스트 등장 확인(없어도 일단 성공으로 간주하고 스샷 저장)
    listed_sel = wait_any(page, LIST_SELECTORS, timeout_ms=15000)

    # 5) 아티팩트 남기기(성공/실패 모두)
    Path(".artifacts").mkdir(exist_ok=True)
    page.screenshot(path=".artifacts/state.png", full_page=True)
    html = page.content()
    Path(".artifacts/state.html").write_text(html, encoding="utf-8")

    print("URL:", page.url)
    print("MAP_READY_SELECTOR:", first_ok)
    print("LIST_READY_SELECTOR:", listed_sel)

    ctx.close(); browser.close()
