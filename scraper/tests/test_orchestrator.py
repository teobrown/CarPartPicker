import os
import psycopg
from pathlib import Path
from scraper.orchestrator import run_vendor_from_fixtures

FIXTURES = Path(__file__).parent / "fixtures" / "fcp-euro"
DATABASE_URL = os.environ["DATABASE_URL"]


def test_orchestrator_imports_fcp_euro_fixtures_into_db():
    # Snapshot pre-test counts; we'll restore them in the cleanup
    with psycopg.connect(DATABASE_URL, autocommit=True) as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM parts")
            parts_before = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM vendor_listings")
            listings_before = cur.fetchone()[0]
        try:
            n = run_vendor_from_fixtures("fcp-euro", FIXTURES)
            assert n >= 1, f"expected at least 1 part upserted, got {n}"
            with c.cursor() as cur:
                cur.execute("SELECT count(*) FROM parts")
                assert cur.fetchone()[0] >= parts_before + 1
                cur.execute("SELECT count(*) FROM vendor_listings")
                assert cur.fetchone()[0] >= listings_before + 1
        finally:
            # cleanup: delete anything inserted from these fixtures
            with c.cursor() as cur:
                # the fixtures' brands are 034Motorsport and Genuine VW
                cur.execute("""
                    DELETE FROM fitment_rules
                    WHERE part_id IN (
                      SELECT id FROM parts WHERE brand IN ('034Motorsport', 'Genuine VW')
                    )
                """)
                cur.execute("""
                    DELETE FROM vendor_listings
                    WHERE part_id IN (
                      SELECT id FROM parts WHERE brand IN ('034Motorsport', 'Genuine VW')
                    )
                """)
                cur.execute(
                    "DELETE FROM parts WHERE brand IN ('034Motorsport', 'Genuine VW')"
                )
