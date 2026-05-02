from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Iterable
import httpx
from scraper.db import connect
from scraper.upsert import upsert_part
from scraper.fitment_parser import parse_fitment
from scraper.category_map import map_category
from scraper.normalized import NormalizedPart
from scraper.vendors import fcp_euro

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


def run_vendor_live(vendor_slug: str) -> int:
    if vendor_slug != "fcp-euro":
        raise ValueError(f"unknown vendor: {vendor_slug}")
    parts = asyncio.run(_live_scrape_fcp_euro())
    return _process_and_upsert(parts)
