"""Site profiles: declarative scraping rules, one YAML file per site.

Adding a new site is a config file, not code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Field:
    """One extracted column."""
    css: str
    attr: str = ""          # "" = element text; otherwise read this attribute
    absolute: bool = False  # prefix relative hrefs with base_url
    regex: str = ""         # optional: keep only the first capture group
    required: bool = False  # drop the row if this field is empty


@dataclass
class Fallback:
    domain: str = ""
    url_contains: str = ""
    enabled: bool = True


@dataclass
class SiteConfig:
    name: str
    search_url: str                    # must contain {query}
    card: str                          # CSS selector for one result card
    fields: dict[str, Field]
    base_url: str = ""
    description: str = ""
    query_sep: str = "+"               # how spaces are encoded in search_url
    wait: float = 4.0                  # seconds after load before reading
    scrolls: int = 3                   # lazy-load passes
    fallback: Fallback = field(default_factory=Fallback)

    @classmethod
    def load(cls, path: str | Path) -> "SiteConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        fields = {
            key: Field(**spec) if isinstance(spec, dict) else Field(css=spec)
            for key, spec in (raw.pop("fields", {}) or {}).items()
        }
        fb = Fallback(**(raw.pop("fallback", {}) or {}))
        return cls(fields=fields, fallback=fb, **raw)

    def url_for(self, query: str) -> str:
        return self.search_url.format(query=query.strip().replace(" ", self.query_sep))


def load_all(directory: str | Path) -> dict[str, SiteConfig]:
    """Load every *.yaml in a directory, keyed by site name."""
    out: dict[str, SiteConfig] = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        cfg = SiteConfig.load(p)
        out[cfg.name] = cfg
    return out
