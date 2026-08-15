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


def test_waf_vendor_string_on_a_full_page_is_not_a_block():
    """Changed deliberately: this test used to assert the opposite.

    Most large sites sit behind a WAF and say so in their own markup. The
    real-world case was peopleperhour.com, whose served pages contain
    "aws-waf-token" in a session JSON blob — 348KB of listings reported as
    blocked.
    """
    verdict = blocking.inspect(f"<html>awswaf{FILLER}</html>")
    assert not verdict.blocked


def test_waf_vendor_string_with_no_content_is_a_block():
    verdict = blocking.inspect("<html>awswaf</html>")
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.WAF


def test_google_rate_limit_detected():
    html = f"<html>Our systems have detected unusual traffic{FILLER}</html>"
    verdict = blocking.inspect(html)
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.RATE_LIMIT


def test_captcha_widget_on_a_full_page_is_not_a_block():
    """Changed deliberately: this test used to assert the opposite.

    A page carrying a reCAPTCHA widget *and* a full body of content is
    usually a login or signup form, not a block. Asserting otherwise is what
    made the detector fire on healthy pages.
    """
    verdict = blocking.inspect(f"<html><div class='g-recaptcha'></div>{FILLER}</html>")
    assert not verdict.blocked


def test_captcha_widget_with_no_content_is_a_block():
    verdict = blocking.inspect("<html><div class='g-recaptcha'></div></html>")
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.CAPTCHA


def test_captcha_challenge_text_is_always_a_block():
    verdict = blocking.inspect(f"<html>Verify you are human{FILLER}</html>")
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
    assert bool(blocking.inspect("<html>awswaf</html>"))  # marker + no content


# --- regression: WAF present is not WAF blocking -------------------------
#
# stealth-scrape reported peopleperhour.com as WAF-blocked while the page had
# loaded perfectly — 348KB of HTML, 171 job listings. The marker "aws-waf"
# matched `aws-waf-token=...` inside the site's own session JSON.
#
# The site is *protected* by AWS WAF. So is much of the web. Treating the
# vendor's name as proof of a block made the detector fire on exactly the
# sites it exists to help with.

REAL_PAGE_BEHIND_A_WAF = (
    "<html><head><title>Technology &amp; Programming Projects</title></head>"
    "<body>"
    '<script>window.__STATE__={"session":{"cookies":"aws-waf-token=4328d67f-60c4"}}</script>'
    + "<div class='listing'>Camera SDK development. Looking for a software "
      "developer to build and develop a full camera SDK for an industrial "
      "client, including firmware bindings and documentation. </div>" * 60
    + "</body></html>"
)

GENUINE_WAF_BLOCK = (
    "<html><body><h1>Sorry, you have been blocked</h1>"
    "<p>You are unable to access this website</p></body></html>"
)

SHELL_WITH_VENDOR_MARKER = (
    "<html><body><script src='/challenge-platform/h/b/orchestrate'></script>"
    "<div id='root'></div></body></html>"
)


def test_waf_cookie_in_a_healthy_page_is_not_a_block():
    verdict = blocking.inspect(REAL_PAGE_BEHIND_A_WAF)
    assert not verdict.blocked, verdict.detail
    assert verdict.kind is blocking.BlockKind.NONE


def test_genuine_block_page_text_is_still_caught():
    verdict = blocking.inspect(GENUINE_WAF_BLOCK)
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.WAF


def test_vendor_marker_plus_no_content_is_a_block():
    """The weak marker still counts when there is nothing behind it."""
    verdict = blocking.inspect(SHELL_WITH_VENDOR_MARKER)
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.WAF


def test_block_text_wins_even_on_a_large_page():
    """A block page padded with challenge JavaScript is still a block page."""
    padded = GENUINE_WAF_BLOCK + "<script>" + ("x" * 50_000) + "</script>"
    assert blocking.inspect(padded).blocked


def test_script_heavy_shell_is_not_mistaken_for_content():
    """200KB of JavaScript around one sentence is not a page of results."""
    shell = "<html><body><script>" + ("y" * 60_000) + "</script><p>Loading</p></body></html>"
    verdict = blocking.inspect(shell)
    assert verdict.blocked
    assert verdict.kind is blocking.BlockKind.EMPTY


def test_thresholds_are_caller_controlled():
    """A caller scraping deliberately small pages can lower the bar."""
    small = "<html><body><p>" + ("word " * 40) + "</p></body></html>"
    assert blocking.inspect(small).blocked
    assert not blocking.inspect(small, min_chars=100, min_text=100).blocked
