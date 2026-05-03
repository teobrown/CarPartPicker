"""One-shot orchestration: walk every part, classify, update parts.category_id.

Read phase uses a short-lived connection and joins parts -> categories so
the classifier sees the OLD slug (suffixed with `-old` by the migrate-
categories.ts script). Write phase uses an autocommit connection with
per-part transactions to survive Neon's idle-in-transaction timeout.

Idempotent: a part that's already on a non-`-old` category is left alone.
Re-running on a partially-reclassified DB resumes cleanly.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg

from scraper.category_classifier import classify, classify_heuristic


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


def _slug_to_id(conn: psycopg.Connection) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, slug FROM categories")
        return {row[1]: row[0] for row in cur.fetchall()}


def _fetch_pending(db_url: str) -> list[tuple[int, str, str, str]]:
    """Returns (part_id, name, brand, current_slug). Skips parts whose
    category_id already points at a non-old slug."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.name, p.brand, c.slug
                FROM parts p
                JOIN categories c ON c.id = p.category_id
                WHERE c.slug LIKE '%-old'
                ORDER BY p.id
                """
            )
            return cur.fetchall()


def main() -> None:
    _load_env_local()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        slug_to_id = _slug_to_id(conn)
        if "misc" not in slug_to_id:
            raise SystemExit("misc category not seeded — run migrate-categories.ts first")
    misc_id = slug_to_id["misc"]

    rows = _fetch_pending(db_url)
    log.info("reclassifying %d parts (parts on -old categories)", len(rows))

    counts = {"heuristic": 0, "llm": 0, "misc": 0}

    with psycopg.connect(db_url, autocommit=True) as conn:
        slug_to_id = _slug_to_id(conn)
        for i, (part_id, name, brand, current_slug) in enumerate(rows, start=1):
            new_slug = classify(name, brand, current_slug)
            if new_slug is None:
                target_id = misc_id
                counts["misc"] += 1
            else:
                target_id = slug_to_id.get(new_slug)
                if target_id is None:
                    log.warning("classifier returned unknown slug %r — sending to misc", new_slug)
                    target_id = misc_id
                    counts["misc"] += 1
                else:
                    # heuristic-vs-llm split is best-effort: re-running heuristic
                    # to attribute is cheap.
                    if classify_heuristic(name, brand, current_slug) is not None:
                        counts["heuristic"] += 1
                    else:
                        counts["llm"] += 1

            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE parts SET category_id = %s WHERE id = %s",
                        (target_id, part_id),
                    )
            if i % 50 == 0:
                log.info("progress: %d/%d (heuristic=%d llm=%d misc=%d)",
                         i, len(rows), counts["heuristic"], counts["llm"], counts["misc"])

    log.info("done. heuristic=%d llm=%d misc=%d total=%d",
             counts["heuristic"], counts["llm"], counts["misc"], sum(counts.values()))


if __name__ == "__main__":
    main()
