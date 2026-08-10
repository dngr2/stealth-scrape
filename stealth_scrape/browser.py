"""Stealth Chrome driver factory.

Plain HTTP clients get consent walls, 403s and empty SPA shells from most
commercial sites. A real browser with automation fingerprints removed does not.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

# Chrome exposes automation through a handful of tells. These cover the ones
# that WAF vendors actually fingerprint.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--ignore-certificate-errors",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
]

# navigator.webdriver is the single most-checked property. It has to be gone
# before the page's own scripts run, hence addScriptToEvaluateOnNewDocument
# rather than a plain execute_script after load.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

COOKIE_SELECTORS = [
    "button[data-testid='cookies-banner-accept-btn']",
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='Accept']",
    "button[aria-label*='Acceptă']",
    "#acceptCookies",
    ".cookie-accept",
    ".cc-allow",
    "button.accept",
]


@dataclass
class BrowserConfig:
    driver_path: str = "/usr/bin/chromedriver"
    user_agent: str = DEFAULT_UA
    window_size: str = "1500,2600"
    lang: str = "en-US"
    headless: bool = False
    page_load_timeout: int = 45
    extra_args: list[str] = field(default_factory=list)


def build_driver(cfg: BrowserConfig | None = None) -> webdriver.Chrome:
    """Return a Chrome driver with automation fingerprints suppressed.

    Runs headed by default — headless Chrome has its own detectable signature.
    Wrap the process in `xvfb-run -a` on a machine with no display.
    """
    cfg = cfg or BrowserConfig()
    opts = Options()
    for arg in STEALTH_ARGS:
        opts.add_argument(arg)
    opts.add_argument(f"--window-size={cfg.window_size}")
    opts.add_argument(f"--lang={cfg.lang}")
    opts.add_argument(f"--user-agent={cfg.user_agent}")
    for arg in cfg.extra_args:
        opts.add_argument(arg)
    if cfg.headless:
        opts.add_argument("--headless=new")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(cfg.driver_path), options=opts)
    driver.set_page_load_timeout(cfg.page_load_timeout)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_JS}
    )
    return driver


def dismiss_cookies(driver) -> bool:
    """Click the first cookie-consent button that matches. Returns True if one did."""
    from selenium.webdriver.common.by import By

    for sel in COOKIE_SELECTORS:
        with contextlib.suppress(Exception):
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                el.click()
                return True
    return False
