import os
import psycopg


def connect():
    """Open a Postgres connection from $DATABASE_URL.

    Raises a clear error if the env var is missing or empty so a misconfigured
    GitHub Actions run (e.g. secret not wired through) fails fast with a
    useful message instead of psycopg silently falling back to a local Unix
    socket and reporting "connection to /var/run/postgresql/.s.PGSQL.5432".
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set or is empty. In GitHub Actions, add a "
            "repository secret named DATABASE_URL (Settings -> Secrets and "
            "variables -> Actions) and reference it from the workflow with "
            "env: DATABASE_URL: ${{ secrets.DATABASE_URL }}."
        )
    return psycopg.connect(url)
