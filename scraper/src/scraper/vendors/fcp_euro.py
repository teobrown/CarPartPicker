"""FCP Euro vendor parsers.

FCP Euro (https://www.fcpeuro.com) was selected as the Phase 0 first vendor
after Summit Racing's product detail pages turned out to be gated by Imperva
Incapsula (returns a ~4 KB challenge to non-browser HTTP clients). FCP Euro
serves fully-rendered HTML with a JSON-LD ``Product`` block on every product
page, which makes parsing robust without JS execution.

Coverage relevant to our 8-platform launch list: Golf R / GTI (MK7/MK8) and
Audi RS3, with broad European catalog beyond.

Notes / caveats:
- Fitment is a JS-rendered widget. The static page only contains a "Make
  sure this fits your car" notification, so we use the JSON-LD product
  ``description`` as the ``fitment_text`` (it usually carries chassis /
  engine context like "MQB" / "EA888 1.8T & 2.0T" / "MK7 Golf").
- Prices come from JSON-LD ``offers[0].price`` (USD float).
- Availability is encoded as a schema.org URL
  (``https://schema.org/InStock`` / ``OutOfStock``).
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "fcp-euro"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the JSON-LD <script> block of @type=Product."""
    for s in tree.css("script[type='application/ld+json']"):
        txt = (s.text() or "").strip()
        if not txt or '"Product"' not in txt:
            continue
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            continue
        # Sometimes payload is a list of @graph nodes
        if isinstance(data, list):
            for node in data:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        elif isinstance(data, dict):
            if data.get("@type") == "Product":
                return data
            for node in data.get("@graph", []) or []:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
    return None


def _first_offer(product: dict[str, Any]) -> Optional[dict[str, Any]]:
    offers = product.get("offers")
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else None
    if isinstance(offers, dict):
        return offers
    return None


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from an FCP Euro category page.

    Product URLs match the pattern ``/products/<slug>``.
    """
    tree = HTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a[href*='/products/']"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href)
        # Strip query/fragment to dedupe variant links
        clean = absolute.split("?", 1)[0].split("#", 1)[0]
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse an FCP Euro product detail page into a NormalizedPart.

    Primary extraction path is the JSON-LD ``Product`` block. We fall back to
    DOM selectors for the few fields the JSON-LD does not always carry
    (breadcrumb-derived category hint).
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Name (required)
    name: str = ""
    if product and isinstance(product.get("name"), str):
        name = product["name"].strip()
    if not name:
        h1 = tree.css_first("h1")
        if h1:
            name = h1.text(strip=True)
    if not name:
        return None

    # Brand
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku:
        sku_el = tree.css_first("[class*='sku']")
        if sku_el:
            sku = sku_el.text(strip=True).replace("SKU:", "").replace("Part #", "").strip()

    # Price
    price_cents: Optional[int] = None
    offer = _first_offer(product) if product else None
    if offer:
        raw_price = offer.get("price")
        if isinstance(raw_price, (int, float)):
            price_cents = int(round(float(raw_price) * 100))
        elif isinstance(raw_price, str):
            try:
                price_cents = int(round(float(raw_price.replace(",", "")) * 100))
            except ValueError:
                pass
    if price_cents is None:
        price_el = tree.css_first("[class*='price']")
        if price_el:
            m = PRICE_RE.search(price_el.text())
            if m:
                price_cents = int(round(float(m.group(1).replace(",", "")) * 100))

    # In-stock
    in_stock = True
    if offer:
        avail = (offer.get("availability") or "").lower()
        if "outofstock" in avail or "out_of_stock" in avail or "soldout" in avail:
            in_stock = False

    # Image
    image_url: Optional[str] = None
    if product:
        img = product.get("image")
        if isinstance(img, str):
            image_url = img
        elif isinstance(img, list) and img:
            image_url = img[0] if isinstance(img[0], str) else None
    if image_url and image_url.startswith("/"):
        image_url = urljoin("https://www.fcpeuro.com", image_url)
    if image_url is None:
        img_el = tree.css_first("img.product-image") or tree.css_first(".product-photo img")
        if img_el:
            image_url = img_el.attributes.get("src") or img_el.attributes.get("data-src")

    # Fitment text: server-side widget is JS-only, so fall back to the
    # JSON-LD description, which usually carries chassis/engine context.
    fitment_text = ""
    if product and isinstance(product.get("description"), str):
        fitment_text = product["description"].strip()
    if not fitment_text:
        fit_el = tree.css_first(".fitment")
        if fit_el:
            fitment_text = fit_el.text(strip=True)

    # Category hint: prefer JSON-LD category, else breadcrumb anchors.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css(".breadcrumbs a") or tree.css("nav.breadcrumb a")
        if crumb_els:
            category_hint = " > ".join(c.text(strip=True) for c in crumb_els[1:] if c.text(strip=True))

    # Model: best-effort split on dashes (FCP names are like
    # "VW Performance Intercooler Kit - 034Motorsport KIT-01804").
    model = name.split(" - ")[0].strip() if " - " in name else name

    return NormalizedPart(
        vendor=VENDOR_SLUG,
        vendor_sku=sku,
        vendor_url=url,
        brand=brand,
        model=model,
        name=name,
        category_hint=category_hint,
        image_url=image_url,
        price_cents=price_cents,
        in_stock=in_stock,
        fitment_text=fitment_text,
        raw_html=html,
    )


def _guess_brand_from_name(name: str) -> str:
    return name.split()[0] if name else "Unknown"


def scrape() -> Iterator[NormalizedPart]:
    """Live scrape entry point. Wired up in Task 11."""
    raise NotImplementedError("wire up live scraping in Task 11")
