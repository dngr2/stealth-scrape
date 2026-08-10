"""Search-engine fallback for when a site's own search is behind a WAF.

If example.com/search is blocked, the same product pages are usually indexed.
`site:example.com <query>` on DuckDuckGo or Bing gets you the URLs, and each
individual product page is often served normally even when search is not.

Engines are tried in order — DuckDuckGo first because it throttles least.
Google is deliberately absent: it rate-limits automated queries within a
handful of requests and then poisons the session.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import quote_plus, unquote

from .browser import dismiss_cookies


@dataclass
class Engine:
    name: str
    url_template: str
    # DuckDuckGo wraps results as /l/?uddg=<urlencoded>; Bing links are direct.
    patterns: tuple[str, ...]


ENGINES = (
    Engine(
        "duckduckgo",
        "https://html.duckduckgo.com/html/?q={q}",
        (r"uddg=([^&\"']+)",),
    ),
    Engine(
        "bing",
        "https://www.bing.com/search?q={q}&count=30",
        (r'href="(https?://[^"]+)"',),
    ),
)


def site_search(
    driver,
    domain: str,
    query: str,
    url_contains: str = "",
    limit: int = 20,
    pause: float = 2.5,
) -> list[str]:
    """Return URLs on `domain` matching `query`, found via search engines.

    `url_contains` filters to a path fragment that marks a real content page
    (e.g. "/pd/" for eMAG products, "/d/oferta/" for OLX listings), which drops
    category and help pages from the results.
    """
    found: list[str] = []
    seen: set[str] = set()
    q = quote_plus(f"site:{domain} {query}")

    for engine in ENGINES:
        try:
            driver.get(engine.url_template.format(q=q))
        except Exception:
            continue
        time.sleep(pause)
        dismiss_cookies(driver)
        time.sleep(0.8)

        html = driver.page_source
        for pat in engine.patterns:
            for m in re.finditer(pat, html):
                url = unquote(m.group(1)).split("&")[0].split("?")[0]
                if domain not in url:
                    continue
                if url_contains and url_contains not in url:
                    continue
                if url in seen:
                    continue
                seen.add(url)
                found.append(url)
                if len(found) >= limit:
                    return found

        if found:
            break  # first engine that produced anything wins

    return found
