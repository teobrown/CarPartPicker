"""PRL Motorsports vendor parsers.

PRL Motorsports (https://www.prlmotorsports.com) is a Honda specialist —
their sweet spot is the Civic Type R (FK8 / FL5) and Civic Si (FE1 / 10th
gen 1.5T), with broader Honda/Acura coverage. Adding them closes the
zero-coverage gap on Honda Civic platforms in our catalog.

PRL is a Shopify storefront. Like FCP Euro / RallySport Direct, every PDP
carries a JSON-LD ``Product`` block (often two — we take the first match
that has the richer offers payload). Category (collection) pages are
JS-rendered: only ~6 anchor links to product pages appear in the static
HTML (header / footer / recommendations), but the full product listing is
embedded in a ``var meta = {...};`` blob that Shopify Analytics injects.
We parse that blob to pull product handles for the seeded categories.

URL conventions:
- Category (collection) pages: ``/collections/<slug>``
- Product detail pages: ``/products/<handle>``

Hostname caveat: the storefront's canonical link uses the bare apex
``prlmotorsports.com`` (the www host 301s to bare). We coerce all stored
vendor_urls back to the ``www.`` form so they match the vendor row's
``baseUrl`` and pass the /go redirector hostname check.

Notes / caveats:
- ``brand`` is the schema.org dict form (``{"@type": "Brand", "name":
  "PRL Motorsports"}`` for in-house parts).
- Availability is encoded BOTH as a schema.org URL and as a bare
  ``OutOfStock`` token across the two JSON-LD blocks. The first Product
  block is the authoritative one (carries productID, gtin, full offer).
- Honda parts often fit multiple platforms (Civic Type R FK8 + Type R FL5
  + Acura Integra Type S DE5, or Civic Si + 1.5T non-Si). We feed the
  full description into ``fitment_text`` so the LLM/regex extractors get
  every year/chassis token.
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

VENDOR_SLUG = "prl-motorsports"
BASE_HOST = "https://www.prlmotorsports.com"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")
# Shopify Analytics injects ``var meta = { products: [...], page: {...} };``
# in a script tag near the top of category pages. The closing token is
# ``};`` followed by a newline; the JSON itself never contains an unescaped
# ``};\n`` so a non-greedy match is safe.
META_BLOB_RE = re.compile(r"var meta = (\{.*?\});\n", re.DOTALL)


def _coerce_www(url: str) -> str:
    """Force the www. host on prlmotorsports.com URLs so vendor_url matches
    the seeded ``baseUrl`` (https://www.prlmotorsports.com). The site 301s
    www.→apex but both serve identical content; we store the www form
    because the /go redirector validates target hostname equality against
    baseUrl."""
    if not url:
        return url
    parts = urlsplit(url)
    if parts.netloc == "prlmotorsports.com":
        parts = parts._replace(netloc="www.prlmotorsports.com")
        return urlunsplit(parts)
    return url


def _strip_query(url: str) -> str:
    """Drop query/fragment for canonicalization (variant query, UTM, etc.)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_product_jsonld(tree: HTMLParser) -> Optional[dict[str, Any]]:
    """Find and parse the first JSON-LD <script> block of @type=Product.

    PRL pages typically carry two Product blocks: the first is the rich
    Shopify-emitted payload (productID, gtin, mpn, priceValidUntil,
    availability as schema.org URL), the second is a sparser app-emitted
    one with aggregateRating. The first match wins because its offer is
    the authoritative price + availability source.
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


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product detail URLs from a PRL collection page.

    PRL's category pages are JS-rendered: only ~6 anchor links to PDPs
    appear in the static HTML (header / footer / cross-sell). The full
    paginated listing is embedded in a ``var meta = { products: [...],
    page: {...} };`` blob injected for Shopify Analytics. We parse the
    blob and map each product's ``handle`` to its canonical PDP URL.
    """
    out: list[str] = []
    seen: set[str] = set()

    # Primary path: the meta JSON blob carries every product on the page.
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
                url = _coerce_www(urljoin(base_url, f"/products/{handle}"))
                if url in seen:
                    continue
                seen.add(url)
                out.append(url)

    # Fallback: pick up any anchor-rendered PDPs (rare on PRL, but keeps
    # the parser robust if Shopify changes how the meta blob is named).
    tree = HTMLParser(html)
    for a in tree.css("a[href*='/products/']"):
        href = a.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        absolute = _coerce_www(absolute)
        path = urlsplit(absolute).path
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
    """Parse a PRL product detail page into a NormalizedPart.

    Primary path: JSON-LD ``Product`` block. Fall back to DOM selectors
    for fields the JSON-LD does not always carry.
    """
    tree = HTMLParser(html)
    product = _extract_product_jsonld(tree)

    # Prefer canonical link; coerce to www host; strip query/UTM.
    canonical_url = url
    canon_el = tree.css_first("link[rel='canonical']")
    if canon_el:
        href = canon_el.attributes.get("href")
        if href:
            canonical_url = href.strip()
    canonical_url = _coerce_www(_strip_query(canonical_url))

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

    # Brand. PRL JSON-LD uses the dict form.
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

    # In-stock. PRL uses both schema.org URL and bare-token forms across
    # its two JSON-LD blocks; substring match catches both.
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

    # Fitment text. Honda parts often fit multiple platforms (e.g. Type R
    # FK8 + FL5 + Integra Type S, or Si + non-Si 1.5T) so we keep BOTH the
    # name (year range + chassis up front) AND the description (lists
    # explicit per-year compatibility) as fitment input. This gives the
    # regex parser its cleanest signal first and the LLM tier the full
    # marketing blurb when it has to fall through.
    fitment_parts: list[str] = [name]
    if product and isinstance(product.get("description"), str):
        fitment_parts.append(product["description"].strip())
    fitment_text = "\n".join(p for p in fitment_parts if p).strip()

    # Category hint. PRL JSON-LD doesn't populate `category` (always None
    # on the samples I've seen), so we try the breadcrumb. The orchestrator
    # uses a per-seed slug override so this is informational only.
    category_hint = ""
    if product and isinstance(product.get("category"), str):
        category_hint = product["category"].strip()
    if not category_hint:
        crumb_els = tree.css("nav.breadcrumb a, .breadcrumb a, .breadcrumbs a")
        if crumb_els:
            tail = [c.text(strip=True) for c in crumb_els[-3:] if c.text(strip=True)]
            category_hint = " > ".join(t for t in tail if t)

    # Model: PRL names are like "2017-2021 Honda Civic Type-R FK8 Stage 1
    # Intake System". Strip a leading "<year-range> " prefix so the model
    # field carries the part-relevant phrase without year noise.
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
