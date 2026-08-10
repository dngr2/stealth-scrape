"""stealth-scrape — config-driven Selenium scraping that survives bot protection."""
from .blocking import BlockKind, BlockVerdict, inspect
from .browser import BrowserConfig, build_driver, dismiss_cookies
from .config import Field, SiteConfig, load_all
from .fallback import site_search
from .scraper import Scraper, ScrapeResult

__version__ = "0.1.0"

__all__ = [
    "BlockKind",
    "BlockVerdict",
    "BrowserConfig",
    "Field",
    "ScrapeResult",
    "Scraper",
    "SiteConfig",
    "build_driver",
    "dismiss_cookies",
    "inspect",
    "load_all",
    "site_search",
]
