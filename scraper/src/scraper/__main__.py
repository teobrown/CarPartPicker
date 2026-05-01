import argparse
import logging
import os
import sys
from pathlib import Path


def _load_env_local() -> None:
    """Best-effort load of repo-root .env.local for local dev. CI sets env vars
    directly via secrets, so this is a no-op in GitHub Actions."""
    env_path = Path(__file__).resolve().parents[3] / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def main():
    _load_env_local()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(prog="scraper")
    parser.add_argument("vendor", help="vendor slug (e.g., fcp-euro)")
    args = parser.parse_args()

    if "DATABASE_URL" not in os.environ:
        sys.exit("DATABASE_URL is not set. Add it to .env.local or set it in the environment.")

    from scraper.orchestrator import run_vendor_live
    n = run_vendor_live(args.vendor)
    print(f"upserted {n} parts from {args.vendor}")
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
