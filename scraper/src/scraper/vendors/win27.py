"""27WON Performance vendor parsers.

27WON Performance (https://store.27won.com) is a Honda Civic specialist —
their sweet spot is the 2022+ Civic Si (FE1) and the FK8 / FL5 Type R, with
broader Civic / Integra Type S coverage. Adding them rounds out our Honda
coverage on the Si side, since PRL Motorsports skews Type R.

The storefront runs on **CS-Cart** (NOT Shopify), so URL conventions, DOM
selectors, and the "PDP listing" flow all differ from PRL / RSD / FCP /
AmericanMuscle:

- Category pages are chassis-organized: ``/civic-si-11th-gen/``,
  ``/civic-type-r-10th-gen/``, ``/integra-type-s-5th-gen-2023/`` — there
  is no per-part-category listing (no ``/intakes/`` etc.). Each chassis
  page renders ~15 product cards as ``a.product-title`` links to PDPs.
- PDP URLs end in ``.html`` (e.g. ``/2022-civic-integra-1-5t-turbocharger-upgrade.html``).
- Every PDP carries a ``Product`` JSON-LD block alongside a separate
  ``BreadcrumbList`` block. The ``Product`` block has ``name``, ``sku``,
  ``image``, ``description``, and an ``AggregateOffer`` ``offers`` payload
  with ``price``, ``priceCurrency``, ``availability`` (schema.org URL).
  ``brand`` is **not** populated — we fall back to "27WON" since it's the
  in-house brand for everything they sell.

Module name caveat: Python identifiers cannot start with a digit, so this
module is named ``win27`` (not ``27won``). The vendor slug used in the DB
and seeded vendor row is still ``27won``.

Notes / caveats:
- The chassis-only category structure means we can't anchor a part-category
  slug to a single category URL the way we do for PRL / RSD. Instead, the
  orchestrator seeds chassis URLs and falls back to ``category_hint``-based
  fuzzy matching using each product's BreadcrumbList tail. For the small
  curated catalog (~50-100 SKUs) this is fine — most products name their
  category in the title (e.g. "Turbocharger Upgrade", "Intake System").
- Honda parts often fit multiple platforms (FK8 + FL5 + Integra Type S, or
  Si + non-Si 1.5T). We feed the full description into ``fitment_text``.
- The DOM SKU block (``.ty-product-block__sku``) prefixes "CODE:" before
  the SKU — JSON-LD ``sku`` is the cleaner source.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "27won"
BASE_HOST = "https://store.27won.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")
DEFAULT_BRAND = "27WON"


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_jsonld_blocks(tree: HTMLParser) -> list[Any]:
    """Parse every <script type='application/ld+json'> block into Python."""
    out: list[Any] = []
    for s in tree.css("script[type='application/ld+json']"):
        txt = (s.text() or "").strip()
        if not txt:
            continue
        try:
            out.append(json.loads(txt))
        except json.JSONDecodeError:
            continue
    return out


def _find_product(blocks: list[Any]) -> Optional[dict[str, Any]]:
    """Find the first ``@type=Product`` dict across all JSON-LD blocks."""
    for b in blocks:
        if isinstance(b, dict):
            if b.get("@type") == "Product":
                return b
            for node in b.get("@graph", []) or []:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        elif isinstance(b, list):
            for node in b:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
    return None


def _find_breadcrumb_tail(blocks: list[Any]) -> str:
    """Return the leaf-most BreadcrumbList item name (last positioned entry).

    27WON's BreadcrumbList runs Home -> All Products -> <product name>, so
    the tail is the product itself (which is too noisy for category mapping).
    We return the last *non-product-name* item we can find — usually the
    "All Products" / chassis label — so the orchestrator's fuzzy mapper has
    a stable hint string. Most CS-Cart deployments include a deeper crumb,
    27WON's happens to be shallow; that's fine since we lean on per-seed
    slug overrides for the live scrape.
    """
    for b in blocks:
        candidates = [b] if isinstance(b, dict) else (b if isinstance(b, list) else [])
        for node in candidates:
            if not isinstance(node, dict):
                continue
            if node.get("@type") != "BreadcrumbList":
                continue
            items = node.get("itemListElement") or []
            names = [
                (it.get("name") or "").strip()
                for it in items
                if isinstance(it, dict)
            ]
            # Drop "Home" (always position 1) and the trailing product name.
            mid = [n for n in names[1:-1] if n]
            if mid:
                return " > ".join(mid)
    return ""


def _first_offer(product: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return the headline offer.

    27WON uses ``AggregateOffer`` with a top-level ``price`` field plus a
    nested ``offers`` array (one per variant). The top-level fields are the
    authoritative price + availability for the default variant — return the
    AggregateOffer dict itself so callers can read ``price`` directly.
    """
    offers = product.get("offers")
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else None
    return None


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from a 27WON chassis page.

    CS-Cart category pages render product cards server-side as
    ``a.product-title`` anchors pointing at ``/<slug>.html`` PDPs on the
    same host. No JS rendering / Shopify Analytics blob to worry about.
    """
    out: list[str] = []
    seen: set[str] = set()
    tree = HTMLParser(html)

    # Primary selector: CS-Cart's grid-list product card title link.
    for a in tree.css("a.product-title"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        if not absolute.endswith(".html"):
            continue
        # Constrain to same host so we don't follow off-site cross-sells.
        if urlsplit(absolute).netloc != urlsplit(BASE_HOST).netloc:
            continue
        clean = _strip_query(absolute)
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)

    # Fallback: ``.ty-grid-list__item-name a`` (alternate CS-Cart grid theme).
    if not out:
        for a in tree.css(".ty-grid-list__item-name a"):
            href = a.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(base_url, href.strip())
            if not absolute.endswith(".html"):
                continue
            if urlsplit(absolute).netloc != urlsplit(BASE_HOST).netloc:
                continue
            clean = _strip_query(absolute)
            if clean in seen:
                continue
            seen.add(clean)
            out.append(clean)

    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse a 27WON product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block (always present on 27WON PDPs).
    Fall back to DOM selectors for fields the JSON-LD does not carry —
    notably ``brand`` (always null in their feed) and any field that the
    Product block happens to omit on a given variant.
    """
    tree = HTMLParser(html)
    blocks = _extract_jsonld_blocks(tree)
    product = _find_product(blocks)

    # Canonical URL — strip query/UTM. CS-Cart canonicals are clean ``.html``.
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
        h1 = tree.css_first("h1.ut2-pb__title") or tree.css_first("h1")
        if h1:
            name = h1.text(strip=True)
    if not name:
        return None

    # Brand. 27WON's JSON-LD doesn't populate brand. Everything in the store
    # is in-house 27WON product, so default to that and only fall back if we
    # somehow encounter a non-27WON name (defensive — none seen in recon).
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        # DOM fallback — itemprop=brand is rare on CS-Cart but check.
        brand_el = tree.css_first("[itemprop='brand']")
        if brand_el:
            brand = brand_el.text(strip=True) or (
                brand_el.attributes.get("content") or ""
            ).strip()
    if not brand:
        brand = DEFAULT_BRAND

    # SKU. JSON-LD ``sku`` is clean; DOM ``.ty-product-block__sku`` is
    # prefixed with "CODE:" which we strip if we have to fall through.
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku:
        sku_el = tree.css_first(".ty-product-block__sku") or tree.css_first(
            "[itemprop='sku']"
        )
        if sku_el:
            raw = sku_el.text(strip=True)
            # "CODE:FK8-6-571-10" -> "FK8-6-571-10"
            sku = re.sub(r"^(?:CODE|SKU|Part\s*Number)\s*:\s*", "", raw, flags=re.I)
            sku = sku.strip()

    # Price. Read AggregateOffer.price first (default variant), then offer
    # array entries, then any ``.ty-price`` text on the page.
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
        price_el = tree.css_first(".ty-price-num") or tree.css_first(".ty-price")
        if price_el:
            m = PRICE_RE.search(price_el.text())
            if m:
                price_cents = int(round(float(m.group(1).replace(",", "")) * 100))

    # In-stock. 27WON uses schema.org URL form (InStock / OutOfStock).
    in_stock = True
    if offer:
        avail = (offer.get("availability") or "").lower()
        if "outofstock" in avail or "out_of_stock" in avail or "soldout" in avail:
            in_stock = False

    # Image. JSON-LD ``image`` is the high-res CDN URL; og:image is the
    # cleanest fallback (matches the same CDN path).
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

    # Fitment text. 27WON titles already lead with the year range and
    # chassis tokens (e.g. "2017+ Civic Type R ... FK8/FL5/DE5/AccordX"),
    # and the description spells out per-platform compatibility further
    # down. Concat both so the regex parser sees clean tokens up front and
    # the LLM tier has the marketing blurb if it has to fall through.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. 27WON's BreadcrumbList is shallow (Home > All Products
    # > <product name>) so it rarely carries a useful category leaf; the
    # orchestrator's per-seed slug override is the authoritative path. We
    # still populate this so the fuzzy mapper has *something* if the seed
    # override is ever absent.
    category_hint = _find_breadcrumb_tail(blocks)

    # Model: strip a leading "<year-range> " prefix so the model field
    # carries the part-relevant phrase. 27WON uses both "2022+" and
    # "2017-2021" forms.
    model = re.sub(r"^\d{4}\+?\s+", "", name)
    model = re.sub(r"^\d{4}-\d{4}\s+", "", model).strip()
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


def scrape() -> Iterator[NormalizedPart]:
    """Live scrape entry point. Wired up via orchestrator.run_vendor_live."""
    raise NotImplementedError("wired via orchestrator")
