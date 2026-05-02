"""Detect garbage `trims_included` rows from bad regex extraction and re-run
the LLM to produce clean rules.

The earlier RSD scrape produced fitment_rules with garbage trims like
``['2']``, ``['2015-2021']``, or ``['Mega Ram']`` — the regex caught
parenthetical fragments that aren't actually trims. This script:

1. Finds parts whose fitment_rules have any trim that looks like a
   year range, a single short alphanumeric token (1-3 chars, not a known
   trim like GT/RS/STI/Si/CS), or other obvious junk.
2. Drops the bad rules for that part.
3. Calls the LLM to re-extract from the part's name + description.
4. Inserts the clean rules with source = ``llm:repair``.

Idempotent within a single run; running twice on the same DB after a
successful repair is a no-op (the new rules don't match the garbage
heuristic). Fail-open: per-part LLM failures log a warning but don't
abort the loop.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from scraper.db import connect
from scraper.llm_fitment import parse_fitment_with_llm

YEAR_RANGE = re.compile(r"^\d{4}-\d{4}$")
SHORT_TOKEN = re.compile(r"^[A-Z0-9]{1,3}$", re.IGNORECASE)

# Known short trim tokens we should NOT treat as garbage even though they
# match the SHORT_TOKEN heuristic.
KNOWN_SHORT_TRIMS = {"gt", "rs", "sti", "si", "cs"}


def _looks_like_garbage(trim: str) -> bool:
    if not trim:
        return False
    t = trim.strip()
    if YEAR_RANGE.match(t):
        return True
    if SHORT_TOKEN.match(t) and t.lower() not in KNOWN_SHORT_TRIMS:
        return True
    return False


def _trims_look_garbage(trims: list | None) -> bool:
    if not trims:
        return False
    return any(_looks_like_garbage(t) for t in trims)


def _load_env_local() -> None:
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
            cur.execute(
                """
                SELECT DISTINCT p.id, p.name, p.description
                FROM parts p
                JOIN fitment_rules fr ON fr.part_id = p.id
                WHERE fr.trims_included IS NOT NULL
                ORDER BY p.id
                """
            )
            candidates = cur.fetchall()

        bad_part_ids: list[tuple[int, str, str | None]] = []
        for part_id, name, description in candidates:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT trims_included FROM fitment_rules "
                    "WHERE part_id=%s AND trims_included IS NOT NULL",
                    (part_id,),
                )
                trim_lists = [row[0] for row in cur.fetchall()]
            if any(_trims_look_garbage(t) for t in trim_lists):
                bad_part_ids.append((part_id, name, description))

        log.info("parts with garbage trims: %d", len(bad_part_ids))

        repaired = 0
        zero = 0
        for i, (part_id, name, description) in enumerate(bad_part_ids, start=1):
            text = " ".join(filter(None, [name, description]))
            try:
                parsed = parse_fitment_with_llm(text)
            except Exception as e:  # noqa: BLE001
                log.warning("llm failed for part %s: %s", part_id, e)
                continue
            if not parsed:
                zero += 1
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM fitment_rules WHERE part_id=%s", (part_id,)
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
                            "llm:repair",
                        ),
                    )
            conn.commit()
            repaired += 1
            if i % 25 == 0:
                log.info(
                    "progress: %d/%d (repaired=%d zero=%d)",
                    i,
                    len(bad_part_ids),
                    repaired,
                    zero,
                )

        log.info("done. repaired=%d zero=%d", repaired, zero)


if __name__ == "__main__":
    main()
