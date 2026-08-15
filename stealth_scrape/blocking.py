"""Detect when a page is a block page rather than the content you asked for.

A 200 OK means nothing. WAFs, consent walls and SPA shells all return 200 with
a body that contains no data. Catching this is the difference between "0 results"
and "we were blocked, fall back".

The hard part is not spotting blocks, it is not crying wolf. Most large sites
sit behind a WAF and serve perfectly good pages that mention it: a page that
contains "aws-waf-token" in its session JSON has been *protected* by AWS WAF,
not *blocked* by it. Treating the vendor's name as proof of a block makes the
detector useless on exactly the sites that need it.

So markers are split by strength:

  STRONG  text a block page shows a human — "Sorry, you have been blocked".
          Conclusive on its own.
  WEAK    vendor and infrastructure names. Evidence that a WAF exists, which
          is true of most of the web. Only meaningful when the page also has
          no content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class BlockKind(str, Enum):
    NONE = "none"
    WAF = "waf"                # AWS WAF / Cloudflare / DataDome / PerimeterX
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"  # search engines throttling
    CONSENT = "consent"        # cookie/consent wall, no content behind it
    EMPTY = "empty"            # SPA shell that never hydrated


# Phrases a block page shows a human. Conclusive on their own, because no
# normal page tells you that you have been blocked.
_STRONG: list[tuple[BlockKind, tuple[str, ...]]] = [
    (BlockKind.WAF, (
        "sorry, you have been blocked",
        "attention required! | cloudflare",
        "you have been blocked from accessing this website",
        "your request has been blocked",
        "access to this page has been denied",
    )),
    (BlockKind.CAPTCHA, (
        "verify you are human",
        "i'm not a robot",
        "please complete the security check",
        "checking your browser before accessing",
    )),
    (BlockKind.RATE_LIMIT, (
        "our systems have detected unusual traffic",
        "unusual traffic from your computer network",
        "too many requests",
        "rate limit exceeded",
    )),
    (BlockKind.CONSENT, (
        "before you continue to google",
        "consent.youtube.com",
    )),
]

# Vendor and infrastructure names. Present on a large share of the web,
# including on pages that loaded perfectly. Only count when corroborated by
# the page having no actual content.
_WEAK: list[tuple[BlockKind, tuple[str, ...]]] = [
    (BlockKind.WAF, (
        "awswaf", "aws-waf", "perimeterx", "datadome", "_incapsula_",
        "challenge-platform", "captcha-delivery",
    )),
    (BlockKind.CAPTCHA, (
        "recaptcha/api.js", "hcaptcha.com/captcha", "g-recaptcha",
    )),
    (BlockKind.CONSENT, (
        "we and our partners store and/or access information",
    )),
]

# Below this, a "page" is a shell or an error stub, not content.
MIN_BODY_CHARS = 4000

# A real page has text between its tags, not just markup. Block pages and SPA
# shells are mostly script and very little prose.
MIN_TEXT_CHARS = 500

_TAG = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_MARKUP = re.compile(r"<[^>]+>")


def _visible_text_length(html: str) -> int:
    """Roughly how much human-readable text the page carries.

    Scripts and styles are removed first: a block page is often 200KB of
    challenge JavaScript wrapped around one sentence, and counting raw length
    would call that content.
    """
    without_code = _TAG.sub(" ", html)
    text = _MARKUP.sub(" ", without_code)
    return len(" ".join(text.split()))


@dataclass
class BlockVerdict:
    blocked: bool
    kind: BlockKind
    detail: str = ""

    def __bool__(self) -> bool:
        return self.blocked


def inspect(html: str | None, min_chars: int = MIN_BODY_CHARS,
            min_text: int = MIN_TEXT_CHARS) -> BlockVerdict:
    """Classify a page's HTML as content or as a block page.

    Order matters. Strong markers decide immediately. Weak markers only decide
    once the page has already failed the content test, so a healthy page behind
    a WAF is reported as content — which is what it is.
    """
    if not html:
        return BlockVerdict(True, BlockKind.EMPTY, "no html returned")

    low = html.lower()

    for kind, markers in _STRONG:
        for marker in markers:
            if marker in low:
                return BlockVerdict(True, kind, f"block page text: {marker!r}")

    text_length = _visible_text_length(html)
    has_content = len(html) >= min_chars and text_length >= min_text

    if has_content:
        # Page carries real content. Any vendor marker present is a WAF doing
        # its job in front of a page that was served to us anyway.
        return BlockVerdict(False, BlockKind.NONE)

    for kind, markers in _WEAK:
        for marker in markers:
            if marker in low:
                return BlockVerdict(
                    True, kind,
                    f"{marker!r} present and page has only {text_length} chars of text")

    return BlockVerdict(
        True, BlockKind.EMPTY,
        f"{len(html)} chars of html, {text_length} chars of text "
        f"(need {min_chars}/{min_text})")
