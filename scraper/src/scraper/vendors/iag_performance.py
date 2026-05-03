"""IAG Performance vendor parsers.

IAG Performance (https://www.iagperformance.com) is a Subaru specialist —
their catalog is the deepest WRX/STI/BRZ-fit set on the market and pairs
COBB Tuning's full house catalog (catbacks, tuners, BPVs) with IAG's own
engine internals, AOS systems, and built short/long blocks. Adding them
deepens the Subaru coverage that RallySport Direct only half-fills (RSD
doesn't carry IAG-house AOS / engine-builds at all).

IAG runs on **BigCommerce Stencil**. Like FCP Euro / RSD / PRL / FM, every
PDP carries a single JSON-LD ``Product`` block carrying name / sku / mpn /
brand (dict form) / image / offers — the standard schema.org payload. The
storefront is fully server-rendered (no JS hydration needed), so category
pages list every visible product card directly in the HTML.

URL conventions:
- Category pages: ``/<system>/<sub>[/<sub>]/`` with trailing slash
  (e.g. ``/engine/exhausts/cat-back/``,
  ``/suspension/height-adjustment/coilovers/``).
- Product detail pages: PDPs **usually** end with a ``-<part-number>/``
  suffix (e.g. ``/cobb-titanium-catback-…-516160/``) but **not always**
  — in particular IAG-house parts often drop the suffix (e.g.
  ``/iag-air-oil-separator-aos-fits-2022-24-subaru-wrx/``). We anchor
  category extraction on the BigCommerce Stencil card-title selector
  (``article.card h4.card-title a``) which doesn't depend on the URL
  shape.

Notes / caveats:
- ``brand`` is the schema.org dict form
  (``{"@type": "Brand", "name": "COBB"}`` for COBB-resold parts,
  ``{"@type": "Brand", "name": "IAG Performance"}`` for IAG-house). We
  also handle the bare-string form defensively.
- ``sku`` carries a noisy storefront prefix (e.g. ``ds_FMKH_516160`` —
  BigCommerce dropship integration code), while ``mpn`` carries the
  clean manufacturer part number (``516160``). We prefer ``mpn`` and
  fall back to ``sku`` only when ``mpn`` is missing.
- IAG carries multi-brand resold parts (COBB / Invidia / AWE / IAG-house
  / Magnaflow / Borla) so brand discrimination matters for downstream
  inventory + fitment queries.
- Multi-platform fitment: many products fit BRZ + GR86 + FR-S + Toyota
  86 simultaneously. We feed the full description into ``fitment_text``
  so every chassis/year token is visible to the regex/LLM tiers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "iag-performance"
BASE_HOST = "https://www.iagperformance.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the JSON-LD ``Product`` block on an IAG PDP.

    IAG emits two JSON-LD blocks per PDP — a ``BreadcrumbList`` and a
    single ``Product``. We pick the first ``Product`` we find; all the
    identifying fields (name / sku / mpn / brand / image / offers) live
    on it. Defensive against ``@graph`` wrappers and array-shaped
    payloads even though IAG's stock template doesn't currently use
    either.
    """
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


def _brand_name(product: Optional[dict[str, Any]]) -> str:
    """Pull the brand name out of the JSON-LD payload.

    IAG's ``Product.brand`` is the schema.org dict form
    (``{"@type": "Brand", "name": "COBB"}``) on every PDP we've seen,
    but we also accept the bare-string form because BigCommerce
    storefronts can flip between them based on theme version.
    """
    if not product:
        return ""
    b = product.get("brand")
    if isinstance(b, dict):
        return (b.get("name") or "").strip()
    if isinstance(b, str):
        return b.strip()
    return ""


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from an IAG category page.

    BigCommerce Stencil renders product cards as
    ``<article class="card">`` blocks with the canonical product link
    living on the ``h4.card-title a`` element. This selector is robust
    to PDPs that don't follow the ``-<part-number>/`` URL convention
    (notably IAG-house items like the AOS line). A secondary fallback
    on ``a.product_img_link`` catches the same PDPs from the figure
    block in case the title anchor ever changes.
    """
    out: list[str] = []
    seen: set[str] = set()

    tree = HTMLParser(html)

    # Primary: title anchor inside each product card. Stable across IAG's
    # current Stencil theme.
    selectors = [
        "h4.card-title a",
        ".card-title a",
        "a.product_img_link",
    ]
    for sel in selectors:
        for a in tree.css(sel):
            href = a.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(base_url, href.strip())
            parts = urlsplit(absolute)
            # Stay on the IAG host — drop cross-domain anchors (CDN, blog,
            # social) that occasionally appear inside the page chrome.
            if parts.netloc and "iagperformance.com" not in parts.netloc:
                continue
            # Drop nav/category paths (no PDP slug). PDPs always sit at the
            # site root with at least one descriptive token in the path,
            # while categories live under known top-level systems
            # (/engine/, /suspension/, /brakes/, etc.).
            path = parts.path
            if not path or path == "/":
                continue
            if path.startswith(
                (
                    "/engine/",
                    "/suspension/",
                    "/brakes/",
                    "/drivetrain/",
                    "/exterior/",
                    "/interior/",
                    "/wheels/",
                    "/electronics/",
                    "/accessories/",
                    "/iag-parts/",
                    "/vehicles/",
                    "/brands/",
                    "/clearance/",
                    "/blog/",
                )
            ):
                continue
            clean = _strip_query(absolute)
            if clean in seen:
                continue
            seen.add(clean)
            out.append(clean)

    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse an IAG product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block. Fall back to DOM selectors
    for the rare fields the JSON-LD does not always carry (image when
    ``image`` is missing, breadcrumb when ``category`` is null).
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Prefer canonical link; strip query/UTM. BigCommerce always emits
    # link[rel=canonical] on PDPs.
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

    # Brand. IAG JSON-LD uses the dict form; defensive against the
    # bare-string form too.
    brand = _brand_name(product)
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU. IAG's ``sku`` carries a noisy storefront prefix
    # (``ds_FMKH_516160`` — BigCommerce dropship integration code),
    # while ``mpn`` carries the clean manufacturer part number
    # (``516160``). Prefer ``mpn``; fall back to ``sku`` then offer.sku.
    sku = ""
    if product and isinstance(product.get("mpn"), str):
        sku = product["mpn"].strip()
    if not sku and product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku and product and isinstance(product.get("productID"), str):
        sku = product["productID"].strip()
    if not sku:
        offer = _first_offer(product) if product else None
        if offer and isinstance(offer.get("sku"), str):
            sku = offer["sku"].strip()

    # Price. Comes from the single Offer block on every IAG PDP.
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

    # In-stock. IAG uses the schema.org URL form (``…/InStock`` /
    # ``…/OutOfStock``); substring match catches both that and the
    # bare-token alternates that BigCommerce sometimes emits.
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

    # Fitment text. IAG names embed year-range + chassis up front
    # ("COBB Titanium Catback Exhaust For 2022-24 Subaru WRX") and the
    # description carries explicit per-platform compatibility (BRZ +
    # GR86 + FR-S + Toyota 86 multi-fits are common). Feed both to the
    # fitment tiers.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. IAG's JSON-LD doesn't populate ``category``; use the
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

    # Model: IAG names lead with the brand+part-type token ("COBB
    # Titanium Catback Exhaust"). Strip a leading year-range prefix if
    # the storefront ever inverts the order.
    model = re.sub(r"^\d{4}(?:[-+]\d{0,4})?\s+", "", name).strip()
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
