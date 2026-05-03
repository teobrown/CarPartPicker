from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Iterable
import httpx
from scraper.db import connect
from scraper.upsert import upsert_part
from scraper.fitment_parser import parse_fitment
from scraper.llm_fitment import parse_fitment_with_llm, extract_fitment_from_html
from scraper.category_map import map_category
from scraper.normalized import NormalizedPart
from scraper.vendors import (
    fcp_euro,
    americanmuscle,
    rallysport_direct,
    prl_motorsports,
    win27,
)

log = logging.getLogger(__name__)
USER_AGENT = "CarPartPickerBot/0.1 (+mailto:teobrown1@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "From": "teobrown1@gmail.com"}


def _process_and_upsert(
    parts: Iterable[tuple[NormalizedPart, str | None] | NormalizedPart],
) -> int:
    """Upsert an iterable of parts. Each entry can be either a bare
    ``NormalizedPart`` (use the fuzzy ``category_hint`` mapper) or a
    ``(part, slug_override)`` tuple (skip the mapper and use ``slug_override``).

    The override path is the live scraper's primary route — FCP Euro's
    JSON-LD ``category`` field only carries the top-level breadcrumb
    (e.g. "Exterior Body" for wheels/spoilers/headlights alike), so we
    can't disambiguate the leaf category from the product page. Instead,
    we anchor the slug to the seed-list URL we navigated through.
    """
    n = 0
    with connect() as conn:
        for entry in parts:
            if isinstance(entry, tuple):
                p, slug_override = entry
            else:
                p, slug_override = entry, None
            slug = slug_override
            if slug is None and p.category_hint:
                slug = map_category(p.category_hint)
            if slug is None:
                log.warning(
                    "dropping part with unmapped category: %s (part=%s)",
                    p.category_hint,
                    p.name[:80],
                )
                continue
            parsed = parse_fitment(p.fitment_text)
            if not parsed and p.fitment_text:
                # regex didn't latch — try the LLM (DeepSeek). Fails open
                # to [] so a transient API blip never blocks an upsert.
                try:
                    parsed = parse_fitment_with_llm(p.fitment_text)
                except Exception as e:
                    log.warning("llm fitment fallback failed: %s", e)
                    parsed = []
            if not parsed and p.raw_html:
                # third-tier fallback: feed the raw page to the LLM. Useful
                # when fitment_text is too thin (e.g. "Make sure this fits
                # your car") to extract anything from.
                try:
                    parsed = extract_fitment_from_html(p.raw_html)
                except Exception as e:
                    log.warning("llm html extraction failed: %s", e)
                    parsed = []
            try:
                upsert_part(conn, p, parsed_fitment=parsed, category_slug=slug)
                n += 1
            except Exception:
                log.exception("upsert failed for %s", p.vendor_url)
    return n


def run_vendor_from_fixtures(vendor_slug: str, fixtures_dir: Path) -> int:
    """Used for tests and dry runs. Reads pre-saved HTML files from disk."""
    parts: list[NormalizedPart] = []
    if vendor_slug == "fcp-euro":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = fcp_euro.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "americanmuscle":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = americanmuscle.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "rallysport-direct":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = rallysport_direct.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "prl-motorsports":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = prl_motorsports.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "27won":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = win27.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    else:
        raise ValueError(f"unknown vendor: {vendor_slug}")
    return _process_and_upsert(parts)


# FCP Euro VW category seed list. Each entry pins a category page URL to the
# internal slug we want every product on that page to land in, since the
# product-page JSON-LD `category` field only carries the top-level breadcrumb
# (e.g. "Exterior Body") and can't disambiguate wheels vs spoilers vs lights.
FCP_EURO_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.fcpeuro.com/Volkswagen-parts/Air-Intake/", "intake"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Catback-Exhaust/", "catback"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Muffler/", "muffler-delete"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Intercooler/", "intercooler"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Coilovers/", "coilovers"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Wheels/", "wheels"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Spoiler/", "spoiler"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Fender-Flare/", "fender-flares"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Headlight-Assembly/", "headlights"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Tail-Light-Assembly/", "taillights"),
]


