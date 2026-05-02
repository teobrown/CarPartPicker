"""AmericanMuscle vendor parsers.

AmericanMuscle (https://www.americanmuscle.com) is the second vendor wired up
after FCP Euro. They are a Ford Mustang specialist, so adding them gives us
broad coverage of every Mustang generation from Fox-body through S650.

Like FCP Euro, AmericanMuscle serves fully-rendered HTML with a JSON-LD
``Product`` block on every product detail page, so the primary parsing path
mirrors ``fcp_euro.py``: locate the ``application/ld+json`` ``Product`` node
and pull name/brand/sku/price/image/availability from it.

Notes / caveats:
- Category pages list each product in an ``<li class="product_container">``;
  the first absolute ``href`` in that block points at the product detail
  page (URL pattern: ``/<slug>.html`` directly off the host).
- Fitment is encoded inline in the H1 as ``<span class="fitment">(05-09
  Mustang GT)</span>``. We pull that out plus the JSON-LD ``description``
  for ``fitment_text`` so the regex parser in ``fitment_parser.py`` (which
  already knows about "Mustang") can latch on.
- ``brand`` in the JSON-LD is sometimes a bare string (e.g. "SR Performance")
  rather than the schema.org ``{name: ...}`` dict — handle both.
- AmericanMuscle's JSON-LD ``description`` is the marketing blurb, which is
  long but typically references year ranges and trims; the H1 fitment span
  is the most reliable terse fitment hint, so we put it first.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from scraper.normalized import NormalizedPart

VENDOR_SLUG = "americanmuscle"
BASE_HOST = "https://www.americanmuscle.com"
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
    """Return absolute product detail URLs from an AmericanMuscle category page.

    Each product card is wrapped in ``<li class="product_container">`` and
    contains a per-card JSON-LD ``Product`` block whose ``url`` field is the
    canonical product detail URL. We use that as the primary path because
    AmericanMuscle's customer-facing PDP anchor lives inside a ``<noscript>``
    fallback that some HTML pre-processors strip.

    Fallback paths: per-card ``<noscript>`` anchor, then any host-root
    ``/<slug>.html`` anchors anywhere in the card.
    """
    tree = HTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for li in tree.css("li.product_container"):
        url = _extract_card_pdp_url(li, base_url=base_url)
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _extract_card_pdp_url(li, *, base_url: str) -> Optional[str]:
    """Pull the product detail URL out of a single product card."""
    # Primary: per-card JSON-LD <script type=application/ld+json>.
    for s in li.css("script[type='application/ld+json']"):
        txt = (s.text() or "").strip()
        if '"Product"' not in txt:
            continue
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            continue
        node = data
        if isinstance(data, list):
            node = next(
                (n for n in data if isinstance(n, dict) and n.get("@type") == "Product"),
                None,
            )
        if isinstance(node, dict):
            url = node.get("url")
            if isinstance(url, str) and url.strip():
                cleaned = _validate_pdp_url(url, base_url=base_url)
                if cleaned:
                    return cleaned
    # Fallback: any anchor inside the card pointing at a host-root .html PDP.
    # Includes the <noscript> branch when it survives the page rendering.
    for a in li.css("a"):
        href = a.attributes.get("href")
        if not href:
            continue
        cleaned = _validate_pdp_url(href, base_url=base_url)
        if cleaned:
            return cleaned
    return None


def _validate_pdp_url(href: str, *, base_url: str) -> Optional[str]:
    """Resolve a card link to a clean absolute PDP URL, or return None.

    AmericanMuscle PDPs all sit at ``https://www.americanmuscle.com/<slug>.html``
    (single path segment). Reject category pages, save-for-later URLs, etc.
    """
    absolute = urljoin(base_url, href.strip())
    if not absolute.startswith(BASE_HOST + "/"):
        return None
    path = urlsplit(absolute).path
    if not path.endswith(".html"):
        return None
    if path.count("/") != 1:
        return None
    return _strip_query(absolute)


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    """Parse an AmericanMuscle product detail page into a NormalizedPart.

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
            # H1 contains the marketing name plus a <span class="fitment">…</span>
            # plus a "Find parts that fit my vehicle" link. Strip them.
            for span in h1.css(".fitment, .find_more_button"):
                span.decompose()
            name = h1.text(strip=True)
    if not name:
        return None

    # Brand. JSON-LD may carry a bare string OR a {name: ...} dict.
    brand = ""
    if product:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = (b.get("name") or "").strip()
        elif isinstance(b, str):
            brand = b.strip()
    if not brand:
        # Breadcrumb-derived brand fallback (rare).
        crumb = tree.css_first(".breadcrumb a, nav.breadcrumb a")
        if crumb:
            brand = crumb.text(strip=True)
    if not brand:
        brand = _guess_brand_from_name(name)

    # SKU.
    sku = ""
    if product and isinstance(product.get("sku"), str):
        sku = product["sku"].strip()
    if not sku and product and isinstance(product.get("mpn"), str):
        sku = product["mpn"].strip()
    if not sku:
        sku_el = tree.css_first("[data-sku]")
        if sku_el:
            sku = (sku_el.attributes.get("data-sku") or "").strip()

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
    if image_url is None:
        img_el = tree.css_first("img.product-image") or tree.css_first(".product-photo img")
        if img_el:
            image_url = img_el.attributes.get("src") or img_el.attributes.get("data-src")

    # Fitment text. The H1 fitment span is the terse, reliable hint
    # (e.g. "(05-09 Mustang GT)"). The JSON-LD description is verbose
    # marketing copy that nonetheless usually carries year ranges. We
    # concatenate both so the regex parser has plenty to match against.
    fitment_parts: list[str] = []
    fit_el = tree.css_first("h1 .fitment")
    if fit_el:
        # Drop nested anchors ("Find parts that fit my vehicle").
        for a in fit_el.css("a"):
            a.decompose()
        terse = fit_el.text(strip=True)
        if terse:
            fitment_parts.append(terse)
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(fitment_parts).strip()

    # Category hint: prefer JSON-LD category if it's a string, else the
    # last leaf of the breadcrumb. The orchestrator uses a per-seed slug
    # override so this is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css(".breadcrumb a, nav.breadcrumb a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(tail)

    # Model: bare best-effort. AmericanMuscle names look like
    # "SR Performance Aluminum Cold Air Intake; Polished (05-09 Mustang GT)".
    # The "(...)" suffix is fitment, so strip it for the model field.
    model = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()

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
    raise NotImplementedError("wired up via orchestrator.run_vendor_live")
