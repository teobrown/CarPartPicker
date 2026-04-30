from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Optional
import yaml
from rapidfuzz import process, fuzz

YAML_PATH = Path(__file__).resolve().parents[2] / "category_map.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, list[str]]:
    return yaml.safe_load(YAML_PATH.read_text())


def map_category(vendor_string: str, *, fuzzy_threshold: int = 80) -> Optional[str]:
    """Map a vendor's category string to our internal category slug."""
    table = _load()
    # exact match (case-insensitive)
    needle = vendor_string.strip().lower()
    for slug, aliases in table.items():
        if needle in (a.lower() for a in aliases):
            return slug
    # fuzzy match across the flattened alias list
    flat = [(slug, alias) for slug, aliases in table.items() for alias in aliases]
    choices = [alias for _, alias in flat]
    best = process.extractOne(vendor_string, choices, scorer=fuzz.WRatio,
                              score_cutoff=fuzzy_threshold)
    if best is None:
        return None
    matched_alias = best[0]
    for slug, alias in flat:
        if alias == matched_alias:
            return slug
    return None
