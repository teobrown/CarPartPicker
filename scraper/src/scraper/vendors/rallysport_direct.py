"""RallySport Direct vendor parsers.

RallySport Direct (https://www.rallysportdirect.com) is the third vendor
wired up after FCP Euro and AmericanMuscle. They're a Subaru specialist
(WRX / STI / BRZ / Crosstrek / Forester / Outback), so adding them gives
us first-pass coverage of the WRX flagship platform that previously had
zero compatible parts in the catalog.

RSD is a Shopify storefront. Like FCP Euro and AmericanMuscle, every
product detail page carries a JSON-LD ``Product`` block with name, sku,
brand, offers (price + availability), image, and description, so the
primary parsing path mirrors those vendors: locate the
``application/ld+json`` ``Product`` node and pull fields from it.

URL conventions:
- Category (collection) pages: ``/collections/<slug>``
- Product detail pages: ``/products/<slug>``

Notes / caveats:
- Subaru fitment is encoded inline in the product name itself (e.g.
  "Cobb SF Intake System - 2015-2021 Subaru WRX"). We feed that into
  ``fitment_text`` along with the JSON-LD description so the regex
  parser in ``fitment_parser.py`` can latch on to year ranges and
  chassis codes.
- ``brand`` in RSD's JSON-LD is the schema.org dict form
  (``{"@type": "Brand", "name": "COBB"}``).
- Availability is the schema.org URL form
  (``http://schema.org/InStock`` / ``OutOfStock``).
- Image URLs come from the JSON-LD ``image`` field (Shopify CDN); we
  fall back to ``meta[property=og:image]`` when missing.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "rallysport-direct"
BASE_HOST = "https://www.rallysportdirect.com"
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


def _strip_query(url: str) -> str:
    """Drop query string and fragment from a URL (for canonicalization)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from an RSD collection page.

    RSD is a Shopify storefront, so all product detail pages live at
    ``/products/<slug>`` and the collection page renders them as
    ``<a href="/products/...">`` anchors inside product card containers.
    We dedupe by canonical (no-query) URL.
    """
    tree = HTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a[href*='/products/']"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        # Reject anything that escaped to another host
        if not absolute.startswith(BASE_HOST + "/"):
            continue
        # Reject sub-routes like /products/<slug>/... that aren't PDPs
        path = urlsplit(absolute).path
        # /products/<slug> → split on / gives ['', 'products', '<slug>']
        if not path.startswith("/products/"):
            continue
        if path.count("/") != 2:
            continue
        clean = _strip_query(absolute)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse an RSD product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block. DOM fallbacks for fields the
    JSON-LD does not always carry.
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Prefer the canonical link if present so we always store a clean URL.
    canonical_url = url
    canon_el = tree.css_first("link[rel='canonical']")
    if canon_el:
        href = canon_el.attributes.get("href")
        if href:
            canonical_url = href.strip()
    canonical_url = _strip_query(canonical_url)

    # Name (required).
    name: str = ""
    if product and isinstance(product.get("name"), str):
        name = product["name"].strip()
    if not name:
        h1 = tree.css_first("h1")
        if h1:
            name = h1.text(strip=True)
    if not name:
        return None

    # Brand. RSD's JSON-LD uses the {name: ...} dict form.
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU.
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku and product and isinstance(product.get("mpn"), str):
        sku = product["mpn"].strip()

    # Price.
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

    # In-stock.
    in_stock = True
    if offer:
        avail = (offer.get("availability") or "").lower()
        if "outofstock" in avail or "out_of_stock" in avail or "soldout" in avail:
            in_stock = False

    # Image.
    image_url: Optional[str] = None
    if product:
        img = product.get("image")
        if isinstance(img, str):
            image_url = img
        elif isinstance(img, list) and img:
            image_url = img[0] if isinstance(img[0], str) else None
    if image_url and image_url.startswith("/"):
        image_url = urljoin(BASE_HOST, image_url)
    if image_url is None:
        og = tree.css_first("meta[property='og:image']")
        if og:
            image_url = (og.attributes.get("content") or None)

    # Fitment text. RSD encodes year ranges + chassis directly in the
    # product name (e.g. "2015-2021 Subaru WRX"), so we put the name first
    # to give the regex parser the cleanest signal, then append the
    # JSON-LD description (verbose marketing blurb that often carries
    # additional year/trim references).
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint: prefer JSON-LD category if it's a string, else the
    # last leaf of the breadcrumb. The orchestrator uses a per-seed slug
    # override so this is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css("nav.breadcrumb a, .breadcrumb a, .breadcrumbs a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(tail)

    # Model: RSD names look like "Cobb SF Intake System - 2015-2021 Subaru WRX".
    # Strip a trailing " - <year-range> ..." suffix if present so the model
    # field carries the part name without fitment noise.
    model = re.split(r"\s+-\s+\d{4}", name, maxsplit=1)[0].strip()
    if not model:
        model = name

    return NormalizedPart(
        vendor=VENDOR_SLUG,
        vendor_sku=sku,
        vendor_url=canonical_url,
        brand=brand,
        model=model,
        name=name,
        category_hint=category_hint,
        image_url=image_url,
        price_cents=price_cents,
        in_stock=in_stock,
        fitment_text=fitment_text,
    )


def _guess_brand_from_name(name: str) -> str:
    return name.split()[0] if name else "Unknown"


def scrape() -> Iterator[NormalizedPart]:
    """Live scrape entry point. Wired up via orchestrator.run_vendor_live."""
    raise NotImplementedError("wired up via orchestrator.run_vendor_live")
