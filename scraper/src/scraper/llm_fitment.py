"""LLM-backed fitment fallback.

When the regex parser in ``fitment_parser`` can't latch onto a vendor's
prose (FCP Euro chassis-coded blurbs, AmericanMuscle 2-digit years,
RallySport Direct multi-car descriptions), we fall back to DeepSeek
to extract structured ``ParsedFitment`` rows.

The output is filtered to the 11 platforms the app actually supports
(no Foresters, A4s, Passats, Camrys leaking through). Empty/no-API-key
inputs fail open with an empty list — the orchestrator should never
crash because the LLM was unreachable.

Cache is keyed on a sha256 of the input text and lives at
``scraper/.cache/llm_fitment/`` (gitignored). Re-running the scraper
or the backfill on unchanged descriptions is free.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from scraper.fitment_parser import ParsedFitment

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm_fitment"

# Aligned with KNOWN_MODELS in fitment_parser.py — these are the only
# (make, model) tuples the picker can resolve to a vehicle today.
SUPPORTED_PLATFORMS: list[tuple[str, str]] = [
    ("Subaru", "WRX"),
    ("Subaru", "WRX STI"),
    ("Subaru", "BRZ"),
    ("Toyota", "GR Corolla"),
    ("Toyota", "GR86"),
    ("Honda", "Civic Si"),
    ("Honda", "Civic Type R"),
    ("Ford", "Mustang"),
    ("Mazda", "MX-5 Miata"),
    ("Volkswagen", "Golf R"),
    ("Volkswagen", "GTI"),
]

SYSTEM_PROMPT = """You are a parser that extracts structured automotive fitment data from vendor product descriptions.

Given a string of prose, return a JSON object with a single key "rules", an array of fitment rules.

Each rule has:
- "make": car manufacturer ("Subaru", "Honda", "Ford", "Toyota", "Mazda", "Volkswagen") - required
- "model": specific model ("WRX", "Civic Type R", "Mustang", "Golf R", etc.) - required
- "generation": chassis code if mentioned ("VA", "VB", "FK8", "FL5", "S550", "Mk7", "Mk8", "ZN8", "ZD8", "ND") or null
- "year_start": integer or null
- "year_end": integer or null (use null for "+" or open ranges like "2022+")
- "trims_included": list of trims mentioned (e.g. ["Premium", "Limited"]) or null
- "status": "fits" if explicit and clean, "fits_with_caveat" if requires modification (note in caveat), "unknown" if ambiguous
- "caveat": short string describing any caveat ("requires fender rolling", "remove OEM intake first") or null

Rules:
- Only emit rules for the platforms the app cares about: WRX, WRX STI, GR Corolla, GR86, BRZ, Civic Si, Civic Type R, Mustang, MX-5 Miata, Golf R, GTI. SKIP fitments for cars not in this list (Camry, Passat, Forester, Outback, Crosstrek, A4, etc.).
- Prefer "fits" status when the description says "fits", "compatible with", or "designed for".
- Prefer "fits_with_caveat" when the description mentions trimming, rolling, or other modifications.
- Two-digit years: "05-09" means 2005-2009 in US-market context for Mustang.
- Normalize "VW" -> "Volkswagen", "Subaru WRX STI" -> make:"Subaru", model:"WRX STI".
- For platforms our app doesn't support (e.g., Forester, Outback, A4, Passat), skip entirely. Don't emit them.
- Empty input -> return {"rules": []}.

Return strict JSON with no surrounding prose."""

HTML_SYSTEM_PROMPT = """You are a parser that extracts automotive fitment data from product page HTML text content (no markup — pre-stripped to plain text).

Find every mention of a specific car make + model + year range and emit a fitment rule. Skip generic categories ("vehicles", "cars"). Skip cars NOT in this exact list: WRX, WRX STI, BRZ, GR Corolla, GR86, Civic Si, Civic Type R, Mustang, MX-5 Miata, Golf R, GTI.

Each rule has:
- "make": Subaru, Honda, Ford, Toyota, Mazda, Volkswagen — required
- "model": one of the supported model names above — required
- "generation": chassis code if mentioned (VA, VB, FK8, FL5, S550, Mk7, Mk8, ZN8, ZD8, ND) or null
- "year_start": int or null
- "year_end": int or null
- "trims_included": list of trims (e.g. ["Premium", "Limited"]) or null
- "status": "fits" if explicit ("fits", "compatible", "designed for"), "fits_with_caveat" if requires modification, "unknown" if ambiguous
- "caveat": short string or null

