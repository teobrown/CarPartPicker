"""Skunk2 Racing vendor parsers.

Skunk2 (https://www.skunk2.com) is a long-running Honda specialist —
intake manifolds, headers, suspension, alpha-series cold air intakes for
the Civic Si and Acura platforms. Adding them deepens older + newer Si
chassis coverage that PRL alone doesn't fully address.

Skunk2 runs a Magento storefront. Unlike PRL/K-Tuned, the store does not
expose a Shopify-style ``var meta`` blob and JSON-LD is absent from the
PDPs we sampled. The category browse (`/category/<slug>/`) is also
JS-rendered — only featured products show up in static HTML. The reliable
discovery path is the search results page (`/catalogsearch/result/?q=...`)
which returns ~80 product anchors per query in static HTML.

URL conventions:
- Product detail pages: ``/<descriptive-slug>-<sku>.html`` at the root.
  e.g. ``/cold-air-intake-06-11-civic-si-343-05-0100.html``
- Category browse: ``/category/<slug>/`` (JS-rendered, low yield)
- Search results: ``/catalogsearch/result/?q=<query>`` (static, high yield)

Notes:
- No JSON-LD on PDPs. We scrape og:* meta tags for name/image/description
  and a price regex from page text.
- Skunk2 P/Ns follow the format ``###-##-####`` (e.g. 343-05-0100). They
  appear in the URL slug — that's our SKU source.
- Fitment is in <title> + og:description. Title pattern:
  "<Product Name> - '<YY>-'<YY> <Make> <Model>" (e.g. "Cold Air
  Intake - '06-'11 Civic Si"). The two-digit years let the existing
  fitment parser + LLM recover real ranges.
"""
from __future__ import annotations

import re
from html import unescape
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "skunk2"
BASE_HOST = "https://www.skunk2.com"

# Skunk2 PNs are 9 digits in 3-2-4 form (e.g. 343-05-0100).
SKU_RE = re.compile(r"\b(\d{3}-\d{2}-\d{4})\b")
# Magento price tags: ``<span class="price">$393.45</span>``
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return product detail URLs from a Skunk2 search-result or category page.

    Skunk2 PDPs live at the root path with a ``.html`` suffix, e.g.
    ``https://www.skunk2.com/cold-air-intake-06-11-civic-si-343-05-0100.html``.
    Filters out static / nav links by requiring the URL contain a
    Skunk2-format part number in the slug.
    """
    out: list[str] = []
    seen: set[str] = set()

    for m in re.finditer(r'href="(https?://www\.skunk2\.com/[^"]+\.html)"', html):
        href = m.group(1)
        # Require a part number in the slug — keeps category / nav URLs out.
        if not SKU_RE.search(href):
            continue
        clean = _strip_query(href)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)

    return out


def _meta_content(tree: HTMLParser, *selectors: str) -> Optional[str]:
    for sel in selectors:
        node = tree.css_first(sel)
        if node:
            v = node.attributes.get("content")
            if v:
                return unescape(v).strip()
    return None


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse a Skunk2 PDP into a NormalizedPart.

    Skunk2 has no JSON-LD; we rely on og:* meta tags + page text:
    - name      : og:title (or <title>)
    - image     : og:image
    - description: og:description
    - SKU       : ###-##-#### parsed out of the URL
    - price     : first ``$X.XX`` match in the rendered text
    """
    tree = HTMLParser(html)

    canonical_url = _strip_query(url)
    canon_el = tree.css_first("link[rel='canonical']")
    if canon_el:
        href = canon_el.attributes.get("href")
        if href:
            canonical_url = _strip_query(href.strip())

    name = _meta_content(tree, "meta[property='og:title']")
    if not name:
        title_el = tree.css_first("title")
        name = title_el.text(strip=True) if title_el else ""
    if not name:
        return None
    # Skunk2 wraps og:title in entity-encoded characters even after
    # unescape; collapse runs of whitespace so the name is clean.
    name = re.sub(r"\s+", " ", name).strip()

    sku_match = SKU_RE.search(canonical_url) or SKU_RE.search(html)
    sku = sku_match.group(1) if sku_match else None

    image_url = _meta_content(tree, "meta[property='og:image']")
    description = _meta_content(tree, "meta[property='og:description']", "meta[name='description']") or ""

    # Price from the rendered page (first $X.XX in body text).
    price_cents: Optional[int] = None
    body_text = tree.text()
    pm = PRICE_RE.search(body_text)
    if pm:
        try:
            price_cents = int(round(float(pm.group(1).replace(",", "")) * 100))
        except ValueError:
            pass

    # In-stock — Magento renders an "Add to Cart" button only when at least
    # one option is available. Out-of-stock pages show a "Currently
    # unavailable" message.
    body_lower = body_text.lower()
    in_stock = ("add to cart" in body_lower) and ("currently unavailable" not in body_lower)

    # Fitment — title carries year + Civic/Acura hints, og:description
    # adds product context. Both feed into the LLM extractor.
    fitment_text = (name + " " + description).strip()

    return NormalizedPart(
        vendor=VENDOR_SLUG,
        vendor_url=canonical_url,
        vendor_sku=sku or "",
        brand="Skunk2",
        model=name,
        name=name,
        image_url=image_url,
        price_cents=price_cents,
        in_stock=in_stock,
        category_hint="",
        fitment_text=fitment_text,
        raw_html=html,
    )
