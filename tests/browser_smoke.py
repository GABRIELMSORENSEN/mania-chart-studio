"""Opt-in real network/browser test. Requires running local server and model.

Run: python tests/browser_smoke.py
Does not certify musical quality. Screenshots/audio stay ignored by Git.
"""
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "test-results"
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto("http://127.0.0.1:8765")
    page.wait_for_function("() => document.querySelector('#library-list').textContent !== 'Carregando biblioteca…'")
    page.screenshot(path=str(OUT / "studio-empty.png"), full_page=True)
    page.locator("#url").fill("https://example.com/test")
    page.locator("#generate-button").click()
    assert "HTTPS" in page.locator("#form-error").inner_text()
    page.locator("#url").fill("https://youtu.be/s4fuzKjr4cA")
    assert page.locator("#style option").count() == 8
    page.locator("#style").select_option("stream")
    assert page.locator("#style").input_value() == "stream"
    page.locator("#style").select_option("auto")
    page.locator("#generate-button").click()
    deadline = time.monotonic() + 300
    while page.locator("#project").is_hidden() and time.monotonic() < deadline:
        if page.locator("#form-error").inner_text():
            raise RuntimeError(page.locator("#form-error").inner_text())
        page.wait_for_timeout(1000)
    assert page.locator("#project").is_visible(), page.locator("#job-status").inner_text()
    page.screenshot(path=str(OUT / "studio-project.png"), full_page=True)
    page.locator("#play").click()
    page.wait_for_timeout(2300)
    assert page.locator("#clock").inner_text().startswith("0:02")
    page.locator("#play").click()
    page.locator("#offset").fill("10")
    page.locator("#apply-timing").click()
    assert page.locator("#undo").is_enabled()
    page.locator("#undo").click()
    page.locator("summary").click()
    page.locator("#note-time").fill("100")
    page.locator("#add-note").click()
    assert "inserida" in page.locator("#editor-status").inner_text()
    page.locator("#undo").click()
    page.locator("#save").click()
    page.wait_for_function("() => document.querySelector('#editor-status').textContent.includes('Projeto salvo')")
    with page.expect_download() as info:
        page.locator("#export").click()
    download = info.value
    download.save_as(str(OUT / "real-youtube-export.osz"))
    assert (OUT / "real-youtube-export.osz").stat().st_size > 100000
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    page.screenshot(path=str(OUT / "studio-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#style").focus()
    page.keyboard.press("End")
    page.keyboard.press("Tab")
    assert page.locator("#style").input_value() == "ln"
    assert not errors, errors
    (OUT / "browser-report.json").write_text(json.dumps({"page_errors": errors, "real_youtube_generation": True, "export_bytes": (OUT / "real-youtube-export.osz").stat().st_size, "mobile_overflow": False, "preview_clock_advances": True}, indent=2))
    browser.close()
    print("BROWSER_REAL_FLOW_OK")
