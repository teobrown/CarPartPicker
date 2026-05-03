"""MAPerformance vendor parsers.

MAPerformance (https://www.maperformance.com) is a multi-platform tuner
shop with the broadest **Toyota GR Corolla** catalog on the market
(~280 SKUs) and full **GR86** / **Subaru WRX-STI** / **Mitsubishi Evo**
coverage on the side. Adding them closes the GR Corolla zero-coverage
gap and supplements the GR86 / Subaru sets that RallySport Direct only
half-fills.

MAP is a Shopify storefront fronted by Cloudflare. Like Flyin' Miata /
PRL Motorsports / RallySport Direct, every PDP carries JSON-LD blocks
with the standard schema.org fields — but unlike those vendors, MAP
emits a **``ProductGroup``** as the primary node (multiple Shopify
variants per product), with each variant exposed under ``hasVariant``
as an inline ``Product`` carrying its own ``sku``/``mpn``/``offers``.
We pick the ``ProductGroup``'s name/brand/image/description and
reach into the first variant for ``sku`` and price.

Rate limiting: MAP returns 429 fast on ``/products.json``. The
orchestrator pacing for MAP is bumped to 1.5s/req (vs 1.0s for other
vendors) to stay safe — see ``_live_scrape_maperformance``.

URL conventions:
- Category pages: MAP exposes both ``/pages/<vehicle>-parts-...``
  vehicle hubs and ``/search?q=<keyword>&type=product`` keyword searches.
  The keyword search consistently returns more visible product cards
  per page (~48 vs ~8 on the vehicle hub), so we anchor the seed list
  on search URLs.
- Product detail pages: ``/products/<handle>``

Notes / caveats:
- The seeded ``baseUrl`` is the **www-prefixed** form
  (``https://www.maperformance.com``). MAP's canonical link already
  matches, so no host coercion needed.
- ``ProductGroup.name`` is the marketing title and ``ProductGroup.brand``
  is the dict form (``{"@type": "Brand", "name": "AWE Tuning"}``). The
  in-house line ships under brand ``"MAPerformance"``.
- SKU is on each variant. We pick the first variant's ``sku``; if
  missing, fall back to ``ProductGroup.productID`` (which mirrors the
  variant SKU on every page we've seen).
- ``offers`` is a **list** under each variant (one Offer per region
  configuration); we take the first.
- Multi-platform fitment: a single PDP might fit Subaru BRZ + Toyota
  GR86 + Scion FR-S simultaneously. We feed name + description into
  ``fitment_text`` so every chassis token is visible to the regex/LLM
  fitment tiers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "maperformance"
BASE_HOST = "https://www.maperformance.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _parse_jsonld_blocks(tree: HTMLParser) -> list[Any]:
    """Parse every JSON-LD <script> block on the page, ignoring decode errors."""
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


def _extract_product_group(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find the primary ``ProductGroup`` (or ``Product``) node on a PDP.

    MAP emits a ``ProductGroup`` as the primary product node, with
    Shopify variants nested under ``hasVariant``. Some simpler PDPs
    might emit a bare ``Product`` instead — we handle either. When
    multiple ``Product``-typed schemas appear (the briefing flagged
    this), we prefer ``ProductGroup`` and otherwise pick the first
    ``Product`` with the highest offer count.
    """
    blocks = _parse_jsonld_blocks(tree)
    candidates_pg: list[dict[str, Any]] = []
    candidates_p: list[dict[str, Any]] = []

    def _consider(node: Any) -> None:
        if not isinstance(node, dict):
            return
        t = node.get("@type")
        if t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t):
            candidates_pg.append(node)
        elif t == "Product" or (isinstance(t, list) and "Product" in t):
            candidates_p.append(node)

    for data in blocks:
        if isinstance(data, list):
            for node in data:
                _consider(node)
        elif isinstance(data, dict):
            _consider(data)
            for node in data.get("@graph", []) or []:
                _consider(node)

    if candidates_pg:
        return candidates_pg[0]
    if candidates_p:
        # Pick the Product with the most offers (the "main" one), falling
        # back to the first.
        def _offer_count(p: dict[str, Any]) -> int:
            offers = p.get("offers")
            if isinstance(offers, list):
                return len(offers)
            if isinstance(offers, dict):
                return int(offers.get("offerCount") or 1)
            return 0
        candidates_p.sort(key=_offer_count, reverse=True)
        return candidates_p[0]
    return None


