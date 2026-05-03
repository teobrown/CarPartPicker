"""034Motorsport vendor parsers.

034Motorsport (https://www.034motorsport.com) is a VW/Audi tuner-side
specialist — the engineering/aftermarket counterpart to FCP Euro's
OEM-replacement focus. Their catalog spans 034-house performance parts
(intakes, throttle bodies, dogbone mounts, billet diff mounts, sway
bars, ECU tunes) plus reseller distribution for IE, APR-licensed
software, Racingline, etc. They appear repeatedly in our existing FCP
Euro descriptions ("034Motorsport Performance Intercooler Kit") so we
know the catalog overlap is exactly the demand-driven market we want
to serve.

Storefront platform: **Magento 2** on the ``www.034motorsport.com``
host. Note the recon-time ``store.034motorsport.com`` subdomain
issues a 302 redirect to ``www.`` for the bot UA, so the canonical
host (and the host every JSON-LD/canonical-link field uses) is
``www.034motorsport.com``. PDPs themselves are server-rendered with
a single JSON-LD ``Product`` block carrying name / sku / brand (dict
form) / model / description / offers — clean schema.org with a few
quirks specific to 034:

1. ``sku`` sometimes carries a trailing slash
   (``"034-108-5012/"`` for the B9 turbo inlet). We strip it.
2. ``brand`` is the dict form
   (``{"@type": "Brand", "name": "034Motorsport"}``) on every PDP
   we've seen. Bare-string fallback is defensive only.
3. ``offers`` ships in **two shapes** depending on whether the PDP
   has variants:
   - Single-variant PDPs (e.g. P34 MQB intake): ``offers`` is a
     dict with ``@type: Offer`` and a top-level ``price`` field.
   - Multi-variant PDPs (e.g. B9 turbo inlet — black vs. raw
     finish): ``offers`` is a dict with ``@type: AggregateOffer``,
     ``lowPrice`` / ``highPrice`` fields, and a nested ``offers``
     array of individual ``Offer`` dicts. We pick the first.

URL conventions:
- Category pages: flat ``/<slug>.html`` at the site root
  (``/cold-air-intakes.html``, ``/exhaust-upgrades.html``,
  ``/springs-sway-bars.html``). 034 has a *very* shallow category
  structure — only a handful of top-level category pages exist;
  most navigation is funneled through the ``/vehicles`` car-picker
  rather than per-system category pages. Most candidate URLs
  (``/intercoolers.html``, ``/coilovers.html``, ``/sway-bars.html``)
  return 404; the orchestrator probes each candidate and only seeds
  ones that actually exist.
- PDPs: flat ``/<slug>.html`` at the site root with the brand prefix
  embedded in the slug (``/034motorsport-...``, ``/x34-...``,
  ``/p34-...``, ``/s34-...``). Mostly Audi/VW fitment, with a small
  BMW segment and a universal-parts catch-all.

Notes / caveats:
- Category card selector is the standard Magento 2 stencil:
  ``a.product-item-link`` (text anchor on the card title).
- Multi-platform PDPs are the norm — a single MQB intake fits 8V
  Audi A3/S3, 8S TT/TTS, MkVII VW Golf/GTI/R, MkVII VW Jetta/GLI all
  at once. We feed both name and description into ``fitment_text``
  so the regex + LLM tiers can extract every chassis token.
- 034 hosts ship with a CloudFront-based bot-detection layer that
  serves a reCAPTCHA challenge after sustained traffic from a single
  IP. Live scraping must respect 1.0s pacing and tolerate per-URL
  failures.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "034motorsport"
BASE_HOST = "https://www.034motorsport.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the JSON-LD ``Product`` block on a 034 PDP.

    034's Magento template emits a single JSON-LD ``Product`` block per
    PDP carrying name / sku / brand (dict form) / model / description
    / offers. Defensive against ``@graph`` wrappers and array-shaped
    payloads even though 034's stock template uses neither.
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
    """Pick the first concrete ``Offer`` from a 034 ``Product.offers``.

    034's ``offers`` ships in two shapes:
    - Single-variant PDPs: ``offers`` is a single ``Offer`` dict
      with a top-level ``price`` field.
    - Multi-variant PDPs: ``offers`` is an ``AggregateOffer`` dict
      with a nested ``offers`` array of individual ``Offer`` dicts;
      we pick the first.

    Returns ``None`` only when no concrete offer is reachable
    (defensive — we've not seen a 034 PDP without offers).
    """
    offers = product.get("offers")
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else None
    if isinstance(offers, dict):
        if offers.get("@type") == "AggregateOffer":
            sub = offers.get("offers")
            if isinstance(sub, list) and sub and isinstance(sub[0], dict):
                return sub[0]
            # Fallback: return the AggregateOffer itself (lowPrice path).
            return offers
        return offers
    return None


def _aggregate_low_price(product: dict[str, Any]) -> Optional[str]:
    """If ``offers`` is an AggregateOffer, return the ``lowPrice`` field
    as a string (variant pricing — represent the cheapest variant).
    Returns ``None`` for single-Offer PDPs.
    """
    offers = product.get("offers")
    if isinstance(offers, dict) and offers.get("@type") == "AggregateOffer":
        lp = offers.get("lowPrice")
        if isinstance(lp, (int, float)):
            return str(lp)
        if isinstance(lp, str):
            return lp
    return None


def _brand_name(product: Optional[dict[str, Any]]) -> str:
    """Pull the brand name out of the JSON-LD payload.

    034's ``Product.brand`` is the schema.org dict form
    (``{"@type": "Brand", "name": "034Motorsport"}``) on every PDP we've
    seen. Bare-string form is defensive — Magento themes can flip
    between dict/string based on theme version.
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
    """Return absolute product detail URLs from a 034 category page.

    034's Magento 2 template renders product cards as
    ``<li class="item product product-item">`` blocks with the title
    anchor on ``a.product-item-link``. This selector is robust to the
    common Magento variations that affect the card photo anchor.
    """
    out: list[str] = []
    seen: set[str] = set()

    tree = HTMLParser(html)

    # Primary: title anchor inside each product card. Standard Magento 2
    # selector, stable across 034's current theme.
    selectors = [
        "a.product-item-link",
        ".product-item-link",
        "a.product-item-photo",
    ]
    for sel in selectors:
        for a in tree.css(sel):
            href = a.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(base_url, href.strip())
            parts = urlsplit(absolute)
            # Stay on the 034 host — drop cross-domain anchors (CDN,
            # blog, social) that occasionally appear inside the page
            # chrome.
            if parts.netloc and "034motorsport.com" not in parts.netloc:
                continue
            path = parts.path
            if not path or path == "/":
                continue
            # Drop nav/blog/service paths that aren't PDPs. PDPs sit at
            # the site root with a flat ``.html`` slug; categories sit
            # at the same depth so we can't filter purely by depth.
            # Instead, drop the known non-PDP path prefixes.
            if path.startswith(
                (
                    "/blog/",
                    "/service/",
                    "/about-us",
                    "/contact",
                    "/dealers",
                    "/customer/",
                    "/checkout/",
                    "/cart/",
                    "/sales/",
                    "/returns/",
                    "/resources/",
                )
            ):
                continue
            if not path.endswith(".html"):
                continue
            clean = _strip_query(absolute)
            if clean in seen:
                continue
            seen.add(clean)
            out.append(clean)

    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse a 034 product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block. Fall back to DOM selectors
    for the rare fields the JSON-LD does not always carry (image when
    ``image`` is missing, breadcrumb when ``category`` is null).
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Prefer canonical link; strip query/UTM. Magento always emits
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

    # Brand. 034's JSON-LD uses the dict form on every PDP; defensive
    # against the bare-string form too.
    brand = _brand_name(product)
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU. 034's ``sku`` sometimes carries a trailing slash
    # (``"034-108-5012/"``) — strip it. Prefer top-level ``sku``;
    # fall back to ``mpn`` then ``offer.sku`` (Magento occasionally
    # only populates ``offer.sku`` on multi-variant PDPs).
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip().rstrip("/")
    if not sku and product and isinstance(product.get("mpn"), str):
        sku = product["mpn"].strip().rstrip("/")
    if not sku and product and isinstance(product.get("productID"), str):
        sku = product["productID"].strip().rstrip("/")
    if not sku:
        offer = _first_offer(product) if product else None
        if offer and isinstance(offer.get("sku"), str):
            sku = offer["sku"].strip().rstrip("/")

    # Price. 034 ships two offer shapes: single ``Offer`` (top-level
    # ``price``) or ``AggregateOffer`` (nested ``offers[0].price`` plus
    # a top-level ``lowPrice``). ``_first_offer`` returns the first
    # concrete Offer dict regardless of wrapper; we still fall back to
    # the AggregateOffer ``lowPrice`` when the nested offers list is
    # empty.
    price_cents: Optional[int] = None
    offer = _first_offer(product) if product else None
    if offer:
        raw_price = offer.get("price") or offer.get("lowPrice")
        if isinstance(raw_price, (int, float)):
            price_cents = int(round(float(raw_price) * 100))
        elif isinstance(raw_price, str):
            try:
                price_cents = int(round(float(raw_price.replace(",", "")) * 100))
            except ValueError:
                pass
    if price_cents is None and product:
        agg_low = _aggregate_low_price(product)
        if agg_low:
            try:
                price_cents = int(round(float(agg_low.replace(",", "")) * 100))
            except ValueError:
                pass
    if price_cents is None:
        price_el = tree.css_first("[class*='price']")
        if price_el:
            m = PRICE_RE.search(price_el.text())
            if m:
                price_cents = int(round(float(m.group(1).replace(",", "")) * 100))

    # In-stock. Magento emits ``schema.org/InStock`` /
    # ``schema.org/OutOfStock`` URL form by default; substring match
    # also catches the bare-token alternates.
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

    # Fitment text. 034 names embed make/model/chassis up front
    # ("P34 Performance Cold Air Intake, 8V Audi A3/S3/TT/TTS & MkVII
    # Volkswagen Golf/GTI/R, 1.8T/2.0T Gen 3 (MQB)") and the
    # description repeats every chassis/year token. Feed both to the
    # fitment tiers so multi-platform PDPs (8V/8S Audi + MkVII VW)
    # surface every fitment.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. 034's JSON-LD doesn't populate ``category``; use
    # the breadcrumb. The orchestrator uses a per-seed slug override so
    # this is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css(
            "ul.items li.item.category strong, "
            "ul.items li.item.category a, "
            ".breadcrumbs a, .breadcrumbs strong"
        )
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(t for t in tail if t)

    # Model: 034 names lead with the brand+model token. Strip a
    # leading year-range prefix if the storefront ever inverts the
    # order (defensive — we've not seen this shape on 034).
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
