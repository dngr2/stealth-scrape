# Stealth scraper image: headed Chromium under Xvfb (headless Chrome has its own
# detectable signature), running as a non-root user.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium chromium-driver xvfb fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# browser.py reads CHROME_BIN (binary) and defaults chromedriver to /usr/bin/chromedriver.
ENV CHROME_BIN=/usr/bin/chromium \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY stealth_scrape ./stealth_scrape
RUN pip install --no-cache-dir .

# Drop privileges: rendering untrusted remote HTML should never run as root.
RUN useradd -m -u 10001 scraper && chown -R scraper:scraper /app
USER scraper

# xvfb-run provides a virtual display for headed Chrome on a machine with none.
ENTRYPOINT ["xvfb-run", "-a", "stealth-scrape"]
