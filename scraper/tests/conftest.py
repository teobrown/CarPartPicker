import os
import sys
from pathlib import Path

ENV_LOCAL = Path(__file__).resolve().parents[2] / ".env.local"
if ENV_LOCAL.exists():
    for line in ENV_LOCAL.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

test_url = os.environ.get("TEST_DATABASE_URL")
prod_url = os.environ.get("DATABASE_URL")

if not test_url:
    sys.exit(
        "TEST_DATABASE_URL is required to run tests. Set it in .env.local. "
        "It MUST point at a separate database from DATABASE_URL — tests truncate tables."
    )
if test_url == prod_url:
    sys.exit(
        "TEST_DATABASE_URL must NOT equal DATABASE_URL. "
        "Tests truncate tables. Use a separate database for testing."
    )

# Tests read DATABASE_URL via the upsert/orchestrator code paths; point at the test DB.
os.environ["DATABASE_URL"] = test_url
