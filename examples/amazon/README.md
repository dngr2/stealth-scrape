# Amazon product extraction — worked example

A single product page, extracted into one flat record. Two samples are included
because **one sample proves nothing**: Amazon serves several different detail-page
layouts, and a scraper built against one returns nulls on another.

| File | Product | Notes |
|---|---|---|
| [`sample_B0DBR3DZWG.json`](sample_B0DBR3DZWG.json) | Kingston NV3 1TB NVMe SSD | 10-row technical spec table, 27% promotion |
| [`sample_B0CFQ5T5F6.json`](sample_B0CFQ5T5F6.json) | LISEN USB-C cable 5-pack | different layout, 5 spec rows |

Both were produced by a single extractor run against the live pages, using the
block detection and stealth browser in this repo. The extractor itself isn't
published here — the notes below cover what it has to get right.

## Schema

```
asin, url, title, brand, bullets[], specs{}, images[],
price, list_price, currency, promo_text, availability,
rating, review_count,
reviews[{rating, title, body, date, verified}],
scraped_at
```

Reviews carry no reviewer identity — no name, profile link or ID. Only the
rating, text, date and verified-purchase flag are kept, because nothing else is
needed to analyse a product and collecting it would mean holding personal data
for no reason.

## Four layout traps this handles

Each one produces a scraper that looks fine on the ASIN you tested and quietly
returns nulls across a real catalogue.

**1. The price is in a hidden node.**
The authoritative price lives in `.a-offscreen`, which is visually hidden.
Selenium's `.text` returns `""` for anything not rendered, so `.text` silently
loses the price on every product. Read `textContent` instead.

**2. Spec cells contain inline JavaScript.**
`textContent` walks every descendant including `<script>`, and Amazon inlines JS
inside detail-table cells — so spec values come back as minified JavaScript.
Strip `script`/`style`/`noscript` from the DOM before reading.

**3. The review hooks were renamed.**
`data-hook="review-title"` and `review-body` became `reviewTitle` and
`reviewText`. Most published code still uses the old names and returns zero
reviews today. This queries both, since Amazon A/B-tests between them.

**4. Prices are localised by exit IP.**
The same ASIN returns USD from a US IP and EUR from a European one — the samples
here were captured from an EU host and show EUR. If a scheduled job's exit
location ever varies, you get silently mixed currencies in one column and
nothing flags it. Pin the exit region, and record `currency` per row rather than
assuming it.

Long spec cells are also rendered twice — full text plus a truncated copy ending
in "… See more" — so naive reads return the value doubled.

## Note

Amazon's Terms of Service prohibit automated access. This example exists to
demonstrate extraction and page-layout handling; it reads only public product
pages and collects no personal data. Check the ToS and `robots.txt` of any site
before pointing a scraper at it, and see the responsible-use section in the
[main README](../../README.md).
