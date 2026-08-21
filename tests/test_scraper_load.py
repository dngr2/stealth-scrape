"""load() must wait for real readiness (WebDriverWait), not a blind fixed sleep.

Uses a fake driver so no real browser is launched: it reports readyState
progressing to 'complete', and we assert load() returns promptly (well under the
nominal `wait` timeout) and never blocks the full duration.
"""
import time

from stealth_scrape.scraper import Scraper


class FakeDriver:
    def __init__(self):
        self.page_source = "<html><body>ok</body></html>"
        self.scrolled = 0

    def get(self, url):
        pass

    def execute_script(self, script):
        if "readyState" in script:
            return "complete"        # ready immediately
        self.scrolled += 1           # scrollBy calls
        return None


def test_load_returns_quickly_when_ready(monkeypatch):
    s = Scraper.__new__(Scraper)     # bypass __init__ (no browser)
    s.driver = FakeDriver()
    s.verbose = False
    # cookie dismissal touches find_element; make it a no-op
    monkeypatch.setattr("stealth_scrape.scraper.dismiss_cookies", lambda d: False)

    t0 = time.time()
    html = s.load("https://example.com", wait=10.0, scrolls=0)
    elapsed = time.time() - t0

    assert "ok" in html
    # a blind sleep(wait) would take ~10s; the readiness wait returns immediately
    assert elapsed < 2.0, f"load blocked {elapsed:.1f}s — not using WebDriverWait"


def test_wait_ready_never_raises_on_bad_driver():
    s = Scraper.__new__(Scraper)
    s.driver = object()              # no execute_script → WebDriverWait errors internally
    s.verbose = False
    s._wait_ready(0.2)               # must swallow the error, not raise
