import argparse
import logging
import sys
from scraper.orchestrator import run_vendor_live


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(prog="scraper")
    parser.add_argument("vendor", help="vendor slug (e.g., fcp-euro)")
    args = parser.parse_args()
    n = run_vendor_live(args.vendor)
    print(f"upserted {n} parts from {args.vendor}")
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