async def _live_scrape_fcp_euro(
    *, max_products_per_category: int = 40
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape FCP Euro's seeded VW categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under, not from any
    field on the product page itself.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in FCP_EURO_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = fcp_euro.parse_category_page(
                r.text, base_url="https://www.fcpeuro.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = fcp_euro.parse_product_page(pr.text, url=u)
                if p:
                    out.append((p, slug))
                fetched += 1
                if fetched % 25 == 0:
                    log.info(
                        "progress: %d products from %d categories",
                        fetched,
                        cats_done + 1,
                    )
            cats_done += 1
    log.info("scrape done: %d products from %d categories", fetched, cats_done)
    return out


# AmericanMuscle Mustang category seed list. Each entry pins a category page
# URL to the internal slug we want every product on that page to land in.
# Mirrors the FCP Euro seed pattern: AmericanMuscle's per-product JSON-LD does
# not carry a vendor-side category we can map cleanly, and the breadcrumb
# (e.g. "Cold Air Intakes") is too narrow on some pages and too broad on
# others, so anchoring slug to the seed URL is the most reliable path.
AMERICANMUSCLE_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.americanmuscle.com/cold-air-intakes.html", "intake"),
    ("https://www.americanmuscle.com/aftermarket-performance-exhaust.html", "catback"),
    ("https://www.americanmuscle.com/aftermarket-performance-racing-mufflers.html", "muffler-delete"),
    ("https://www.americanmuscle.com/aftermarket-performance-racing-intercoolers.html", "intercooler"),
    ("https://www.americanmuscle.com/aftermarket-shocks-struts.html", "coilovers"),
    ("https://www.americanmuscle.com/aftermarket-headlights.html", "headlights"),
    ("https://www.americanmuscle.com/aftermarket-muscle-car-tail-lights.html", "taillights"),
    ("https://www.americanmuscle.com/aftermarket-rear-spoilers-wings.html", "spoiler"),
]


async def _live_scrape_americanmuscle(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape AmericanMuscle's seeded Mustang categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in AMERICANMUSCLE_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = americanmuscle.parse_category_page(
                r.text, base_url="https://www.americanmuscle.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = americanmuscle.parse_product_page(pr.text, url=u)
                if p:
                    out.append((p, slug))
                fetched += 1
                if fetched % 25 == 0:
                    log.info(
                        "progress: %d products from %d categories",
                        fetched,
                        cats_done + 1,
                    )
            cats_done += 1
    log.info("scrape done: %d products from %d categories", fetched, cats_done)
    return out


# RallySport Direct Subaru category seed list. RSD is a Shopify storefront
# (`/collections/<slug>` for category pages, `/products/<slug>` for PDPs)
# specializing in Subaru WRX / STI / BRZ / Crosstrek / Forester / Outback,
# so this list is the first set of Subaru-fit parts to land in the catalog.
RALLYSPORT_DIRECT_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.rallysportdirect.com/collections/cold-air-intakes", "intake"),
    ("https://www.rallysportdirect.com/collections/cat-back-exhaust-system", "catback"),
    ("https://www.rallysportdirect.com/collections/axle-back-exhausts", "muffler-delete"),
    ("https://www.rallysportdirect.com/collections/cobb-tuning-accessports", "tune"),
    ("https://www.rallysportdirect.com/collections/downpipes-and-y-pipes", "downpipe"),
    ("https://www.rallysportdirect.com/collections/intercoolers", "intercooler"),
    ("https://www.rallysportdirect.com/collections/blow-off-valves", "bov"),
    ("https://www.rallysportdirect.com/collections/coilovers", "coilovers"),
    ("https://www.rallysportdirect.com/collections/lowering-springs", "springs"),
    ("https://www.rallysportdirect.com/collections/sway-bars", "sway-bars"),
    ("https://www.rallysportdirect.com/collections/wheels", "wheels"),
    ("https://www.rallysportdirect.com/collections/front-lips", "lip-kit"),
    ("https://www.rallysportdirect.com/collections/spoilers-and-wings", "spoiler"),
]


async def _live_scrape_rallysport_direct(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape RSD's seeded Subaru categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in RALLYSPORT_DIRECT_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = rallysport_direct.parse_category_page(
                r.text, base_url="https://www.rallysportdirect.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = rallysport_direct.parse_product_page(pr.text, url=u)
                if p:
                    out.append((p, slug))
                fetched += 1
                if fetched % 25 == 0:
                    log.info(
                        "progress: %d products from %d categories",
                        fetched,
                        cats_done + 1,
                    )
            cats_done += 1
    log.info("scrape done: %d products from %d categories", fetched, cats_done)
    return out


# PRL Motorsports Honda category seed list. PRL is a Shopify storefront
# (`/collections/<slug>` for category pages, `/products/<handle>` for PDPs)
# specializing in Honda Civic Type R (FK8 / FL5) and Civic Si — the first
# vendor we wire up that targets that platform set, closing the Honda
# zero-coverage gap. Probed each candidate URL for product count via the
# embedded Shopify Analytics ``var meta = ...`` blob (visible cards are
# JS-rendered, so anchor scraping returns ~6 false positives per page).
# Seeds chosen for Civic-relevant volume: intake (50), exhaust (45),
# intercoolers (35), coilovers (15), springs (16), sway bars (12),
# wings/spoilers (11).
PRL_MOTORSPORTS_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.prlmotorsports.com/collections/intake", "intake"),
    ("https://www.prlmotorsports.com/collections/exhaust", "catback"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-intercoolers-charge-pipes", "intercooler"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-coilovers", "coilovers"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-lowering-springs", "springs"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-sway-bars-end-links", "sway-bars"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-wings-spoilers", "spoiler"),
]


async def _live_scrape_prl_motorsports(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape PRL's seeded Honda Civic categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in PRL_MOTORSPORTS_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = prl_motorsports.parse_category_page(
                r.text, base_url="https://www.prlmotorsports.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = prl_motorsports.parse_product_page(pr.text, url=u)
                if p:
                    out.append((p, slug))
                fetched += 1
                if fetched % 25 == 0:
                    log.info(
                        "progress: %d products from %d categories",
                        fetched,
                        cats_done + 1,
                    )
            cats_done += 1
    log.info("scrape done: %d products from %d categories", fetched, cats_done)
    return out


# 27WON Performance Honda chassis seed list. Unlike PRL/RSD, the 27WON
# storefront (CS-Cart on store.27won.com) is organized by *chassis*, not by
# part category — every chassis page lists ~15 mixed products (intakes,
# exhausts, intercoolers, brakes, turbos, motor mounts, etc.). There is no
# /intakes/ or /exhausts/ URL we can anchor a slug to. Instead, we seed the
# Civic Si / Type R / Integra Type S chassis URLs and infer the part-category
# slug from each product's name via ``_27won_slug_from_name``. Products
# whose name doesn't match any of our 18 categories (turbos, brake kits,
# motor mounts, oil caps, shift knobs) are dropped at upsert time, which is
# expected — the catalog is small (~50-100 SKUs total) and we only carry
# the 18 supported categories.
WIN27_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://store.27won.com/civic-si-11th-gen/", "civic-si-11"),
    ("https://store.27won.com/civic-si-10th-gen/", "civic-si-10"),
    ("https://store.27won.com/civic-type-r-11th-gen/", "civic-type-r-11"),
    ("https://store.27won.com/civic-type-r-10th-gen/", "civic-type-r-10"),
    ("https://store.27won.com/integra-type-s-5th-gen-2023/", "integra-type-s"),
]


# Keyword -> category slug router, ordered most-specific first. CS-Cart 27WON
# product names lead with the year/chassis tokens, so a substring match on
# the lowercased name reliably picks out the part type. Keys checked in the
# order listed; first hit wins. We deliberately omit categories like
# "turbocharger" and "brake kit" that have no slug in our 18-category map —
# returning None means the orchestrator drops the part (logged as warning),
# which is the correct behavior for catalog-fit gaps.
_WIN27_NAME_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    # Most-specific exhaust variants first (axle-back is rare on 27WON;
    # cat-back / "Front-Pipe Back" / valved exhaust are the common forms).
    (("axle-back", "axleback"), "axleback"),
    (("downpipe", "down pipe", "down-pipe"), "downpipe"),
    (("cat-back", "catback", "cat back", "front-pipe back exhaust", "valved exhaust", "exhaust system"), "catback"),
    # Intake variants. "Snorkel" sits in the intake family on 27WON.
    (("cold air intake", "cai", "air intake", "intake system", "intake snorkel", "sri upgrade"), "intake"),
    # Charge-air. FMIC / "front mount intercooler" / "intercooler".
    (("intercooler", "fmic"), "intercooler"),
    # Bypass / blow-off / diverter valve.
    (("bypass valve", "blow off valve", "blow-off valve", "diverter valve", "bpv", "bov"), "bov"),
    # Suspension.
    (("coilover",), "coilovers"),
    (("lowering spring", "lowering springs"), "springs"),
    (("sway bar", "swaybar", "anti-roll bar"), "sway-bars"),
    # Tuning. 27WON resells Hondata fuel system upgrades + reflashes; map
    # those onto our generic "tune" slug.
    (("hondata", "ecu tune", "flash tuner", "ecu reflash"), "tune"),
]


def _27won_slug_from_name(name: str) -> str | None:
    """Infer an internal category slug from a 27WON product name.

    27WON's chassis-only category structure forces us to route by name
    keyword instead of seed URL. Returns None when the product doesn't map
    to any of our 18 categories (turbos, brake kits, motor mounts, oil caps,
    strut bars, shift knobs, etc. all return None and get dropped upstream).
    """
    if not name:
        return None
    low = name.lower()
    for keywords, slug in _WIN27_NAME_KEYWORDS:
        for kw in keywords:
            if kw in low:
                return slug
    return None


async def _live_scrape_27won(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape 27WON's seeded Honda chassis pages.

    Returns a list of ``(part, target_slug)`` tuples. Unlike PRL/RSD, the
    slug is derived per-product from the product name (chassis-organized
    catalog has no per-category seed URL to anchor to). Products that don't
    match any keyword family are skipped before upsert.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    seen_urls: set[str] = set()
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, _chassis_label in WIN27_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = win27.parse_category_page(
                r.text, base_url="https://store.27won.com"
            )
            log.info("%s: %d product URLs found", cat_url, len(urls))
            for u in urls[:max_products_per_category]:
                # Same product appears across multiple chassis pages
                # (e.g. the FK8/FL5 turbo lives on 4 chassis pages); de-dupe.
                if u in seen_urls:
                    continue
                seen_urls.add(u)
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = win27.parse_product_page(pr.text, url=u)
                if not p:
                    continue
                slug = _27won_slug_from_name(p.name)
                if slug is None:
                    log.info(
                        "27won: skipping unmappable product (%s) — %s",
                        p.vendor_sku or "no-sku",
                        p.name[:80],
                    )
                    continue
                out.append((p, slug))
                fetched += 1
                if fetched % 25 == 0:
                    log.info(
                        "progress: %d products from %d chassis pages",
                        fetched,
                        cats_done + 1,
                    )
            cats_done += 1
    log.info("scrape done: %d products from %d chassis pages", fetched, cats_done)
    return out


def run_vendor_live(vendor_slug: str) -> int:
    if vendor_slug == "fcp-euro":
        parts = asyncio.run(_live_scrape_fcp_euro())
    elif vendor_slug == "americanmuscle":
        parts = asyncio.run(_live_scrape_americanmuscle())
    elif vendor_slug == "rallysport-direct":
        parts = asyncio.run(_live_scrape_rallysport_direct())
    elif vendor_slug == "prl-motorsports":
        parts = asyncio.run(_live_scrape_prl_motorsports())
    elif vendor_slug == "27won":
        parts = asyncio.run(_live_scrape_27won())
    else:
        raise ValueError(f"unknown vendor: {vendor_slug}")
    return _process_and_upsert(parts)
