"""Steeda Autosports vendor parsers.

Steeda Autosports (https://www.steeda.com) is a Mustang specialist —
the deepest S550 / S650 catalog among the Ford-platform tuners we
carry, plus Bronco / F-150 / Explorer breadth on the same storefront.
Adding them supplements AmericanMuscle's Mustang coverage with the
Steeda-house engineering set (drag springs, Pro-Action shocks,
Tri-Ax shifters, Q-series chassis kits, Watts-link rear ends) that AM
doesn't carry first-party.

Storefront platform: **BigCommerce backend** (the CDN host is
``cdn11.bigcommerce.com/s-67g50tl419``) but Steeda has replaced
BigCommerce's stock category renderer with a **Searchspring**
(``snapui.searchspring.io/3thnkg``) JS widget. As a consequence the
``/<year>-mustang-<system>`` URLs are pure navigation hubs in the
server-rendered HTML — no product cards, no anchor list, just the
chrome links and a Searchspring init script. Visible products are
populated client-side from
``api.searchspring.net/api/search/search.json?siteId=3thnkg``.

To stay aligned with the IAG / FCP / RSD / FM seed-list pattern we
**replace category-page HTML scraping with Searchspring API calls**.
``parse_category_page`` accepts either JSON text (Searchspring native
response) or HTML (defensive fallback that scans anchor href shapes).
PDPs themselves are server-rendered with two JSON-LD ``Product``
blocks — the BigCommerce default and a Steeda-custom URL-encoded one
— and the BigCommerce default carries the clean fields we need
(name / sku / mpn / brand / image / offers).

URL conventions:
- Category pages (in the human nav): flat ``/<year>-mustang-<system>``
  (e.g. ``/2024-mustang-suspension``) — but **the API path is what we
  actually scrape**, keyed on the ``categories_hierarchy`` facet
  (``Mustang>2024-2026 Mustang>Suspension``).
- PDPs: flat ``/<slug>`` at the site root, sometimes with a trailing
  ``.html`` (legacy) and sometimes without. Examples:
  ``/steeda-555-8231-s550-drag-springs``,
  ``/steeda-s550-mustang-pro-action-shocks-struts-kit-555-8157.html``.

Notes / caveats:
- ``brand`` is the schema.org dict form
  (``{"@type": "Brand", "name": "Steeda Autosports"}`` for
  Steeda-house parts, ``{"@type": "Brand", "name": "Mishimoto"}`` /
  ``"Roush"`` / ``"Corsa"`` for resold parts). We also handle the
  bare-string form defensively.
- ``sku`` carries a noisy "075 " or "531 " prefix on resold parts
  (Steeda's internal supplier code) plus an embedded space
  (``"555 8231"``); ``mpn`` carries the clean dashed manufacturer
  part number (``"555-8231"``). Prefer ``mpn``.
- Catalog is mostly Mustang but mixes F-150 / Bronco / Explorer
  products. Downstream make-name heuristics in compat.ts handle the
  per-vehicle demotion.
- Multi-trim PDPs ("GT/V6/EcoBoost", "GT/Mach 1", "S550/S650") are
  the norm, so the description carries every trim/year token. We
  feed both name and description into ``fitment_text`` so the regex
  + LLM tiers can latch onto every chassis the part fits.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "steeda"
BASE_HOST = "https://www.steeda.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _is_searchspring_payload(text: str) -> bool:
    """Cheap sniff: Searchspring native JSON starts with ``{`` and has
    the ``pagination`` + ``results`` keys early in the payload. We only
    need a yes/no answer here — if it parses as JSON and looks like a
    Searchspring response, route through the JSON path; otherwise fall
    back to HTML anchor scraping.
    """
    head = text[:200].lstrip()
    if not head.startswith("{"):
        return False
    return '"pagination"' in text[:2000] and '"results"' in text[:4000]


def _parse_category_jsonl(text: str) -> list[str]:
    """Extract product URLs from a Searchspring native-format JSON
    response. Each result has a ``url`` field that's a site-relative
    path (``/steeda-555-8231-s550-drag-springs``); we resolve to the
    Steeda host and strip query strings.
    """
    out: list[str] = []
    seen: set[str] = set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return out
    results = data.get("results")
    if not isinstance(results, list):
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        href = r.get("url")
        if not isinstance(href, str) or not href:
            continue
        absolute = urljoin(BASE_HOST + "/", href.strip())
        clean = _strip_query(absolute)
        # Stay on the Steeda host (defensive — Searchspring always
        # emits site-relative paths but a future config change could
        # bake in absolute URLs).
        parts = urlsplit(clean)
        if parts.netloc and "steeda.com" not in parts.netloc:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the JSON-LD ``Product`` block on a Steeda PDP.

    Steeda PDPs emit two JSON-LD ``Product`` blocks back to back —
    the BigCommerce stock template (clean fields, plain description)
    and a Steeda-custom block (URL-encoded description, slightly
    different ``brand`` shape). Either parses cleanly, but the BC
    stock block is a hair cleaner so we accept the first ``Product``
    we find. Defensive against ``@graph`` wrappers and array-shaped
    payloads.
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
    """Pull the brand name out of the JSON-LD payload. Steeda's
    ``Product.brand`` is the schema.org dict form on every PDP; the
    bare-string fallback is defensive.
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
    """Return absolute product detail URLs from a Steeda category response.

    Two routes:

    1. **Searchspring JSON** (primary). The orchestrator fetches
       ``api.searchspring.net/api/search/search.json?siteId=3thnkg``
       with ``filter.categories_hierarchy=...`` and passes the response
       text in here. We parse the ``results[].url`` field directly.

    2. **HTML anchor scrape** (defensive fallback). If a future
       template change ever server-renders product cards, the
       ``.card-title a`` selector would catch them — same pattern as
       IAG / FCP / RSD. Today this falls back to filtering anchor
       hrefs that look product-shaped (no leading ``/<year>-``,
       ``/<chassis>-``, ``/blog``, etc., and at least three dashes
       in the slug indicating a part name).
    """
    if _is_searchspring_payload(html):
        return _parse_category_jsonl(html)

    # Fallback: HTML anchor scrape. Today's storefront returns navigation
    # chrome only, so this path will normally yield 0 URLs — but it
    # keeps the parser resilient to a future server-render switch.
    out: list[str] = []
    seen: set[str] = set()
    tree = HTMLParser(html)
    for sel in ["h4.card-title a", ".card-title a", "a.product_img_link"]:
        for a in tree.css(sel):
            href = a.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(base_url, href.strip())
            parts = urlsplit(absolute)
            if parts.netloc and "steeda.com" not in parts.netloc:
                continue
            path = parts.path or ""
            if not path or path == "/":
                continue
            # Drop category / chassis / chrome paths. Steeda category
            # pages are flat (``/2024-mustang-suspension``) and start
            # with a year or generation token; PDPs don't.
            head = path.lstrip("/").split("/")[0]
            if re.match(
                r"^(19\d\d|20\d\d|s5\d0|s6\d0|sn95|fox|new-edge|mustang|f-150|"
                r"bronco|bronco-sport|escape|explorer|focus|fusion|fiesta|"
                r"mach-e|maverick|ranger|super-duty|blog|cdn|page|about|"
                r"contact|customer|account|cart|checkout|return|privacy|"
                r"sale|help|whats|legal|sitemap|installation|dealers|"
                r"financing|tuning|all|clearance-overstock|compare|"
                r"newsletter|open-box|special-offers|steeda-)",
                head,
            ):
                continue
            clean = _strip_query(absolute)
            if clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse a Steeda product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block (BigCommerce stock
    template). Fall back to DOM selectors only for the rare fields
    JSON-LD doesn't always carry (image when ``image`` is missing,
    breadcrumb when ``category`` is null).
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

    # Brand — JSON-LD dict form on every Steeda PDP. Fall back to a
    # leading-token heuristic if the storefront ever flips to bare
    # strings (defensive).
    brand = _brand_name(product)
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU. ``sku`` carries a "075 ", "531 ", or "555 " supplier
    # prefix and an embedded space (``"555 8231"``); ``mpn`` is the
    # clean dashed manufacturer part number (``"555-8231"``). Prefer
    # ``mpn``; fall back to ``sku`` then ``offer.sku``. We strip
    # leading whitespace defensively.
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

    # Price. JSON-LD ``offers.price`` is a string on every Steeda PDP.
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

    # In-stock. Steeda emits both the schema.org URL form
    # (``https://schema.org/InStock``) and the bare ``InStock`` token
    # depending on which JSON-LD block we pick first; substring match
    # catches both.
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

    # Fitment text. Steeda names lead with the brand+model+trim+years
    # ("Steeda Mustang GT Drag Springs - Linear (2015-2026)") and the
    # description repeats every trim/chassis (S550, S650, GT, EcoBoost,
    # V6, Mach 1, etc.). Feed both to the fitment tiers.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. JSON-LD doesn't populate ``category`` on Steeda;
    # fall back to the breadcrumb. The orchestrator uses a per-seed
    # slug override so this is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css("nav.breadcrumb a, .breadcrumb a, .breadcrumbs a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(t for t in tail if t)

    # Model: Steeda names lead with the brand+model token ("Steeda
    # Mustang GT Drag Springs"). Strip a leading year-range prefix if
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
