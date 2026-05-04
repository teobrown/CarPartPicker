"""K-Tuned vendor parsers.

K-Tuned (https://www.k-tuned.com) is a Honda K-series specialist —
B/D/H/F/K-series swap parts, RSX shifters, Civic suspension, Drag Cartel
internals. Adding them deepens our Honda Civic Si and Type R coverage
beyond what PRL alone provides.

K-Tuned is a Shopify storefront — same pattern as PRL Motorsports:
- Category (collection) pages embed the product list in a Shopify
  Analytics ``var meta = { products: [...] };`` blob.
- Product detail pages carry one or more JSON-LD blocks. The site uses
  ``@type: ProductGroup`` (variant grouping) instead of ``@type: Product``
  for listings with size/spring-rate variants. We grab name + brand +
  description from the ProductGroup, and sniff price from the rendered
  HTML when the variant offers aren't directly inlined.

URL conventions:
- Category (collection) pages: ``/collections/<slug>``
- Product detail pages: ``/products/<handle>``
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "k-tuned"
BASE_HOST = "https://www.k-tuned.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")
# Tolerant of minified Shopify scripts: optional whitespace around `=`,
# no required trailing newline, and the `};` is the only required boundary.
# DOTALL so `.*?` can span lines on the unminified version.
META_BLOB_RE = re.compile(r"var\s+meta\s*=\s*(\{.*?\})\s*;", re.DOTALL)


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_jsonld_blocks(tree: HTMLParser) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in tree.css("script[type='application/ld+json']"):
        raw = node.text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend(b for b in data if isinstance(b, dict))
    return out


def _find_product_block(blocks: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Prefer Product over ProductGroup over the first thing with a name."""
    by_type: dict[str, dict[str, Any]] = {}
    for b in blocks:
        t = b.get("@type")
        if isinstance(t, str):
            by_type.setdefault(t, b)
    return by_type.get("Product") or by_type.get("ProductGroup")


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return product detail URLs from a K-Tuned collection page.

    Same shape as PRL: the static HTML carries only nav anchors; the full
    paginated listing lives in the Shopify Analytics ``var meta = {...}``
    blob.
    """
    out: list[str] = []
    seen: set[str] = set()

    m = META_BLOB_RE.search(html)
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for prod in data.get("products") or []:
                if not isinstance(prod, dict):
                    continue
                handle = prod.get("handle")
                if not isinstance(handle, str) or not handle:
                    continue
                url = urljoin(base_url, f"/products/{handle}")
                if url in seen:
                    continue
                seen.add(url)
                out.append(url)

    # Anchor fallback (rare on Shopify, kept for robustness).
    tree = HTMLParser(html)
    for a in tree.css("a[href*='/products/']"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        path = urlsplit(absolute).path
        if not path.startswith("/products/") or path.count("/") != 2:
            continue
        clean = _strip_query(absolute)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)

    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse a K-Tuned product page into a NormalizedPart.

    Pulls structured fields from the JSON-LD ProductGroup (name, brand,
    description) and uses og:* meta tags + page text for price/image when
    JSON-LD doesn't carry them inline.
    """
    tree = HTMLParser(html)
    blocks = _extract_jsonld_blocks(tree)
    product = _find_product_block(blocks)

    canonical_url = url
    canon_el = tree.css_first("link[rel='canonical']")
    if canon_el:
        href = canon_el.attributes.get("href")
        if href:
            canonical_url = href.strip()
    canonical_url = _strip_query(canonical_url)

    # Name
    name = ""
    if product and isinstance(product.get("name"), str):
        name = product["name"].strip()
    if not name:
        og = tree.css_first("meta[property='og:title']")
        if og:
            name = (og.attributes.get("content") or "").strip()
    if not name:
        h1 = tree.css_first("h1")
        if h1:
            name = h1.text(strip=True)
    if not name:
        return None

    # Brand
    brand = "K-Tuned"
    if product:
        b = product.get("brand")
        if isinstance(b, dict) and isinstance(b.get("name"), str):
            brand = b["name"].strip() or brand
        elif isinstance(b, str) and b.strip():
            brand = b.strip()

    # SKU — Shopify ProductGroup hides the SKU on variant level. Fall back
    # to deriving from URL handle.
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku:
        # /products/<handle> → handle
        path_parts = urlsplit(canonical_url).path.split("/")
        if len(path_parts) >= 3 and path_parts[1] == "products":
            sku = path_parts[2]

    # Price — sniff from HTML (Shopify renders price as plain text).
    price_cents: Optional[int] = None
    body_text = tree.text()
    pm = PRICE_RE.search(body_text)
    if pm:
        try:
            price_cents = int(round(float(pm.group(1).replace(",", "")) * 100))
        except ValueError:
            pass

    # In-stock — substring sniff (K-Tuned uses "Sold out" badges on
    # unavailable variants; presence of an Add-to-Cart button means at
    # least one variant is available).
    in_stock = "add to cart" in body_text.lower() or "addtocart" in html.lower()

    # Image
    image_url: Optional[str] = None
    if product:
        img = product.get("image")
        if isinstance(img, str):
            image_url = img
        elif isinstance(img, list) and img and isinstance(img[0], str):
            image_url = img[0]
    if image_url and image_url.startswith("/"):
        image_url = urljoin(BASE_HOST, image_url)
    if image_url is None:
        og = tree.css_first("meta[property='og:image']")
        if og:
            image_url = og.attributes.get("content") or None

    # Fitment text — JSON-LD description usually starts with "Applications:"
    # followed by year/chassis lines. Concatenate name+description so the
    # extractor sees both year ranges in name and chassis codes in body.
    description = ""
    if product and isinstance(product.get("description"), str):
        description = product["description"].strip()
    if not description:
        og = tree.css_first("meta[property='og:description']")
        if og:
            description = (og.attributes.get("content") or "").strip()
    fitment_text = (name + " " + description).strip()

    return NormalizedPart(
        vendor=VENDOR_SLUG,
        vendor_url=canonical_url,
        vendor_sku=sku or "",
        brand=brand,
        model=name,
        name=name,
        image_url=image_url,
        price_cents=price_cents,
        in_stock=in_stock,
        category_hint="",
        fitment_text=fitment_text,
        raw_html=html,
    )
