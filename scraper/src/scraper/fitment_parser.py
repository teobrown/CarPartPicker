from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, List

CAVEAT_PHRASES = [
    "requires fender rolling",
    "requires trimming",
    "requires modification",
    "may require",
]

# Make + model patterns. Add new pairs as the catalog grows.
KNOWN_MODELS: list[tuple[str, str]] = [
    ("Subaru", "WRX STI"),
    ("Subaru", "WRX"),
    ("Subaru", "BRZ"),
    ("Toyota", "GR Corolla"),
    ("Toyota", "GR86"),
    ("Honda", "Civic Type R"),
    ("Honda", "Civic Si"),
    ("Ford", "Mustang"),
    ("Mazda", "MX-5 Miata"),
    ("Volkswagen", "Golf R"),
    ("Volkswagen", "GTI"),
]

YEAR_RANGE_RE = re.compile(r"(?P<ys>\d{4})\s*[-–]\s*(?P<ye>\d{4})")
YEAR_OPEN_RE = re.compile(r"(?P<ys>\d{4})\+")
TRIMS_RE = re.compile(r"\(([^)]+)\)")


@dataclass(frozen=True)
class ParsedFitment:
    make: str
    model: str
    year_start: Optional[int]
    year_end: Optional[int]
    trims_included: Optional[list[str]]
    status: str  # 'fits' | 'fits_with_caveat'
    caveat: Optional[str]


def parse_fitment(text: str) -> List[ParsedFitment]:
    if not text:
        return []
    results: list[ParsedFitment] = []
    for make, model in KNOWN_MODELS:
        if model not in text:
            continue
        # year range
        ys: Optional[int]
        ye: Optional[int]
        if (m := YEAR_RANGE_RE.search(text)):
            ys, ye = int(m["ys"]), int(m["ye"])
        elif (m := YEAR_OPEN_RE.search(text)):
            ys, ye = int(m["ys"]), None
        else:
            continue  # we require at least one year token
        # trims (everything inside parens, except known caveat phrases)
        trims: Optional[list[str]] = None
        caveat: Optional[str] = None
        for paren_match in TRIMS_RE.findall(text):
            lower = paren_match.lower()
            if any(c in lower for c in CAVEAT_PHRASES):
                caveat = paren_match.strip()
            else:
                trims = [t.strip() for t in paren_match.split(",")]
        # bare trim token immediately after the model name (e.g., "Mustang GT")
        if trims is None:
            bare_trim_re = re.compile(
                rf"{re.escape(model)}\s+([A-Z][A-Za-z0-9]*)\b"
            )
            if (bm := bare_trim_re.search(text)):
                token = bm.group(1)
                # skip tokens that look like chassis codes (e.g., FK8) — letter+digit mix
                if not re.fullmatch(r"[A-Z]+\d+", token):
                    trims = [token]
        # also detect bare caveat phrases outside parens
        if caveat is None:
            for phrase in CAVEAT_PHRASES:
                if phrase in text.lower():
                    caveat = phrase
                    break
        status = "fits_with_caveat" if caveat else "fits"
        results.append(ParsedFitment(
            make=make, model=model, year_start=ys, year_end=ye,
            trims_included=trims, status=status, caveat=caveat,
        ))
        break  # one match per pass for v1; multi-vehicle fitments parse later
    return results
