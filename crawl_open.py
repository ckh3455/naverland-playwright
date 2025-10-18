# crawl_open.py — Naver Land 열기(404 복구) + 스샷/HTML 저장
from playwright.sync_api import sync_playwright, TimeoutError as TE
from pathlib import Path
from datetime import datetime
import os

MAP_URL = "https://new.land.naver.com/map"
ART_DIR = Path(".artifacts")  # GitHub Actions 업로드 경로와 동일
ART_DIR.mkdir(exist_ok=True)

LIST_SELECTORS = [
    "[data-testid*=SaleItem]",
    "[data-testid*=List]",
    "div[class*='list'] [role='listitem']",
    "aside [role='listitem']",
]

def is_ci():
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"

def is_404(page) -> bool:
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    body_txt = ""
    try:
        if page.locator("body").count():
            body_txt = page.inner_text("body")
    except Exception:
        body_txt = ""
    mark = "찾을 수 없습니다"
    return (mark in title) or (mark in body_txt)

def wait_any(page, selectors, timeout_ms=20000, poll_ms=500):
    steps = int(timeout_ms / poll_ms)
    for _ in range(steps):
        for sel in selectors:
            try:
                if page.locator(sel).count() > 0:
                    return sel
            except Exception:
                pass
        page.wait_for_timeout(poll_ms)
    return None

with sync_playwright() as p:
    # ── 실행 환경에 따라 브라우저 모드 자동 선택
    if is_ci():
        # GitHub Actions: 일반 컨텍스트(헤디드+xvfb로 실행됨)
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="ko-KR",
            viewport={"width": 1400, "height": 900},
            device_scale_factor=1,
        )
    else:
        # 로컬: 실제 Chrome 채널 + 퍼시스턴트 프로필(사람 브라우저와 유사)
        PROFILE_DIR = r"C:\ChromeDebug\PlaywrightProfile"
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1400, "height": 900},
            device_scale_factor=1,
        )

    # 모든 요청에 Referer 고정(딥링크 404 예방)
    ctx.set_extra_http_headers({"Referer": "https://land.naver.com"})
    page = ctx.new_page()

    # 1) 대문 진입
    page.goto("https://land.naver.com", wait_until="domcontentloaded")

    # 2) 404 복구 루틴
    if is_404(page):
        # 404 화면 내 링크로 복귀 시도
        for sel in ["text=부동산 홈 바로가기", "text=이전페이지", "a[href*='land.naver.com']"]:
            try:
                page.locator(sel).first.click(timeout=1200)
                page.wait_for_load_state("domcontentloaded")
                break
            except Exception:
                pass
        # 그래도 404면 referer 달고 다시 홈으로
        if is_404(page):
            page.goto(
                "https://land.naver.com",
                referer="https://www.naver.com",
                wait_until="domcontentloaded",
            )

    # 3) 내부 클릭으로 지도 진입(실패하면 referer와 함께 맵으로 이동)
    try:
        page.get_by_role("link", name="지도", exact=False).click(timeout=2500)
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        page.goto(MAP_URL, referer="https://land.naver.com", wait_until="domcontentloaded")

    # 4) 지도/레이어 대기(여러 후보)
    first_ok = wait_any(
        page,
        selectors=["canvas", "#map, [id*=map], [class*=map] canvas", "[aria-label*='지도']", "div[class*='map']"],
        timeout_ms=30000,
    )

    # 5) 레이어 로드 유도(줌인 2회)
    if first_ok:
        page.mouse.wheel(0, -700); page.wait_for_timeout(500)
        page.mouse.wheel(0, -700); page.wait_for_timeout(700)

    # 6) 목록 등장 확인(없어도 일단 스샷/HTML 저장)
    listed_sel = wait_any(page, LIST_SELECTORS, timeout_ms=15000)

    # 7) 증거 아티팩트 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    png_path = ART_DIR / f"state_{ts}.png"
    html_path = ART_DIR / f"state_{ts}.html"
    page.screenshot(path=str(png_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")

    print("URL:", page.url)
    print("MAP_READY_SELECTOR:", first_ok)
    print("LIST_READY_SELECTOR:", listed_sel)
    print("PNG:", png_path)
    print("HTML:", html_path)

    # 컨텍스트 정리
    try:
        ctx.close()
    except Exception:
        pass
    try:
        browser.close()  # CI에서만 존재
    except Exception:
        pass
