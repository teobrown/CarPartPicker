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


def _process_and_upsert(parts: Iterable[NormalizedPart]) -> int:
    n = 0
    with connect() as conn:
        for p in parts:
            slug = map_category(p.category_hint) if p.category_hint else None
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


# FCP Euro category seed URLs. Kept small for Phase 0; expand later.
FCP_EURO_SEED_CATEGORIES = [
    "https://www.fcpeuro.com/Volkswagen-parts/Air-Intake/",
    "https://www.fcpeuro.com/Volkswagen-parts/Exhaust/",
    "https://www.fcpeuro.com/Volkswagen-parts/Suspension/",
    # extend as the catalog grows
]


async def _live_scrape_fcp_euro(
    *, max_products_per_category: int = 25
) -> list[NormalizedPart]:
    parts: list[NormalizedPart] = []
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=20.0, follow_redirects=True
    ) as client:
        for cat_url in FCP_EURO_SEED_CATEGORIES:
            try:
                r = await client.get(cat_url)
                r.raise_for_status()
            except httpx.HTTPError:
                log.exception("category fetch failed: %s", cat_url)
                continue
            urls = fcp_euro.parse_category_page(
                r.text, base_url="https://www.fcpeuro.com"
            )
            log.info("%s: %d product URLs found", cat_url, len(urls))
            for u in urls[:max_products_per_category]:
                await asyncio.sleep(1.0)  # ~1 req/sec rate limit
                try:
                    pr = await client.get(u)
                except httpx.HTTPError:
                    log.exception("product fetch failed: %s", u)
                    continue
                if pr.status_code != 200:
                    continue
                p = fcp_euro.parse_product_page(pr.text, url=u)
                if p:
                    parts.append(p)
    return parts


def run_vendor_live(vendor_slug: str) -> int:
    if vendor_slug != "fcp-euro":
        raise ValueError(f"unknown vendor: {vendor_slug}")
    parts = asyncio.run(_live_scrape_fcp_euro())
    return _process_and_upsert(parts)