Return strict JSON: {"rules": [...]}. No surrounding prose."""


def _cache_path(text: str, *, model: str) -> Path:
    h = hashlib.sha256(f"{model}|{text}".encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{h}.json"


def _int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _list_or_none(v: Any) -> Optional[list[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        out = [str(x).strip() for x in v if str(x).strip()]
        return out or None
    return None


def _str_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _is_supported_platform(make: str, model: str) -> bool:
    return (make, model) in SUPPORTED_PLATFORMS


def _dataclass_to_dict(p: ParsedFitment) -> dict[str, Any]:
    return asdict(p)


def parse_fitment_with_llm(text: str) -> list[ParsedFitment]:
    """Extract structured fitment rules from vendor prose via DeepSeek.

    Fail-open behavior:
    - Empty/whitespace input -> []
    - No DEEPSEEK_API_KEY in env -> []
    - JSON decode failure -> []
    - Hallucinated unsupported platforms -> filtered out
    """
    if not text or not text.strip():
        return []

    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

    # Read the cache before importing/instantiating the client so cached
    # hits don't spend tokens or require an API key. Cache key includes the
    # model name so switching models invalidates cleanly without cross-model
    # contamination.
    cp = _cache_path(text, model=model)
    if cp.exists():
        try:
            cached = json.loads(cp.read_text(encoding="utf-8"))
            return [ParsedFitment(**row) for row in cached]
        except (json.JSONDecodeError, TypeError, OSError):
            # Corrupt cache entry — fall through and re-query.
            pass

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        # Fail open: scrapes without a key shouldn't crash, they just
        # don't get the LLM tier of fallback.
        return []

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:4000]},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=600,
    )

    raw = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rules_raw = data.get("rules", []) or []

    out: list[ParsedFitment] = []
    for r in rules_raw:
        if not isinstance(r, dict):
            continue
        make = _str_or_none(r.get("make"))
        model_name = _str_or_none(r.get("model"))
        if not make or not model_name:
            continue
        if not _is_supported_platform(make, model_name):
            continue
        status_raw = r.get("status")
        status = (
            status_raw
            if status_raw in ("fits", "fits_with_caveat", "unknown")
            else "unknown"
        )
        out.append(
            ParsedFitment(
                make=make,
                model=model_name,
                year_start=_int_or_none(r.get("year_start")),
                year_end=_int_or_none(r.get("year_end")),
                trims_included=_list_or_none(r.get("trims_included")),
                status=status,
                caveat=_str_or_none(r.get("caveat")),
            )
        )

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            json.dumps([_dataclass_to_dict(r) for r in out]),
            encoding="utf-8",
        )
    except OSError:
        # Cache writes are best-effort — don't fail the call if the
        # cache dir is unwritable.
        pass

    return out


def _strip_html_noise(html: str) -> str:
    """Strip script/style/nav/footer/aside/noscript blocks and return
    plain-text content with whitespace collapsed. Used to feed the LLM
    a clean view of a product page when the structured parser came up empty.
    """
    from selectolax.parser import HTMLParser

    tree = HTMLParser(html)
    for sel in ("script", "style", "nav", "footer", "aside", "noscript"):
        for n in tree.css(sel):
            n.decompose()
    text = tree.text(separator=" ", strip=True)
    # Collapse runs of whitespace
    return " ".join(text.split())


def _parse_rules_payload(raw: str) -> list[ParsedFitment]:
    """Shared response-decoding step used by both the prose and HTML extractors."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rules_raw = data.get("rules", []) or []

    out: list[ParsedFitment] = []
    for r in rules_raw:
        if not isinstance(r, dict):
            continue
        make = _str_or_none(r.get("make"))
        model_name = _str_or_none(r.get("model"))
        if not make or not model_name:
            continue
        if not _is_supported_platform(make, model_name):
            continue
        status_raw = r.get("status")
        status = (
            status_raw
            if status_raw in ("fits", "fits_with_caveat", "unknown")
            else "unknown"
        )
        out.append(
            ParsedFitment(
                make=make,
                model=model_name,
                year_start=_int_or_none(r.get("year_start")),
                year_end=_int_or_none(r.get("year_end")),
                trims_included=_list_or_none(r.get("trims_included")),
                status=status,
                caveat=_str_or_none(r.get("caveat")),
            )
        )
    return out


def extract_fitment_from_html(
    html: str, *, max_html_chars: int = 8000
) -> list[ParsedFitment]:
    """Aid scraping by extracting fitment rules from raw product-page HTML
    when the structured parser couldn't find clean fitment text.

    Strips ``<script>``/``<style>``/``<nav>``/``<footer>``/``<aside>``/
    ``<noscript>`` blocks before sending so the model sees readable content.
    Caches by hash of the trimmed (stripped + truncated) HTML keyed on the
    same model used by ``parse_fitment_with_llm``.

    Returns the same ``ParsedFitment`` shape as ``parse_fitment_with_llm``.
    Fails open to ``[]`` on empty input, missing API key, or JSON decode error.
    """
    if not html or not html.strip():
        return []
    cleaned = _strip_html_noise(html)[:max_html_chars]
    if not cleaned.strip():
        return []

    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

    # Cache key: prefix with "html|" so HTML-extraction outputs don't
    # collide with prose extraction even when the trimmed text happens
    # to match a prose input verbatim.
    cp = _cache_path(f"html|{cleaned}", model=model)
    if cp.exists():
        try:
            cached = json.loads(cp.read_text(encoding="utf-8"))
            return [ParsedFitment(**row) for row in cached]
        except (json.JSONDecodeError, TypeError, OSError):
            pass

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return []

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": HTML_SYSTEM_PROMPT},
            {"role": "user", "content": cleaned},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=800,
    )

    raw = completion.choices[0].message.content or "{}"
    out = _parse_rules_payload(raw)

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            json.dumps([_dataclass_to_dict(r) for r in out]),
            encoding="utf-8",
        )
    except OSError:
        pass

    return out
