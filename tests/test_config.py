"""Site profiles must load and build URLs correctly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stealth_scrape import SiteConfig, load_all  # noqa: E402

SITES = Path(__file__).resolve().parent.parent / "sites"


def test_every_shipped_profile_loads():
    configs = load_all(SITES)
    assert configs, "no site profiles found"
    for name, cfg in configs.items():
        assert cfg.name == name
        assert "{query}" in cfg.search_url, f"{name}: search_url needs a {{query}}"
        assert cfg.card, f"{name}: missing card selector"
        assert cfg.fields, f"{name}: no fields defined"


def test_query_encoding_respects_separator():
    olx = SiteConfig.load(SITES / "olx.yaml")
    assert olx.url_for("rtx 3090") == "https://www.olx.ro/oferte/q-rtx-3090/"

    emag = SiteConfig.load(SITES / "emag.yaml")
    assert emag.url_for("router gigabit") == "https://www.emag.ro/search/router+gigabit"


def test_query_is_trimmed():
    olx = SiteConfig.load(SITES / "olx.yaml")
    assert olx.url_for("  rtx 3090  ") == olx.url_for("rtx 3090")


def test_fields_parse_into_specs():
    olx = SiteConfig.load(SITES / "olx.yaml")
    assert olx.fields["title"].required is True
    assert olx.fields["url"].attr == "href"
    assert olx.fields["url"].absolute is True


def test_fallback_configured_for_protected_sites():
    emag = SiteConfig.load(SITES / "emag.yaml")
    assert emag.fallback.enabled
    assert emag.fallback.domain == "emag.ro"
    assert emag.fallback.url_contains == "/pd/"
