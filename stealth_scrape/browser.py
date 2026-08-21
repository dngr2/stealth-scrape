"""Stealth Chrome driver factory.

Plain HTTP clients get consent walls, 403s and empty SPA shells from most
commercial sites. A real browser with automation fingerprints removed does not.
"""
from __future__ import annotations

import contextlib
import os
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
#
# SECURITY: `--no-sandbox` and `--ignore-certificate-errors` are deliberately NOT
# here. This tool renders untrusted remote HTML; disabling the sandbox removes the
# primary containment for a browser-exploit payload, and ignoring TLS errors opens
# the fetch to man-in-the-middle tampering. Both are opt-in via BrowserConfig
# (`no_sandbox` / `ignore_cert_errors`) for the environments that genuinely need
# them (e.g. running as root in a minimal container), with the risk documented there.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
]

# navigator.webdriver is the single most-checked property. It has to be gone
# before the page's own scripts run, hence addScriptToEvaluateOnNewDocument
# rather than a plain execute_script after load. The plugins/WebGL/permissions
# patches remove the coarser tells that a plain [1,2,3,4,5] stub (itself a bot
# signal — real navigator.plugins is a PluginArray of MimeType-bearing objects)
# would leave behind.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
(() => {
  const make = (name, filename, desc) => {
    const p = Object.create(Plugin.prototype);
    Object.defineProperties(p, {
      name: {value: name}, filename: {value: filename},
      description: {value: desc}, length: {value: 1},
    });
    return p;
  };
  const plugins = [
    make('Chrome PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
    make('Chrome PDF Viewer', 'mhjfbmdgcfjbbpaeojofohoefgiehjai', ''),
    make('Native Client', 'internal-nacl-plugin', ''),
  ];
  const arr = Object.create(PluginArray.prototype);
  plugins.forEach((p, i) => { arr[i] = p; arr[p.name] = p; });
  Object.defineProperty(arr, 'length', {value: plugins.length});
  Object.defineProperty(navigator, 'plugins', {get: () => arr});
})();
// WebGL vendor/renderer strings — headless/VM often report 'Google SwiftShader',
// a classic automation tell. Report a common real GPU instead.
(() => {
  const patch = (proto) => {
    const orig = proto.getParameter;
    proto.getParameter = function (p) {
      if (p === 37445) return 'Intel Inc.';            // UNMASKED_VENDOR_WEBGL
      if (p === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
      return orig.call(this, p);
    };
  };
  if (window.WebGLRenderingContext) patch(WebGLRenderingContext.prototype);
  if (window.WebGL2RenderingContext) patch(WebGL2RenderingContext.prototype);
})();
// Notification permission mismatch (default vs granted) is fingerprinted.
(() => {
  const orig = window.navigator.permissions && window.navigator.permissions.query;
  if (orig) {
    window.navigator.permissions.query = (params) =>
      params && params.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : orig(params);
  }
})();
window.chrome = window.chrome || {};
window.chrome.runtime = window.chrome.runtime || {};
window.chrome.app = window.chrome.app || {isInstalled: false};
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
    # SECURITY (both default OFF): only enable in an environment that requires it.
    # `no_sandbox` removes the Chrome sandbox — the main containment against a
    # malicious page exploiting the renderer; needed when running as root in some
    # containers, but a real risk when rendering untrusted sites. `ignore_cert_errors`
    # disables TLS validation, exposing the fetch to man-in-the-middle tampering.
    no_sandbox: bool = False
    ignore_cert_errors: bool = False
    # Explicit Chromium/Chrome binary path; falls back to $CHROME_BIN if unset.
    chrome_binary: str = ""


def build_driver(cfg: BrowserConfig | None = None) -> webdriver.Chrome:
    """Return a Chrome driver with automation fingerprints suppressed.

    Runs headed by default — headless Chrome has its own detectable signature.
    Wrap the process in `xvfb-run -a` on a machine with no display.
    """
    cfg = cfg or BrowserConfig()
    opts = Options()
    # Point Selenium at an explicit Chromium/Chrome binary when one is configured
    # (e.g. CHROME_BIN=/usr/bin/chromium in the container) — the default lookup
    # only finds google-chrome, so a chromium-only image would otherwise fail.
    chrome_bin = cfg.chrome_binary or os.environ.get("CHROME_BIN", "")
    if chrome_bin:
        opts.binary_location = chrome_bin
    for arg in STEALTH_ARGS:
        opts.add_argument(arg)
    # opt-in, security-sensitive flags (see BrowserConfig)
    if cfg.no_sandbox:
        opts.add_argument("--no-sandbox")
    if cfg.ignore_cert_errors:
        opts.add_argument("--ignore-certificate-errors")
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
