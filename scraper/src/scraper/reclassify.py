"""One-shot orchestration: walk parts, classify, update parts.category_id.

Default mode walks parts on `-old` categories — the post-migrate state where
the suffix is still on disk and parts haven't been moved yet.

Maintenance mode (`--target-slug <slug>`) walks parts whose CURRENT category
slug matches the given value. Use this after fixing a heuristic rule to
re-classify parts that the old rule mis-bucketed (e.g. after tightening
the intake-family priors, run `--target-slug cold-air-intake` to revisit
parts that should have landed in air-filter, intake-hose, etc.).

Read phase uses a short-lived connection and joins parts -> categories so
the classifier sees the slug being targeted. Write phase uses an autocommit
connection with per-part transactions to survive Neon's idle-in-transaction
timeout.

Idempotent in either mode: a part that classifies to its current category
under the current rules is a no-op write.
"""
from __future__ import annotations

import argparse
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


def _fetch_pending(
    db_url: str, *, target_slug: str | None
) -> list[tuple[int, str, str, str]]:
    """Returns (part_id, name, brand, current_slug).

    target_slug=None: walk every part whose category slug ends in '-old'
    (default migration mode).

    target_slug='<slug>': walk every part currently on that exact slug
    (maintenance mode for rule-fix re-runs).
    """
    where_sql = (
        "WHERE c.slug = %(target)s"
        if target_slug is not None
        else "WHERE c.slug LIKE '%%-old'"
    )
    params = {"target": target_slug} if target_slug is not None else {}
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT p.id, p.name, p.brand, c.slug
                FROM parts p
                JOIN categories c ON c.id = p.category_id
                {where_sql}
                ORDER BY p.id
                """,
                params,
            )
            return cur.fetchall()


def main() -> None:
    _load_env_local()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(prog="scraper.reclassify")
    parser.add_argument(
        "--target-slug",
        default=None,
        help=(
            "Optional. When set, re-classifies parts on the given slug "
            "(maintenance mode). When unset, walks parts on any '%%-old' "
            "category (default migration mode)."
        ),
    )
    args = parser.parse_args()

    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        slug_to_id = _slug_to_id(conn)
        if "misc" not in slug_to_id:
            raise SystemExit("misc category not seeded — run migrate-categories.ts first")
    misc_id = slug_to_id["misc"]

    rows = _fetch_pending(db_url, target_slug=args.target_slug)
    if args.target_slug is not None:
        log.info("re-classifying %d parts currently on %r", len(rows), args.target_slug)
    else:
        log.info("reclassifying %d parts (parts on -old categories)", len(rows))

    classified = {"heuristic": 0, "llm": 0, "misc": 0}
    updates = {"ok": 0, "no_op": 0, "failed": 0}

    with psycopg.connect(db_url, autocommit=True) as conn:
        slug_to_id = _slug_to_id(conn)
        for i, (part_id, name, brand, current_slug) in enumerate(rows, start=1):
            new_slug = classify(name, brand, current_slug)
            if new_slug is None:
                target_id = misc_id
                classified["misc"] += 1
            else:
                target_id = slug_to_id.get(new_slug)
                if target_id is None:
                    log.warning("classifier returned unknown slug %r — sending to misc", new_slug)
                    target_id = misc_id
                    classified["misc"] += 1
                else:
                    if classify_heuristic(name, brand, current_slug) is not None:
                        classified["heuristic"] += 1
                    else:
                        classified["llm"] += 1

            current_id = slug_to_id.get(current_slug)
            if current_id == target_id:
                # Already on the right category — skip the round-trip.
                updates["no_op"] += 1
            else:
                try:
                    with conn.transaction():
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE parts SET category_id = %s WHERE id = %s",
                                (target_id, part_id),
                            )
                    updates["ok"] += 1
                except psycopg.Error as e:
                    log.warning("update failed for part %d: %s", part_id, e)
                    updates["failed"] += 1

            if i % 50 == 0:
                log.info(
                    "progress: %d/%d (classify: heuristic=%d llm=%d misc=%d | "
                    "writes: ok=%d no_op=%d failed=%d)",
                    i, len(rows),
                    classified["heuristic"], classified["llm"], classified["misc"],
                    updates["ok"], updates["no_op"], updates["failed"],
                )

    log.info(
        "done. classify: heuristic=%d llm=%d misc=%d (total=%d). "
        "writes: ok=%d no_op=%d failed=%d.",
        classified["heuristic"], classified["llm"], classified["misc"],
        sum(classified.values()),
        updates["ok"], updates["no_op"], updates["failed"],
    )


if __name__ == "__main__":
    main()
