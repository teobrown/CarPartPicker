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
from scraper.category_classifier import classify_heuristic
from scraper.normalized import NormalizedPart
from scraper.vendors import (
    fcp_euro,
    americanmuscle,
    rallysport_direct,
    prl_motorsports,
    win27,
    flyin_miata,
    maperformance,
    iag_performance,
    steeda,
    motorsport034,
    k_tuned,
    skunk2,
)

log = logging.getLogger(__name__)
USER_AGENT = "CarbuildrBot/0.1 (+mailto:teobrown1@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "From": "teobrown1@gmail.com"}


async def _fetch_with_429_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    backoff_seconds: float = 15.0,
) -> httpx.Response | None:
    """GET ``url`` with one sleep+retry on a 429 response.

    Returns the final ``Response`` (which may itself be 429 or other
    non-200) or ``None`` if both attempts raised an ``httpx.HTTPError``.
    Caller still inspects ``status_code`` and decides whether to keep
    or skip the result.

    Why this exists: vendor sites sporadically 429 single product URLs
    even at our normal pacing (sub-domain rate limit, anti-bot probes).
    A single 15s nap clears most of these. Persistent 429s still get
    skipped per the existing per-URL tolerance.
    """
    try:
        r = await client.get(url)
    except httpx.HTTPError:
        log.exception("product fetch failed: %s", url)
        return None
    if r.status_code != 429:
        return r
    log.info("429 from %s — sleeping %.1fs before retry", url, backoff_seconds)
    await asyncio.sleep(backoff_seconds)
    try:
        return await client.get(url)
    except httpx.HTTPError:
        log.exception("product fetch retry failed: %s", url)
        return None


