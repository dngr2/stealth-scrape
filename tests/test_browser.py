"""Tests for the Chrome factory's security defaults and stealth payload.

These assert the hardening decisions without launching a real browser: the
insecure flags must be absent by default and only appear when explicitly
opted in, and the stealth JS must not carry the [1,2,3,4,5] plugin bot-tell.
"""
from stealth_scrape import browser
from stealth_scrape.browser import STEALTH_ARGS, STEALTH_JS, BrowserConfig


def test_insecure_flags_not_default():
    assert "--no-sandbox" not in STEALTH_ARGS
    assert "--ignore-certificate-errors" not in STEALTH_ARGS


def test_config_defaults_are_secure():
    cfg = BrowserConfig()
    assert cfg.no_sandbox is False
    assert cfg.ignore_cert_errors is False


def test_opt_in_flags_are_applied(monkeypatch):
    added = []

    class FakeOpts:
        def add_argument(self, a):
            added.append(a)

        def add_experimental_option(self, *a, **k):
            pass

    class FakeDriver:
        def set_page_load_timeout(self, *a):
            pass

        def execute_cdp_cmd(self, *a, **k):
            pass

    monkeypatch.setattr(browser, "Options", lambda: FakeOpts())
    monkeypatch.setattr(browser, "Service", lambda *a, **k: None)
    monkeypatch.setattr(browser.webdriver, "Chrome", lambda *a, **k: FakeDriver())

    browser.build_driver(BrowserConfig(no_sandbox=True, ignore_cert_errors=True))
    assert "--no-sandbox" in added
    assert "--ignore-certificate-errors" in added


def test_default_build_omits_insecure_flags(monkeypatch):
    added = []

    class FakeOpts:
        def add_argument(self, a):
            added.append(a)

        def add_experimental_option(self, *a, **k):
            pass

    class FakeDriver:
        def set_page_load_timeout(self, *a):
            pass

        def execute_cdp_cmd(self, *a, **k):
            pass

    monkeypatch.setattr(browser, "Options", lambda: FakeOpts())
    monkeypatch.setattr(browser, "Service", lambda *a, **k: None)
    monkeypatch.setattr(browser.webdriver, "Chrome", lambda *a, **k: FakeDriver())

    browser.build_driver()
    assert "--no-sandbox" not in added
    assert "--ignore-certificate-errors" not in added


def test_stealth_js_has_no_numeric_plugin_stub():
    # the old [1,2,3,4,5] stub was itself a bot tell
    assert "[1, 2, 3, 4, 5]" not in STEALTH_JS
    assert "[1,2,3,4,5]" not in STEALTH_JS
    # and the hardened surfaces are present
    assert "PluginArray" in STEALTH_JS
    assert "getParameter" in STEALTH_JS  # WebGL
    assert "permissions" in STEALTH_JS
