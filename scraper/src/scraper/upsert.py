from __future__ import annotations
from typing import Iterable, Optional
import psycopg
from scraper.normalized import NormalizedPart
from scraper.fitment_parser import ParsedFitment


def _category_id(conn: psycopg.Connection, slug: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE slug=%s", (slug,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"category slug not seeded: {slug}")
        return row[0]


def _vendor_id(conn: psycopg.Connection, slug: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM vendors WHERE slug=%s", (slug,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"vendor slug not seeded: {slug}")
        return row[0]


def _find_existing_part(
    conn: psycopg.Connection,
    brand: str,
    model: str,
    sku: Optional[str],
    name: str,
) -> Optional[int]:
    """Locate an existing part by (brand, model, sku) when sku is given,
    otherwise (brand, model, name). Returns the part id or None."""
    with conn.cursor() as cur:
        if sku:
            cur.execute(
                "SELECT id FROM parts WHERE brand=%s AND model=%s AND sku=%s LIMIT 1",
                (brand, model, sku),
            )
        else:
            cur.execute(
                "SELECT id FROM parts WHERE brand=%s AND model=%s AND sku IS NULL AND name=%s LIMIT 1",
                (brand, model, name),
            )
        row = cur.fetchone()
        return row[0] if row else None


def upsert_part(
    conn: psycopg.Connection,
    p: NormalizedPart,
    *,
    parsed_fitment: Iterable[ParsedFitment],
    category_slug: str,
) -> int:
    """Insert/update a part + its single vendor listing + its fitment rules.

    Idempotent: a second call with the same NormalizedPart produces no
    additional rows in `parts` or `vendor_listings`, and replaces this
    vendor's `fitment_rules` for the part rather than appending.

    Returns the part id.
    """
    category_id = _category_id(conn, category_slug)
    vendor_id = _vendor_id(conn, p.vendor)
    sku = p.vendor_sku or None

    with conn.cursor() as cur:
        # parts: SELECT-first to avoid duplicates (no DB-level unique key on brand+model+sku).
        # NOTE: parts.msrp_cents is intentionally left NULL by the scraper.
        # MSRP and current vendor selling price are different things. Phase 2 will
        # populate msrp_cents from a dedicated MSRP source if/when one is available.
        # Current vendor selling price lives in vendor_listings.price_cents.
        part_id = _find_existing_part(conn, p.brand, p.model, sku, p.name)
        if part_id is None:
            cur.execute(
                """
                INSERT INTO parts (category_id, brand, model, sku, name, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    category_id,
                    p.brand,
                    p.model,
                    sku,
                    p.name,
                    p.image_url,
                ),
            )
            row = cur.fetchone()
            assert row is not None, f"INSERT ... RETURNING returned no row for {p.name}"
            part_id = row[0]
        else:
            # Refresh mutable fields on the existing part.
            cur.execute(
                """
                UPDATE parts
                SET category_id = %s,
                    name = %s,
                    image_url = COALESCE(%s, image_url)
                WHERE id = %s
                """,
                (category_id, p.name, p.image_url, part_id),
            )

        # vendor_listings: unique on (vendor_id, part_id), so ON CONFLICT works.
        cur.execute(
            """
            INSERT INTO vendor_listings (
                part_id, vendor_id, vendor_sku, vendor_url,
                price_cents, in_stock, last_scraped_at, missed_runs
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 0)
            ON CONFLICT (vendor_id, part_id) DO UPDATE SET
                vendor_sku = EXCLUDED.vendor_sku,
                vendor_url = EXCLUDED.vendor_url,
                price_cents = EXCLUDED.price_cents,
                in_stock = EXCLUDED.in_stock,
                last_scraped_at = NOW(),
                missed_runs = 0
            """,
            (part_id, vendor_id, sku, p.vendor_url, p.price_cents, p.in_stock),
        )

        # fitment_rules: replace all rules from this vendor source for this part.
        source = f"vendor:{p.vendor}"
        cur.execute(
            "DELETE FROM fitment_rules WHERE part_id=%s AND source=%s",
            (part_id, source),
        )
        for f in parsed_fitment:
            cur.execute(
                """
                INSERT INTO fitment_rules (
                    part_id, make, model, year_start, year_end,
                    trims_included, status, caveat, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    part_id,
                    f.make,
                    f.model,
                    f.year_start,
                    f.year_end,
                    list(f.trims_included) if f.trims_included else None,
                    f.status,
                    f.caveat,
                    source,
                ),
            )
    conn.commit()
    return part_id
