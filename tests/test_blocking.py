"""Block detection is the part that must not be wrong.

A false negative means parsing a block page as data and reporting "0 results".
A false positive means falling back when the real page was fine.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stealth_scrape import blocking  # noqa: E402

FILLER = "<div>content</div>" * 500  # comfortably over MIN_BODY_CHARS


def test_clean_page_is_not_blocked():
    verdict = blocking.inspect(f"<html><body>{FILLER}</body></html>")
    assert not verdict.blocked
    assert verdict.kind is blocking.BlockKind.NONE


def test_aws_waf_detected():
    verdict = blocking.inspect(f"<html><script src='awswaf.js'></script>{FILLER}</html>")
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.WAF


def test_google_rate_limit_detected():
    html = f"<html>Our systems have detected unusual traffic{FILLER}</html>"
    verdict = blocking.inspect(html)
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.RATE_LIMIT


def test_captcha_detected():
    verdict = blocking.inspect(f"<html><div class='g-recaptcha'></div>{FILLER}</html>")
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.CAPTCHA


def test_short_body_is_empty_shell():
    verdict = blocking.inspect("<html><body>loading…</body></html>")
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.EMPTY


def test_none_html_is_blocked():
    assert blocking.inspect(None).kind is blocking.BlockKind.EMPTY


def test_verdict_is_falsy_when_clean():
    # BlockVerdict.__bool__ lets callers write `if verdict:`
    assert not bool(blocking.inspect(f"<html>{FILLER}</html>"))
    assert bool(blocking.inspect("<html>awswaf</html>"))
