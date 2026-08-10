"""Detect when a page is a block page rather than the content you asked for.

A 200 OK means nothing. WAFs, consent walls and SPA shells all return 200 with
a body that contains no data. Catching this is the difference between "0 results"
and "we were blocked, fall back".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlockKind(str, Enum):
    NONE = "none"
    WAF = "waf"                # AWS WAF / Cloudflare / DataDome / PerimeterX
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"  # search engines throttling
    CONSENT = "consent"        # cookie/consent wall, no content behind it
    EMPTY = "empty"            # SPA shell that never hydrated


# Substrings that only ever appear on block pages, lowercased.
_MARKERS: list[tuple[BlockKind, tuple[str, ...]]] = [
    (BlockKind.WAF, (
        "awswaf", "aws-waf", "captcha-delivery", "challenge-platform",
        "sorry, you have been blocked", "request blocked", "access denied",
        "attention required! | cloudflare", "perimeterx", "datadome",
        "_incapsula_", "please enable cookies and reload the page",
    )),
    (BlockKind.CAPTCHA, (
        "recaptcha/api.js", "hcaptcha.com/captcha", "g-recaptcha",
        "verify you are human", "i'm not a robot",
    )),
    (BlockKind.RATE_LIMIT, (
        "our systems have detected unusual traffic",
        "unusual traffic from your computer network",
        "too many requests", "rate limit exceeded",
    )),
    (BlockKind.CONSENT, (
        "before you continue to google", "consent.youtube.com",
        "we and our partners store and/or access information",
    )),
]

# Below this, a "page" is a shell or an error stub, not content.
MIN_BODY_CHARS = 4000


@dataclass
class BlockVerdict:
    blocked: bool
    kind: BlockKind
    detail: str = ""

    def __bool__(self) -> bool:
        return self.blocked


def inspect(html: str | None, min_chars: int = MIN_BODY_CHARS) -> BlockVerdict:
    """Classify a page's HTML as content or as a block page."""
    if not html:
        return BlockVerdict(True, BlockKind.EMPTY, "no html returned")

    low = html.lower()
    for kind, markers in _MARKERS:
        for m in markers:
            if m in low:
                return BlockVerdict(True, kind, f"matched marker: {m!r}")

    if len(html) < min_chars:
        return BlockVerdict(
            True, BlockKind.EMPTY, f"body only {len(html)} chars (< {min_chars})"
        )

    return BlockVerdict(False, BlockKind.NONE)
