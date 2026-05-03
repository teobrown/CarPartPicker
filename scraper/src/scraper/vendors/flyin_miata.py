"""Flyin' Miata vendor parsers.

Flyin' Miata (https://flyinmiata.com) is THE Mazda MX-5 Miata specialist
— their entire catalog is fitted to the NA (1990-97), NB (1999-05),
NC (2006-15), and ND (2016-now) chassis. Adding them closes the Mazda
zero-coverage gap in our catalog in one shot.

FM is a Shopify storefront. Like PRL Motorsports / RallySport Direct,
every PDP carries a JSON-LD ``Product`` block with the standard fields
(name, sku, brand, image, description, offers). Category (collection)
pages, however, render product cards server-side as anchor tags — the
``var meta = {...};`` blob that other Shopify stores use to hand the
full product list to Shopify Analytics is **always empty** on FM, so
we can't rely on it the way the PRL parser does. Instead we anchor-scrape
``a[href^="/products/"]`` and de-duplicate.

URL conventions:
- Category (collection) pages: ``/collections/<chassis>-<system>[-<sub>]``
  e.g. ``na-handling``, ``nd-handling-coilovers``, ``nb-powertrain-exhaust``,
  ``nc-wheels``. Cross-chassis collections like ``/collections/wheels`` and
  ``/collections/big-brake-kits-for-all-generations`` also exist.
- Product detail pages: ``/products/<handle>``

Hostname caveat: FM's canonical link uses the bare apex
``flyinmiata.com`` (no www). Unlike PRL, the seeded ``baseUrl`` in the
vendor row is also the bare apex, so we do NOT coerce — we just strip
query/UTM params for canonicalization.

Notes / caveats:
- ``brand`` is the schema.org dict form
  (e.g. ``{"@type": "Brand", "name": "Flyin' Miata"}`` for in-house parts,
  ``"Konig American"`` for the Kogeki wheels FM resells, etc.).
- Miata parts are highly chassis-specific (NA/NB share a lot, NC/ND each
  break compatibility). The product description is verbose marketing prose
  that names the chassis explicitly ("for ND chassis", "1990-1997 NA"),
  so we feed name + description into ``fitment_text`` so the regex/LLM
  fitment tiers get every chassis token.
- Category pages render ~16 visible product cards (more behind pagination).
  We don't try to follow pagination — the seed list per chassis is dense
  enough that the first page covers the highest-signal SKUs.
- Image URLs come from JSON-LD ``image`` (Shopify CDN); fall back to
  ``meta[property=og:image]`` when missing.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "flyin-miata"
BASE_HOST = "https://flyinmiata.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the first JSON-LD <script> block of @type=Product."""
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


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from an FM collection page.

    FM's ``var meta = ...`` Shopify Analytics blob is always empty on
    collection pages (verified across NA/NB/NC/ND ``handling``, ``brakes``,
    ``powertrain-*``, ``wheels`` etc.) — the visible product cards are
    rendered as plain anchor tags, so we just scrape ``a[href^="/products/"]``,
    canonicalize the URLs, and de-duplicate.
    """
    out: list[str] = []
    seen: set[str] = set()

    tree = HTMLParser(html)
    for a in tree.css("a[href*='/products/']"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        path = urlsplit(absolute).path
        if not path.startswith("/products/"):
            continue
        # Only top-level product handles (/products/<handle>) — skip
        # /products/<handle>/something nested links.
        if path.count("/") != 2:
            continue
        clean = _strip_query(absolute)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)

    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse an FM product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block. Fall back to DOM selectors
    for fields the JSON-LD does not always carry.
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Prefer canonical link; strip query/UTM. FM's canonical is already
    # the bare-apex form that matches the seeded vendor.baseUrl host.
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

    # Brand. FM JSON-LD uses the dict form.
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU (prefer top-level sku, then mpn, then offer.sku).
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku and product and isinstance(product.get("mpn"), str):
        sku = product["mpn"].strip()
    if not sku:
        offer = _first_offer(product) if product else None
        if offer and isinstance(offer.get("sku"), str):
            sku = offer["sku"].strip()

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

    # In-stock. FM uses the schema.org URL form (e.g. http://schema.org/InStock).
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

    # Fitment text. Miata parts are chassis-specific (NA / NB / NC / ND)
    # and the description usually names the chassis and year range
    # explicitly ("for ND chassis", "1990-1997 NA"). We keep BOTH the
    # name and the description so the regex parser hits the chassis token
    # fast and the LLM tier has the full marketing prose to fall back on.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. FM JSON-LD doesn't populate `category`, so try the
    # breadcrumb. The orchestrator uses a per-seed slug override so this
    # is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css("nav.breadcrumb a, .breadcrumb a, .breadcrumbs a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(t for t in tail if t)

    # Model: FM names already lead with the chassis token in many cases
    # ("Flyin' Miata FOX suspension for ND", "Kogeki 15x9 flow formed wheel").
    # Strip a leading "<year-range> " prefix if present, otherwise just use
    # the full name.
    model = re.sub(r"^\d{4}(?:-\d{4})?\s+", "", name).strip()
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
        raw_html=html,
    )


def _guess_brand_from_name(name: str) -> str:
    return name.split()[0] if name else "Unknown"


def scrape() -> Iterator[NormalizedPart]:
    """Live scrape entry point. Wired up via orchestrator.run_vendor_live."""
    raise NotImplementedError("wired via orchestrator")
