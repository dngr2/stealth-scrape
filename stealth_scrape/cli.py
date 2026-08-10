"""Command-line interface.

    python -m stealth_scrape --site olx --query "rtx 3090" --out results.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import export
from .browser import BrowserConfig
from .config import SiteConfig, load_all
from .scraper import Scraper

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stealth-scrape",
        description="Config-driven Selenium scraper that survives bot protection.",
    )
    p.add_argument("--site", help="site profile name (see --list)")
    p.add_argument("--query", "-q", action="append", default=[],
                   help="search term; repeat for several")
    p.add_argument("--out", "-o", default="results.csv",
                   help="output file; format inferred from extension")
    p.add_argument("--format", "-f", default="", choices=["", "csv", "json", "jsonl"])
    p.add_argument("--sites-dir", default=str(SITES_DIR))
    p.add_argument("--headless", action="store_true",
                   help="not recommended — headless Chrome is easier to fingerprint")
    p.add_argument("--driver", default="/usr/bin/chromedriver")
    p.add_argument("--wait", type=float, default=None, help="override per-site wait")
    p.add_argument("--list", action="store_true", help="list site profiles and exit")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sites = load_all(args.sites_dir)

    if args.list or not args.site:
        print(f"Site profiles in {args.sites_dir}:\n")
        for name, cfg in sites.items():
            print(f"  {name:<12} {cfg.description or cfg.search_url}")
        if not args.site and not args.list:
            print("\nNothing to do: pass --site NAME --query TERM", file=sys.stderr)
            return 2
        return 0

    if args.site not in sites:
        print(f"unknown site {args.site!r}; known: {', '.join(sites)}", file=sys.stderr)
        return 2
    if not args.query:
        print("at least one --query is required", file=sys.stderr)
        return 2

    cfg: SiteConfig = sites[args.site]
    if args.wait is not None:
        cfg.wait = args.wait

    browser = BrowserConfig(driver_path=args.driver, headless=args.headless)
    with Scraper(browser=browser, verbose=not args.quiet) as scraper:
        rows = scraper.search_many(cfg, args.query)

    if not rows:
        print("\nNo rows extracted.", file=sys.stderr)
        return 1

    path = export.write(rows, args.out, args.format)
    print(f"\n{len(rows)} rows → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