def _first_variant(product_group: dict[str, Any]) -> Optional[dict[str, Any]]:
    hv = product_group.get("hasVariant")
    if isinstance(hv, list) and hv and isinstance(hv[0], dict):
        return hv[0]
    return None


def _first_offer(product_or_variant: dict[str, Any]) -> Optional[dict[str, Any]]:
    offers = product_or_variant.get("offers")
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else None
    if isinstance(offers, dict):
        return offers
    return None


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from a MAP category/search page.

    MAP renders product cards on both ``/pages/<vehicle>-parts-...`` hubs
    and ``/search?q=...&type=product`` results as plain anchor tags
    pointing at ``/products/<handle>``. We anchor-scrape, canonicalize,
    and de-duplicate.
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
    """Parse a MAP product detail page into a NormalizedPart.

    Primary path: ``ProductGroup`` JSON-LD (with first variant for SKU
    and price). Falls back to a bare ``Product`` block for the rare
    PDPs that don't ship a variant array.
    """
    tree = HTMLParser(html)
    product = _extract_product_group(tree)

    # Prefer canonical link; strip query/UTM. MAP's canonical is the
    # www-prefixed apex that already matches the seeded vendor.baseUrl.
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

    # Brand. MAP JSON-LD uses the dict form.
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU (prefer first-variant sku, then ProductGroup.productID, then mpn).
    sku = ""
    variant = _first_variant(product) if product else None
    if variant and isinstance(variant.get("sku"), str):
        sku = variant["sku"].strip()
    if not sku and product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku and product and isinstance(product.get("productID"), str):
        sku = product["productID"].strip()
    if not sku and variant and isinstance(variant.get("mpn"), str):
        sku = variant["mpn"].strip()

    # Price comes from the first variant's first offer.
    price_cents: Optional[int] = None
    offer = None
    if variant:
        offer = _first_offer(variant)
    if offer is None and product:
        offer = _first_offer(product)
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

    # In-stock. MAP uses the schema.org URL form (e.g. https://schema.org/InStock).
    in_stock = True
    if offer:
        avail = (offer.get("availability") or "").lower()
        if "outofstock" in avail or "out_of_stock" in avail or "soldout" in avail:
            in_stock = False

    # Image. Prefer ProductGroup.image (list-of-CDN-URLs on every PDP we've
    # seen); fall back to first variant image, then meta[og:image].
    image_url: Optional[str] = None
    for src in (product, variant):
        if not src:
            continue
        img = src.get("image")
        if isinstance(img, str):
            image_url = img
            break
        if isinstance(img, list) and img:
            if isinstance(img[0], str):
                image_url = img[0]
                break
    if image_url and image_url.startswith("/"):
        image_url = urljoin(BASE_HOST, image_url)
    if image_url is None:
        og = tree.css_first("meta[property='og:image']")
        if og:
            image_url = (og.attributes.get("content") or None)

    # Fitment text. MAP names embed year + chassis ("2023+ GR Corolla",
    # "2013-2024 Subaru BRZ / Toyota GR86 / Scion FR-S"); the description
    # repeats and expands. Feed both to the fitment tiers.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    if variant and isinstance(variant.get("description"), str):
        # Variant description is usually identical, but skip empties / dupes.
        v_desc = variant["description"].strip()
        if v_desc and v_desc not in fitment_parts:
            fitment_parts.append(v_desc)
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. ProductGroup doesn't populate `category`; check the
    # variant, then the breadcrumb. Orchestrator uses a per-seed slug
    # override so this is informational only.
    category_hint = ""
    if variant and isinstance(variant.get("category"), str):
        category_hint = variant["category"].strip()
    if not category_hint and product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css("nav.breadcrumb a, .breadcrumb a, .breadcrumbs a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(t for t in tail if t)

    # Model: MAP names typically lead with the brand or part-type token
    # ("AWE Track Edition Exhaust"); strip a leading year-range prefix if
    # the storefront ever inverts it.
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
