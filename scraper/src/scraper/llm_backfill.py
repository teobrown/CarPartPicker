"""One-shot backfill: build fitment_rules for parts that don't have any.

Walks every part with no rules, runs the regex parser first, falls back
to the DeepSeek-backed parser if the regex doesn't latch. Idempotent —
parts that already have rules are skipped, so re-running on partial
failure just resumes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from scraper.db import connect
from scraper.fitment_parser import parse_fitment
from scraper.llm_fitment import parse_fitment_with_llm


def _load_env_local() -> None:
    """Hydrate DATABASE_URL + DEEPSEEK_API_KEY from .env.local at the
    repo root, if present. Match the .env.local sibling-of-scraper layout.
    """
    env_path = Path(__file__).resolve().parents[3] / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    _load_env_local()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    log = logging.getLogger(__name__)

    if "DEEPSEEK_API_KEY" not in os.environ:
        raise SystemExit("DEEPSEEK_API_KEY not set in environment or .env.local")

    with connect() as conn:
        with conn.cursor() as cur:
            # Parts with no fitment_rules at all. Pulling vendor slug
            # alongside so we can stamp the source field correctly.
            cur.execute(
                """
                SELECT
                    p.id,
                    p.brand,
                    p.model,
                    p.name,
                    p.description,
                    vl.id AS listing_id,
                    v.slug AS vendor_slug
                FROM parts p
                LEFT JOIN vendor_listings vl ON vl.part_id = p.id
                LEFT JOIN vendors v ON v.id = vl.vendor_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM fitment_rules fr WHERE fr.part_id = p.id
                )
                ORDER BY p.id
                """
            )
            rows = cur.fetchall()

        log.info("backfilling %d parts", len(rows))

        skipped = 0
        regex_hits = 0
        llm_hits = 0
        zero = 0

        for i, row in enumerate(rows, start=1):
            (
                part_id,
                brand,
                model_name,
                name,
                description,
                _listing_id,
                vendor_slug,
            ) = row

            text = " ".join(filter(None, [name, description]))
            if not text.strip():
                skipped += 1
                continue

            parsed = parse_fitment(text)
            source = f"vendor:{vendor_slug or 'unknown'}+regex"
            if not parsed:
                parsed = parse_fitment_with_llm(text)
                source = f"vendor:{vendor_slug or 'unknown'}+llm"
                if parsed:
                    llm_hits += 1
                else:
                    zero += 1
            else:
                regex_hits += 1

            if not parsed:
                continue

            with conn.cursor() as cur:
                # Clear any prior backfill rows from us so re-runs replace
                # rather than duplicate. Live-scrape rows use plain
                # "vendor:<slug>" so they're untouched.
                cur.execute(
                    "DELETE FROM fitment_rules WHERE part_id=%s AND source LIKE %s",
                    (part_id, "vendor:%+%"),
                )
                for r in parsed:
                    cur.execute(
                        """
                        INSERT INTO fitment_rules
                          (part_id, make, model, year_start, year_end,
                           trims_included, status, caveat, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            part_id,
                            r.make,
                            r.model,
                            r.year_start,
                            r.year_end,
                            list(r.trims_included) if r.trims_included else None,
                            r.status,
                            r.caveat,
                            source,
                        ),
                    )
            conn.commit()

            if i % 25 == 0:
                log.info(
                    "progress: %d/%d (regex=%d llm=%d zero=%d skipped=%d)",
                    i,
                    len(rows),
                    regex_hits,
                    llm_hits,
                    zero,
                    skipped,
                )

        log.info(
            "done. regex=%d llm=%d zero=%d skipped=%d",
            regex_hits,
            llm_hits,
            zero,
            skipped,
        )


if __name__ == "__main__":
    main()
