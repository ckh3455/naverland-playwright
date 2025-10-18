# crawl_open.py — 최소 확인: 네이버부동산 열기 + 404 진단 + 스샷/HTML 저장
from playwright.sync_api import sync_playwright
from pathlib import Path
import os

ART_DIR = Path(".artifacts")
ART_DIR.mkdir(exist_ok=True)

def has_404(page) -> bool:
    try:
        title = (page.title() or "")
    except Exception:
        title = ""
    body = ""
    try:
        if page.locator("body").count():
            body = page.inner_text("body")
    except Exception:
        body = ""
    mark = "찾을 수 없습니다"
    return (mark in title) or (mark in body)

def save_artifacts(page):
    png = ART_DIR / "state.png"
    html = ART_DIR / "state.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    print(f"PNG: {png}")
    print(f"HTML: {html}")

def main():
    with sync_playwright() as p:
        # CI(깃허브 액션)에서는 xvfb로 둘러서 headed 실행
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="ko-KR",
            viewport={"width": 1400, "height": 900},
            device_scale_factor=1,
        )
        # 딥링크 404 예방: Referer 고정
        ctx.set_extra_http_headers({"Referer": "https://land.naver.com"})
        page = ctx.new_page()

        # 1) 홈 진입
        page.goto("https://land.naver.com", wait_until="domcontentloaded")

        # 2) 404 즉시 진단
        if has_404(page):
            print("DIAG: FOUND_404_AT_HOME")
            # 404 화면 내 복귀 링크 시도
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
                # 레퍼러 달고 다시 홈
                page.goto("https://land.naver.com", referer="https://www.naver.com", wait_until="domcontentloaded")
                print("DIAG: RETRY_WITH_REFERER")
        else:
            print("DIAG: NO_404_AT_HOME")

        # 3) 아티팩트 저장 (성공/실패 모두)
        save_artifacts(page)

        # 4) 최종 상태 로그
        print("FINAL_URL:", page.url)
        if has_404(page):
            print("RESULT: STILL_404")
            os._exit(0)  # 파이프라인은 계속 흘러가게 종료코드는 0으로
        else:
            print("RESULT: OK")
            os._exit(0)

if __name__ == "__main__":
    main()