def _process_and_upsert(
    parts: Iterable[tuple[NormalizedPart, str | None] | NormalizedPart],
) -> int:
    """Upsert an iterable of parts. Each entry can be either a bare
    ``NormalizedPart`` (use the fuzzy ``category_hint`` mapper) or a
    ``(part, slug_override)`` tuple (use ``slug_override`` as a soft prior).

    Category resolution order (per part):

    1. Run the heuristic classifier on the part's own name+brand. If a
       rule matches, that wins — the classifier sees what the part is,
       and a category-page seed slug can't override that. This protects
       us from broad-search seeds (e.g. K-Tuned ``/collections/shifters``
       → ``ecu-tune``, Skunk2 ``civic+si`` → ``cold-air-intake``) that
       carried mixed inventory and would otherwise mislabel everything
       in their bucket.
    2. If the heuristic misses, fall back to ``slug_override`` (the
       seed's claimed category) as a soft default.
    3. If there's no override either, fall back to ``map_category()``
       on the vendor's category breadcrumb hint.
    4. Drop the part if nothing landed.

    The maintenance reclassifier (``scraper.reclassify``) runs the LLM
    stage afterwards to mop up parts where the heuristic missed and
    the override was wrong — that's the second line of defense.
    """
    # Materialize once so we can short-circuit when a vendor scrape
    # returned zero products (e.g. Steeda anti-bot 403'd every PDP).
    # No point opening a DB connection just to immediately close it.
    parts_list = list(parts)
    if not parts_list:
        log.info("no parts to upsert — skipping DB connection")
        return 0

    n = 0
    with connect() as conn:
        for entry in parts_list:
            if isinstance(entry, tuple):
                p, slug_override = entry
            else:
                p, slug_override = entry, None
            # Heuristic on the part itself wins over a category-page seed slug.
            slug = classify_heuristic(p.name, p.brand, slug_override)
            if slug is None:
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
    elif vendor_slug == "flyin-miata":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = flyin_miata.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "maperformance":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = maperformance.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "iag-performance":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = iag_performance.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "steeda":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = steeda.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "034motorsport":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = motorsport034.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "k-tuned":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = k_tuned.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    elif vendor_slug == "skunk2":
        for f in sorted(fixtures_dir.glob("product_*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = skunk2.parse_product_page(html, url=f"file://{f}")
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
    ("https://www.fcpeuro.com/Volkswagen-parts/Air-Intake/", "cold-air-intake"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Catback-Exhaust/", "catback-exhaust"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Muffler/", "muffler-delete"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Intercooler/", "intercooler"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Coilovers/", "coilovers"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Wheels/", "wheels"),
    ("https://www.fcpeuro.com/Volkswagen-parts/Spoiler/", "spoiler-wing"),
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
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
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
    ("https://www.americanmuscle.com/cold-air-intakes.html", "cold-air-intake"),
    ("https://www.americanmuscle.com/aftermarket-performance-exhaust.html", "catback-exhaust"),
    ("https://www.americanmuscle.com/aftermarket-performance-racing-mufflers.html", "muffler-delete"),
    ("https://www.americanmuscle.com/aftermarket-performance-racing-intercoolers.html", "intercooler"),
    ("https://www.americanmuscle.com/aftermarket-shocks-struts.html", "coilovers"),
    ("https://www.americanmuscle.com/aftermarket-headlights.html", "headlights"),
    ("https://www.americanmuscle.com/aftermarket-muscle-car-tail-lights.html", "taillights"),
    ("https://www.americanmuscle.com/aftermarket-rear-spoilers-wings.html", "spoiler-wing"),
]


async def _live_scrape_americanmuscle(
    *, max_products_per_category: int = 50
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
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
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
    ("https://www.rallysportdirect.com/collections/cold-air-intakes", "cold-air-intake"),
    ("https://www.rallysportdirect.com/collections/cat-back-exhaust-system", "catback-exhaust"),
    ("https://www.rallysportdirect.com/collections/axle-back-exhausts", "axleback-exhaust"),
    ("https://www.rallysportdirect.com/collections/cobb-tuning-accessports", "ecu-tune"),
    ("https://www.rallysportdirect.com/collections/downpipes-and-y-pipes", "downpipe"),
    ("https://www.rallysportdirect.com/collections/intercoolers", "intercooler"),
    ("https://www.rallysportdirect.com/collections/blow-off-valves", "bov"),
    ("https://www.rallysportdirect.com/collections/coilovers", "coilovers"),
    ("https://www.rallysportdirect.com/collections/lowering-springs", "lowering-springs"),
    ("https://www.rallysportdirect.com/collections/sway-bars", "sway-bars"),
    ("https://www.rallysportdirect.com/collections/wheels", "wheels"),
    ("https://www.rallysportdirect.com/collections/front-lips", "front-lip"),
    ("https://www.rallysportdirect.com/collections/spoilers-and-wings", "spoiler-wing"),
]


async def _live_scrape_rallysport_direct(
    *, max_products_per_category: int = 50
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
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
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
    ("https://www.prlmotorsports.com/collections/intake", "cold-air-intake"),
    ("https://www.prlmotorsports.com/collections/exhaust", "catback-exhaust"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-intercoolers-charge-pipes", "intercooler"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-coilovers", "coilovers"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-lowering-springs", "lowering-springs"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-sway-bars-end-links", "sway-bars"),
    ("https://www.prlmotorsports.com/collections/collection-vendor-wings-spoilers", "spoiler-wing"),
    # Civic Si deepening — probed 2026-05-03, yields confirmed:
    #   air-filters-accessories  -> 31 products
    #   chassis-braces           -> 10 products
    #   aerodynamics             -> 14 products (lips/splitters/diffusers)
    #   brakes-components        -> 22 products (pads/rotors/lines/BBKs)
    # Defaults below are lenient; the post-scrape reclassifier (--target-slug)
    # routes individual products to the right leaf via name regex + LLM.
    ("https://www.prlmotorsports.com/collections/collection-vendor-air-filters-accessories", "air-filter"),
    ("https://www.prlmotorsports.com/collections/chassis-braces", "strut-bar"),
    ("https://www.prlmotorsports.com/collections/aerodynamics", "front-lip"),
    ("https://www.prlmotorsports.com/collections/brakes-components", "big-brake-kit"),
]


async def _live_scrape_prl_motorsports(
    *, max_products_per_category: int = 50
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
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
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
    (("axle-back", "axleback"), "axleback-exhaust"),
    (("downpipe", "down pipe", "down-pipe"), "downpipe"),
    (("cat-back", "catback", "cat back", "front-pipe back exhaust", "valved exhaust", "exhaust system"), "catback-exhaust"),
    # Intake variants. "Snorkel" sits in the intake family on 27WON.
    (("cold air intake", "cai", "air intake", "intake system", "intake snorkel", "sri upgrade"), "cold-air-intake"),
    # Charge-air. FMIC / "front mount intercooler" / "intercooler".
    (("intercooler", "fmic"), "intercooler"),
    # Bypass / blow-off / diverter valve.
    (("bypass valve", "blow off valve", "blow-off valve", "diverter valve", "bpv", "bov"), "bov"),
    # Suspension.
    (("coilover",), "coilovers"),
    (("lowering spring", "lowering springs"), "lowering-springs"),
    (("sway bar", "swaybar", "anti-roll bar"), "sway-bars"),
    # Tuning. 27WON resells Hondata fuel system upgrades + reflashes; map
    # those onto the new "ecu-tune" slug.
    (("hondata", "ecu tune", "flash tuner", "ecu reflash"), "ecu-tune"),
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
    *, max_products_per_category: int = 50
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
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
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


# Flyin' Miata Mazda MX-5 category seed list. FM is a Shopify storefront
# (`/collections/<chassis>-<system>[-<sub>]` for category pages,
# `/products/<handle>` for PDPs) — the entire catalog is fitted to NA / NB
# / NC / ND chassis, so we seed per-chassis sub-collections that cleanly
# map to a single internal slug. We deliberately skip mixed bins like
# `*-handling-springs-shocks-swaybars` (springs + shocks + swaybars in one
# collection — would need name-keyword routing to disambiguate) and
# `*-body-lighting` (head + tail + turn signal lights together).
#
# Probe results (anchor count, FM's ``var meta`` blob is empty so this is
# the per-page visible product count, not the full collection size):
#   na/nb/nc/nd-handling-coilovers  -> 11 / 9  / 2 / 2  (coilovers)
#   na/nb/nc/nd-powertrain-exhaust  -> 16 / 16 / 8 / 10 (catback)
#   na/nb/nc/nd-powertrain-intake   -> 8  / 4  / 1 / 2  (intake)
#   na/nb/nc/nd-wheels              -> 16 / 16 / 11/ 15 (wheels)
FLYIN_MIATA_SEED_CATEGORIES: list[tuple[str, str]] = [
    # NA (1990-1997)
    ("https://flyinmiata.com/collections/na-handling-coilovers", "coilovers"),
    ("https://flyinmiata.com/collections/na-powertrain-exhaust", "catback-exhaust"),
    ("https://flyinmiata.com/collections/na-powertrain-intake", "cold-air-intake"),
    ("https://flyinmiata.com/collections/na-wheels", "wheels"),
    # NB (1999-2005)
    ("https://flyinmiata.com/collections/nb-handling-coilovers", "coilovers"),
    ("https://flyinmiata.com/collections/nb-powertrain-exhaust", "catback-exhaust"),
    ("https://flyinmiata.com/collections/nb-powertrain-intake", "cold-air-intake"),
    ("https://flyinmiata.com/collections/nb-wheels", "wheels"),
    # NC (2006-2015)
    ("https://flyinmiata.com/collections/nc-handling-coilovers", "coilovers"),
    ("https://flyinmiata.com/collections/nc-powertrain-exhaust", "catback-exhaust"),
    ("https://flyinmiata.com/collections/nc-powertrain-intake", "cold-air-intake"),
    ("https://flyinmiata.com/collections/nc-wheels", "wheels"),
    # ND (2016-now)
    ("https://flyinmiata.com/collections/nd-handling-coilovers", "coilovers"),
    ("https://flyinmiata.com/collections/nd-powertrain-exhaust", "catback-exhaust"),
    ("https://flyinmiata.com/collections/nd-powertrain-intake", "cold-air-intake"),
    ("https://flyinmiata.com/collections/nd-wheels", "wheels"),
]


async def _live_scrape_flyin_miata(
    *, max_products_per_category: int = 50
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape Flyin' Miata's seeded NA/NB/NC/ND categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in FLYIN_MIATA_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = flyin_miata.parse_category_page(
                r.text, base_url="https://flyinmiata.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = flyin_miata.parse_product_page(pr.text, url=u)
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


# MAPerformance multi-platform seed list. MAP is a Shopify storefront
# (`/products/<handle>` for PDPs) with no clean per-category collection
# URL convention — instead they expose ``/search?q=<keyword>&type=product``
# keyword searches that consistently return 25-48 visible product cards
# per page (vs ~8 on the per-vehicle ``/pages/<vehicle>-parts-...`` hubs).
# We anchor each seed on a search URL pinned to a part-category slug,
# matching the FCP / RSD / FM seed pattern.
#
# Probe results (verified 2026-04-30, anchor-scrape unique product hrefs):
#   gr+corolla+intake      -> 40
#   gr+corolla+exhaust     -> 48
#   gr+corolla+coilover    -> 35
#   gr+corolla+intercooler -> 27
#   gr86+intake            -> 48
#   wrx+intake             -> 429s reliably (probe and 2026-05-02 live
#                             run both got banned on this category;
#                             dropped to keep the run from blanket-429'ing
#                             after a partial harvest). Subaru WRX
#                             coverage comes from RallySport-Direct + IAG.
#
# RATE LIMIT: MAP returns 429 quickly on `/products.json` and on rapid
# search requests. ``_live_scrape_maperformance`` uses a 3.0s per-request
# sleep (vs 1.0s for every other vendor) — bumped from 1.5s after the
# 2026-05-01 run was blanket-429'd. Don't lower without re-probing.
MAPERFORMANCE_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.maperformance.com/search?q=gr+corolla+intake&type=product", "cold-air-intake"),
    ("https://www.maperformance.com/search?q=gr+corolla+exhaust&type=product", "catback-exhaust"),
    ("https://www.maperformance.com/search?q=gr+corolla+coilover&type=product", "coilovers"),
    ("https://www.maperformance.com/search?q=gr+corolla+intercooler&type=product", "intercooler"),
    ("https://www.maperformance.com/search?q=gr86+intake&type=product", "cold-air-intake"),
]


async def _live_scrape_maperformance(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape MAPerformance's seeded multi-platform searches.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under.

    NOTE: MAP rate-limits aggressively (429 on `/products.json`, ~1 req/sec
    cap on category searches). We use a 3.0s per-request sleep — bumped
    from 1.5s after a 429 blanket-ban during the 2026-05-01 first run.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in MAPERFORMANCE_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = maperformance.parse_category_page(
                r.text, base_url="https://www.maperformance.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(3.0)  # MAP-specific bump (other vendors: 1.0s); 1.5s blanket-429'd on 2026-05-01
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = maperformance.parse_product_page(pr.text, url=u)
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


# IAG Performance Subaru-deep category seed list. IAG is a BigCommerce
# Stencil storefront (`/<system>/<sub>[/<sub>]/` for category pages) and
# the deepest WRX/STI/BRZ-fit catalog on the market — pairing COBB's
# full house catalog (catbacks, tuners, BPVs) with IAG-house engine
# internals + AOS systems that RallySport Direct doesn't carry. This
# seed list deepens Subaru coverage and adds engine-build SKUs to the
# catalog for the first time.
#
# Probe results (verified 2026-04-30, post-card-title selector):
#   /engine/exhausts/cat-back/                           -> 30
#   /engine/exhausts/axle-back/                          -> 29
#   /engine/exhausts/downpipes-j-pipes/                  -> 11
#   /engine/air-induction/air-intakes-hoses/             -> 40
#   /engine/cooling/intercoolers/                        -> 30
#   /engine/engine-management/tuners/                    -> 16
#   /engine/turbos-superchargers/blow-off-valves/        -> 30
#   /suspension/height-adjustment/coilovers/             -> 30
#   /suspension/suspension-linkage/sway-bars/            -> 30
IAG_PERFORMANCE_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.iagperformance.com/engine/exhausts/cat-back/", "catback-exhaust"),
    ("https://www.iagperformance.com/engine/exhausts/axle-back/", "axleback-exhaust"),
    ("https://www.iagperformance.com/engine/exhausts/downpipes-j-pipes/", "downpipe"),
    ("https://www.iagperformance.com/engine/air-induction/air-intakes-hoses/", "cold-air-intake"),
    ("https://www.iagperformance.com/engine/cooling/intercoolers/", "intercooler"),
    ("https://www.iagperformance.com/engine/engine-management/tuners/", "ecu-tune"),
    ("https://www.iagperformance.com/engine/turbos-superchargers/blow-off-valves/", "bov"),
    ("https://www.iagperformance.com/suspension/height-adjustment/coilovers/", "coilovers"),
    ("https://www.iagperformance.com/suspension/suspension-linkage/sway-bars/", "sway-bars"),
]


async def _live_scrape_iag_performance(
    *, max_products_per_category: int = 50
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape IAG's seeded Subaru-deep categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes from
    the seed-list entry the product was discovered under. IAG accepts our
    bot UA without challenge and has no Cloudflare/anti-bot layer, so the
    standard 1.0s per-request pacing is sufficient.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in IAG_PERFORMANCE_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = iag_performance.parse_category_page(
                r.text, base_url="https://www.iagperformance.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = iag_performance.parse_product_page(pr.text, url=u)
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


# Steeda Autosports Mustang-deep category seed list. Steeda's storefront
# is BigCommerce-backed (CDN host ``cdn11.bigcommerce.com/s-67g50tl419``)
# but they've replaced the stock category renderer with a **Searchspring**
# JS widget — the human-facing ``/<year>-mustang-<system>`` URLs are
# pure navigation hubs in the server-rendered HTML, with no product
# anchors to scrape. Visible products are loaded client-side from
# ``api.searchspring.net/api/search/search.json?siteId=3thnkg``.
#
# Seed list keys each entry to a Searchspring API URL pinned to a
# ``filter.categories_hierarchy=<path>`` value (encoded), where the
# hierarchy path matches the human nav (Mustang > generation > system
# > sub-system). PDPs themselves are server-rendered with the standard
# BigCommerce JSON-LD ``Product`` block, so once we have the URL list
# we follow the same per-PDP fetch pattern as IAG / FCP / RSD.
#
# Probe results (verified 2026-04-30 via Searchspring totalResults):
#   2024-2026 Mustang > Exhaust > Cat-Back Exhaust         -> 106
#   2024-2026 Mustang > Exhaust > Axle-Back Exhaust        -> 57
#   2024-2026 Mustang > Induction                          -> 54  (no
#       useful sub-cat; "Cold Air Intake" sub doesn't exist for S650
#       yet, so seed the parent.)
#   2024-2026 Mustang > Suspension > Lowering Springs      -> 21
#   2024-2026 Mustang > Suspension > Shocks & Struts       -> 34
#   2015-2023 Mustang > Exhaust > Cat-Back Exhuast (sic)   -> 168
#       (Steeda's S550 cat-back leaf category has a typo —
#       "Exhuast" — that we have to mirror exactly or the filter
#       returns 0.)
#   2015-2023 Mustang > Exhaust > Axle-Back Exhaust        -> 94
#   2015-2023 Mustang > Induction > Cold Air Intake        -> 65
#   2015-2023 Mustang > Suspension > Coilovers             -> 56
#   2015-2023 Mustang > Suspension > Lowering Springs      -> 60
#
# NOTE: Steeda's catalog mixes Ford platforms (Mustang / F-150 /
# Bronco / Explorer). Seeding only Mustang>... avoids cross-platform
# noise. AmericanMuscle covers the same ground at a much wider catalog
# breadth; Steeda supplements with the Steeda-house engineering line
# (Pro-Action, Tri-Ax, Q-series, drag springs) AM doesn't carry first
# party.
_STEEDA_SS_BASE = (
    "https://api.searchspring.net/api/search/search.json"
    "?siteId=3thnkg&resultsFormat=native&resultsPerPage=100"
)


def _steeda_seed(category_path: str) -> str:
    """Build a Searchspring API URL filtered to one Steeda category
    hierarchy path. The path is the human breadcrumb joined with
    ``>`` — e.g. ``"Mustang>2024-2026 Mustang>Exhaust>Cat-Back Exhaust"``.
    """
    from urllib.parse import quote

    return f"{_STEEDA_SS_BASE}&filter.categories_hierarchy={quote(category_path)}"


STEEDA_SEED_CATEGORIES: list[tuple[str, str]] = [
    # S650 (2024-2026 Mustang)
    (_steeda_seed("Mustang>2024-2026 Mustang>Exhaust>Cat-Back Exhaust"), "catback-exhaust"),
    (_steeda_seed("Mustang>2024-2026 Mustang>Exhaust>Axle-Back Exhaust"), "axleback-exhaust"),
    (_steeda_seed("Mustang>2024-2026 Mustang>Induction"), "cold-air-intake"),
    (_steeda_seed("Mustang>2024-2026 Mustang>Suspension>Lowering Springs"), "lowering-springs"),
    (_steeda_seed("Mustang>2024-2026 Mustang>Suspension>Shocks & Struts"), "coilovers"),
    # S550 (2015-2023 Mustang) — much deeper catalog. Note the typo
    # "Exhuast" in the cat-back leaf name; mirroring it exactly.
    (_steeda_seed("Mustang>2015-2023 Mustang>Exhaust>Cat-Back Exhuast"), "catback-exhaust"),
    (_steeda_seed("Mustang>2015-2023 Mustang>Exhaust>Axle-Back Exhaust"), "axleback-exhaust"),
    (_steeda_seed("Mustang>2015-2023 Mustang>Induction>Cold Air Intake"), "cold-air-intake"),
    (_steeda_seed("Mustang>2015-2023 Mustang>Suspension>Coilovers"), "coilovers"),
    (_steeda_seed("Mustang>2015-2023 Mustang>Suspension>Lowering Springs"), "lowering-springs"),
]


async def _live_scrape_steeda(
    *, max_products_per_category: int = 50
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape Steeda's seeded Mustang categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes
    from the seed-list entry the product was discovered under. Steeda
    accepts our bot UA without challenge and has no Cloudflare/anti-bot
    layer, so the standard 1.0s per-request pacing is sufficient.

    Two-step fetch per category:
    1. ``GET <searchspring-api-url>`` — returns a JSON payload with
       up to 100 ``results[].url`` entries. ``parse_category_page``
       sniffs JSON vs HTML and routes to the JSON parser.
    2. For each result URL, ``GET <pdp-url>`` and parse the JSON-LD
       ``Product`` block via ``parse_product_page``.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in STEEDA_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = steeda.parse_category_page(
                r.text, base_url="https://www.steeda.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = steeda.parse_product_page(pr.text, url=u)
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


# 034Motorsport VW/Audi-deep category seed list. 034 is a Magento 2
# storefront on ``www.034motorsport.com`` (the ``store.`` subdomain
# 302-redirects to ``www.`` for our bot UA). They are the VW/Audi
# tuner-side counterpart to FCP Euro's OEM-replacement focus —
# 034-house parts (P34 / X34 / S34 intakes, Dynamic+ ECU tunes,
# Density Line dogbone mounts, billet diff mounts, sway bars) plus
# Racingline / IE / APR-licensed reseller distribution.
#
# Storefront category structure is **very shallow**. Most candidate
# Magento-style category URLs (``/intercoolers.html``,
# ``/coilovers.html``, ``/sway-bars.html``, ``/lowering-springs.html``,
# ``/ecu-tuning.html``) return 404 — 034 organizes navigation through
# the ``/vehicles`` car-picker rather than per-system category pages.
# Only a handful of top-level category pages exist. Probed each
# candidate against the Wayback Machine 2024 snapshot (live IP banned
# during recon — 034 has CloudFront-fronted bot-detection that
# challenges sustained traffic with reCAPTCHA):
#   /cold-air-intakes.html         -> 24 products (intake)
#   /exhaust-upgrades.html         -> 16 products (catless downpipes,
#       res-deletes, midpipes — closest map is ``downpipe``; not a
#       true catback bucket).
#   /chassis-mounts.html           -> 24 products (motor / dogbone /
#       diff mounts — none of the 18 supported categories cover
#       motor mounts, so this seed is intentionally omitted).
#   /control-arm-kits.html         -> 24 products (ditto — no slug).
#   /springs-sway-bars.html        -> 24 products (mixed bin —
#       lowering springs + sway bars in one collection; would need
#       name-keyword routing à la 27WON to disambiguate. Omitted in
#       this first cut; revisit if the catalog needs deeper coverage.).
#   /universal-parts.html          -> 19 products (non-fitment-bound
#       hardware — dogbone bushings, magnetic plugs, wheel nuts —
#       outside our 18-category scope).
#
# Result: only **2 seed categories** map cleanly to our slug set,
# yielding an estimated 40 SKUs per scrape. This is materially smaller
# than IAG / Steeda but the 034-house engineering line is a unique
# catalog supplement — every product is a 034-engineered VW/Audi
# performance part not available through FCP Euro's OEM-replacement
# inventory.
MOTORSPORT034_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.034motorsport.com/cold-air-intakes.html", "cold-air-intake"),
    # Exhaust-upgrades is dominated by Res-X resonator deletes and
    # cast-stainless racing catalyst (catless downpipe-class) parts,
    # not true catbacks. Mapping to ``downpipe`` is the closest fit
    # in our slug set.
    ("https://www.034motorsport.com/exhaust-upgrades.html", "downpipe"),
]


async def _live_scrape_034motorsport(
    *, max_products_per_category: int = 25
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape 034Motorsport's seeded VW/Audi categories.

    Returns a list of ``(part, target_slug)`` tuples. The slug comes
    from the seed-list entry the product was discovered under. 034 has
    a CloudFront-fronted reCAPTCHA challenge layer that fires on
    sustained bot traffic; we use the standard 1.0s per-request pacing
    and tolerate per-URL failures so a transient 403 doesn't cascade.
    """
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in MOTORSPORT034_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = motorsport034.parse_category_page(
                r.text, base_url="https://www.034motorsport.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = motorsport034.parse_product_page(pr.text, url=u)
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


# K-Tuned — Honda K-series specialist. Shopify storefront, same shape as
# PRL — every collection page carries a ``var meta`` analytics blob with the
# full product list. Probed yields (2026-05-03):
#   coilovers              -> 24
#   springs                -> ~12
#   shifters               -> ~25 (mostly RSX / 8th-9th gen Civic)
#   coolant-housing        -> ~10
#   chassis-braces         -> ~8
# Categories with /products/ in the static HTML count as 0 — those pages
# rely on Shopify analytics + var-meta for the listing.
K_TUNED_SEED_CATEGORIES: list[tuple[str, str]] = [
    ("https://www.k-tuned.com/collections/coilovers", "coilovers"),
    ("https://www.k-tuned.com/collections/springs", "lowering-springs"),
    ("https://www.k-tuned.com/collections/shifters", "ecu-tune"),
    ("https://www.k-tuned.com/collections/cooling-system", "intercooler"),
    ("https://www.k-tuned.com/collections/intake-system", "cold-air-intake"),
    ("https://www.k-tuned.com/collections/exhaust", "catback-exhaust"),
    ("https://www.k-tuned.com/collections/chassis-braces", "strut-bar"),
    ("https://www.k-tuned.com/collections/sway-bars", "sway-bars"),
    ("https://www.k-tuned.com/collections/11th-gen-civic-22", "cold-air-intake"),
]


async def _live_scrape_k_tuned(
    *, max_products_per_category: int = 50
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape K-Tuned's seeded Honda categories. Same shape as
    `_live_scrape_prl_motorsports`. The slug_override is a soft prior
    only — `_process_and_upsert` runs the heuristic classifier on each
    product first, and the post-scrape reclassifier (LLM stage) mops up
    anything the heuristic missed."""
    out: list[tuple[NormalizedPart, str]] = []
    fetched = 0
    parse_misses = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url, slug in K_TUNED_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = k_tuned.parse_category_page(
                r.text, base_url="https://www.k-tuned.com"
            )
            log.info("%s [-> %s]: %d product URLs found", cat_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = k_tuned.parse_product_page(pr.text, url=u)
                fetched += 1
                if p:
                    out.append((p, slug))
                else:
                    parse_misses += 1
                    log.warning("k-tuned parse miss: %s", u)
                if fetched % 25 == 0:
                    log.info("progress: %d products from %d categories (%d parse misses)",
                             fetched, cats_done + 1, parse_misses)
            cats_done += 1
    log.info(
        "scrape done: %d products from %d categories (%d parse misses)",
        fetched, cats_done, parse_misses,
    )
    return out


# Skunk2 — Honda specialist (intake manifolds, headers, Civic Si bolt-ons,
# alpha CAI). Magento storefront with no Shopify-style meta blob and no
# JSON-LD on PDPs. Discovery uses the search-result page which exposes
# ~80 product .html anchors per query in static HTML. We seed by car
# platform + part type so each search returns a clean batch.
SKUNK2_SEARCH_QUERIES: list[tuple[str, str]] = [
    ("civic+si",            "cold-air-intake"),
    ("civic+si+exhaust",    "catback-exhaust"),
    ("civic+si+header",     "front-pipe"),
    ("civic+si+manifold",   "intake-manifold"),
    ("civic+si+coilover",   "coilovers"),
    ("civic+si+springs",    "lowering-springs"),
    ("civic+type+r",        "cold-air-intake"),
    ("integra",             "intake-manifold"),
]


async def _live_scrape_skunk2(
    *, max_products_per_category: int = 40
) -> list[tuple[NormalizedPart, str]]:
    """Live-scrape Skunk2 via the search-result listing. Each query is one
    seed; the slug_override is a soft prior only — `_process_and_upsert`
    runs the heuristic classifier on each product, so a part discovered
    via a broad search (e.g. ``civic+si``) doesn't get permanently
    bucketed into the broad-search default leaf."""
    out: list[tuple[NormalizedPart, str]] = []
    seen: set[str] = set()
    fetched = 0
    parse_misses = 0
    cats_done = 0
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for query, slug in SKUNK2_SEARCH_QUERIES:
            search_url = (
                f"https://www.skunk2.com/catalogsearch/result/?q={query}"
            )
            try:
                r = await client.get(search_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("search fetch failed: %s", search_url)
                continue
            urls = skunk2.parse_category_page(
                r.text, base_url="https://www.skunk2.com"
            )
            # Dedup across queries — a single Civic Si manifold shows up under
            # both "civic si" and "civic si manifold" searches. Safe now that
            # category resolution runs per-product on the part itself, not
            # off the seed slug.
            urls = [u for u in urls if u not in seen]
            seen.update(urls)
            log.info("%s [-> %s]: %d new product URLs", search_url, slug, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)
                pr = await _fetch_with_429_retry(client, u)
                if pr is None:
                    continue
                if pr.status_code != 200:
                    log.warning("product %s returned status %s", u, pr.status_code)
                    continue
                p = skunk2.parse_product_page(pr.text, url=u)
                fetched += 1
                if p:
                    out.append((p, slug))
                else:
                    parse_misses += 1
                    log.warning("skunk2 parse miss: %s", u)
                if fetched % 25 == 0:
                    log.info("progress: %d products from %d searches (%d parse misses)",
                             fetched, cats_done + 1, parse_misses)
            cats_done += 1
    log.info(
        "scrape done: %d products from %d searches (%d parse misses)",
        fetched, cats_done, parse_misses,
    )
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
    elif vendor_slug == "flyin-miata":
        parts = asyncio.run(_live_scrape_flyin_miata())
    elif vendor_slug == "maperformance":
        parts = asyncio.run(_live_scrape_maperformance())
    elif vendor_slug == "iag-performance":
        parts = asyncio.run(_live_scrape_iag_performance())
    elif vendor_slug == "steeda":
        parts = asyncio.run(_live_scrape_steeda())
    elif vendor_slug == "034motorsport":
        parts = asyncio.run(_live_scrape_034motorsport())
    elif vendor_slug == "k-tuned":
        parts = asyncio.run(_live_scrape_k_tuned())
    elif vendor_slug == "skunk2":
        parts = asyncio.run(_live_scrape_skunk2())
    else:
        raise ValueError(f"unknown vendor: {vendor_slug}")
    return _process_and_upsert(parts)
