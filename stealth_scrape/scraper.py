"""The scraping engine: load a search page, survive blocks, extract rows."""
from __future__ import annotations

import contextlib
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from selenium.webdriver.common.by import By

from . import blocking
from .browser import BrowserConfig, build_driver, dismiss_cookies
from .config import Field, SiteConfig
from .fallback import site_search


@dataclass
class ScrapeResult:
    site: str
    query: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    block_kind: str = "none"
    used_fallback: bool = False
    note: str = ""


class Scraper:
    """Drives one browser across many sites and queries.

    Use as a context manager so the browser is always torn down:

        with Scraper() as s:
            result = s.search(cfg, "usb c cable")
    """

    def __init__(self, browser: BrowserConfig | None = None, verbose: bool = True):
        self.browser_cfg = browser or BrowserConfig()
        self.verbose = verbose
        self.driver = None

    def __enter__(self) -> "Scraper":
        self.driver = build_driver(self.browser_cfg)
        return self

    def __exit__(self, *exc) -> None:
        if self.driver:
            with contextlib.suppress(Exception):
                self.driver.quit()
        self.driver = None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    # ---------- page loading ----------

    def load(self, url: str, wait: float = 4.0, scrolls: int = 3) -> str:
        """Navigate, clear consent, trigger lazy-loading, return page source."""
        try:
            self.driver.get(url)
        except Exception as exc:
            self._log(f"    load error: {exc}")
            return ""
        time.sleep(wait)
        dismiss_cookies(self.driver)
        time.sleep(0.8)
        for _ in range(scrolls):
            self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
            time.sleep(0.9)
        return self.driver.page_source

    # ---------- extraction ----------

    def _read(self, element, spec: Field, base_url: str) -> str:
        try:
            target = element if spec.css in ("", ":self") else \
                element.find_element(By.CSS_SELECTOR, spec.css)
        except Exception:
            return ""

        try:
            value = target.get_attribute(spec.attr) if spec.attr else target.text
        except Exception:
            return ""
        value = (value or "").strip()

        if spec.regex and value:
            m = re.search(spec.regex, value)
            value = (m.group(1) if m and m.groups() else m.group(0)) if m else ""
        if spec.absolute and value and base_url:
            value = urljoin(base_url, value.split("?")[0])
        return re.sub(r"\s+", " ", value).strip()

    def extract(self, cfg: SiteConfig) -> list[dict[str, Any]]:
        """Pull every card currently in the DOM into a row dict."""
        rows: list[dict[str, Any]] = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, cfg.card)
        except Exception:
            return rows

        for card in cards:
            row = {name: self._read(card, spec, cfg.base_url)
                   for name, spec in cfg.fields.items()}
            missing = [n for n, s in cfg.fields.items() if s.required and not row[n]]
            if missing or not any(row.values()):
                continue
            rows.append(row)
        return rows

    # ---------- the public call ----------

    def search(self, cfg: SiteConfig, query: str) -> ScrapeResult:
        """Search one site for one query, falling back if the site blocks us."""
        res = ScrapeResult(site=cfg.name, query=query)
        url = cfg.url_for(query)
        self._log(f"  [{cfg.name}] {query!r}\n    → {url}")

        html = self.load(url, wait=cfg.wait, scrolls=cfg.scrolls)
        verdict = blocking.inspect(html)

        if verdict:
            res.blocked = True
            res.block_kind = verdict.kind.value
            self._log(f"    ⚠ blocked ({verdict.kind.value}): {verdict.detail}")

            if cfg.fallback.enabled and cfg.fallback.domain:
                self._log("    → search-engine fallback")
                urls = site_search(
                    self.driver,
                    domain=cfg.fallback.domain,
                    query=query,
                    url_contains=cfg.fallback.url_contains,
                )
                res.used_fallback = True
                res.rows = [{"url": u, "source": "search-engine-fallback"} for u in urls]
                res.note = f"{len(urls)} urls via fallback; fields unavailable"
                self._log(f"    ✓ {len(urls)} urls (URLs only — no prices)")
            return res

        res.rows = self.extract(cfg)
        self._log(f"    ✓ {len(res.rows)} rows")
        return res

    def search_many(self, cfg: SiteConfig, queries: list[str],
                    pause: float = 1.5) -> list[dict[str, Any]]:
        """Run several queries, tag each row with its query, dedupe by url."""
        all_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for q in queries:
            res = self.search(cfg, q)
            for row in res.rows:
                key = row.get("url") or repr(sorted(row.items()))
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append({**row, "query": q, "site": cfg.name})
            time.sleep(pause)
        return all_rows
