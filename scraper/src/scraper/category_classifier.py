"""Pure category-classifier: name + brand + current-slug -> new leaf slug.

Two-stage pipeline (LLM stage added in Task 6):
  1. classify_heuristic — ordered regex rules. Most-specific first so a
     "muffler delete" doesn't get caught by a generic "muffler" rule, etc.
     Returns the first match's slug, or None.

No DB access. The DB-aware orchestrator that walks rows and writes
`parts.category_id` lives in `reclassify.py`.
"""
from __future__ import annotations

import re
from typing import Optional

# Ordered: most-specific first. Each rule is (compiled_pattern, slug).
# Rule precedence is by list order — the first matching rule wins.
_RULES: list[tuple[re.Pattern[str], str]] = [
    # --- Wheels-adjacent hardware FIRST (so "wheel" rules don't swallow a "lug nut for wheels") ---
    (re.compile(r"\b(lug\s*nut|wheel\s*stud|valve\s*cap|valve\s*stem|center\s*cap|centering\s*rings?)\b", re.I), "lug-nuts-studs"),
    (re.compile(r"\b(wheel\s*spacer|hub\s*spacer)\b", re.I), "wheel-spacers"),
    (re.compile(r"\bhub\s*centric\s*ring\b", re.I), "hub-rings"),

    # --- Intake splits (specific kinds before generic "intake") ---
    (re.compile(r"\b(cold[\s\-]?air[\s\-]?intake|cai)\b", re.I), "cold-air-intake"),
    (re.compile(r"\b(short[\s\-]?ram[\s\-]?intake|sri)\b", re.I), "short-ram-intake"),
    (re.compile(r"\bram[\s\-]?air[\s\-]?intake\b", re.I), "ram-air-intake"),
    (re.compile(r"\bintake\s*manifold\b", re.I), "intake-manifold"),
    (re.compile(r"\b(panel\s*air\s*filter|drop[\s\-]?in\s*filter|replacement\s*air\s*filter|panel\s*filter)\b", re.I), "air-filter"),
    (re.compile(r"\b(silicone\s*intake\s*hose|intake\s*hose|silicone\s*hose)\b", re.I), "intake-hose"),
    (re.compile(r"\bmaf\s*housing\b", re.I), "maf-housing"),

    # --- Exhaust splits (most-specific first) ---
    (re.compile(r"\b(catback|cat[\s\-]back)\b", re.I), "catback-exhaust"),
    (re.compile(r"\bmuffler\s*delete\b", re.I), "muffler-delete"),
    (re.compile(r"\b(axleback|axle[\s\-]back)\b", re.I), "axleback-exhaust"),
    (re.compile(r"\b(front[\s\-]?pipe|j[\s\-]?pipe|over[\s\-]?pipe|mid[\s\-]?pipe)\b", re.I), "front-pipe"),
    (re.compile(r"\b(downpipe|down\s*pipe)\b", re.I), "downpipe"),
    (re.compile(r"\b(o2\s*sensor|oxygen\s*sensor|wideband\s*o2)\b", re.I), "o2-sensor"),
    (re.compile(r"\bexhaust\s*tip\b", re.I), "exhaust-tip"),

    # --- Forced induction ---
    (re.compile(r"\bintercooler\b", re.I), "intercooler"),
    (re.compile(r"\b(charge\s*pipe|hot\s*pipe|boost\s*pipe)\b", re.I), "charge-pipe"),
    (re.compile(r"\bwastegate\b", re.I), "wastegate"),
    (re.compile(r"\b(diverter\s*valve|blow[\s\-]?off|\bbov\b|\bbpv\b)\b", re.I), "bov"),

    # --- Tuning ---
    (re.compile(r"\b(accessport|access\s*port|ecu\s*tune|ecu\s*flash|tuner|programmer|flashpro)\b", re.I), "ecu-tune"),
    (re.compile(r"\b(wideband|af\s*gauge|boost\s*gauge|uego)\b", re.I), "wideband-gauge"),

    # --- Brakes ---
    (re.compile(r"\b(big\s*brake\s*kit|caliper\s*kit|\bbbk\b)\b", re.I), "big-brake-kit"),
    (re.compile(r"\b(brake\s*pads?|caliper\s*pads?)\b", re.I), "brake-pads"),
    (re.compile(r"\b(brake\s*rotors?|brake\s*discs?|slotted\s*rotors?)\b", re.I), "brake-rotors"),
    (re.compile(r"\b(brake\s*lines?|stainless\s*lines?)\b", re.I), "brake-lines"),

    # --- Suspension splits (control-arm and end-link before generic suspension) ---
    (re.compile(r"\b(control\s*arm|trailing\s*arm)\b", re.I), "control-arms"),
    (re.compile(r"\b(end\s*link|sway\s*end\s*link)\b", re.I), "end-links"),
    (re.compile(r"\b(sway\s*bar|anti[\s\-]?roll\s*bar)\b", re.I), "sway-bars"),
    (re.compile(r"\b(strut\s*bar|chassis\s*brace|strut\s*tower\s*bar)\b", re.I), "strut-bar"),
    (re.compile(r"\b(camber\s*arm|camber\s*kit|camber\s*bolt|camber\s*plate)\b", re.I), "camber-kit"),
    (re.compile(r"\b(subframe\s*bushing|control\s*arm\s*bushing|bushing\s*kit)\b", re.I), "bushings"),
    (re.compile(r"\b(coilover|coilovers|coil[\s\-]?over\s*kit|height\s*adjustable\s*suspension)\b", re.I), "coilovers"),
    (re.compile(r"\b(lowering\s*spring|sport\s*spring|drop\s*spring|pro[\s\-]?kit\s*spring)\b", re.I), "lowering-springs"),

    # --- Body & aero ---
    (re.compile(r"\b(front\s*lip|splitter|chin\s*spoiler)\b", re.I), "front-lip"),
    (re.compile(r"\bside\s*skirt\b", re.I), "side-skirts"),
    (re.compile(r"\b(rear\s*diffuser|underbody\s*diffuser)\b", re.I), "rear-diffuser"),
    (re.compile(r"\b(spoiler|wing|ducktail)\b", re.I), "spoiler-wing"),
    (re.compile(r"\bfender\s*flare\b", re.I), "fender-flares"),
    (re.compile(r"\b(hood|bonnet)\b", re.I), "hood"),

    # --- Lighting ---
    (re.compile(r"\b(fog\s*light|fog\s*lamp)\b", re.I), "fog-lights"),
    (re.compile(r"\b(headlight|headlamp|head\s*light)\b", re.I), "headlights"),
    (re.compile(r"\b(taillight|tail\s*lamp|tail\s*light)\b", re.I), "taillights"),
    (re.compile(r"\b(led\s*bulb|hid\s*kit|h11|9005|9006|h7\s*bulb)\b", re.I), "led-bulbs"),

    # --- Wheels & tires (last in the wheel/tire family — wheel-hardware rules above already filtered specific cases) ---
    (re.compile(r"\b(tire|tyre|advan|michelin|continental|yokohama|falken|bridgestone)\b", re.I), "tires"),
    (re.compile(r"\b(wheel|alloy)\b", re.I), "wheels"),
]

# Map an old leaf slug (suffixed with -old) to a default leaf slug. Used as
# a fallback PRIOR when no regex rule fires — the part keeps its old leaf's
# spirit (e.g. parts in `coilovers-old` default to coilovers, parts in
# `springs-old` default to lowering-springs).
_PRIOR_DEFAULTS: dict[str, str] = {
    "intake-old": "cold-air-intake",
    "catback-old": "catback-exhaust",
    "axleback-old": "axleback-exhaust",
    "muffler-delete-old": "muffler-delete",
    "downpipe-old": "downpipe",
    "intercooler-old": "intercooler",
    "bov-old": "bov",
    "tune-old": "ecu-tune",
    "coilovers-old": "coilovers",
    "springs-old": "lowering-springs",
    "sway-bars-old": "sway-bars",
    "wheels-old": "wheels",
    "tires-old": "tires",
    "lip-kit-old": "front-lip",
    "spoiler-old": "spoiler-wing",
    "fender-flares-old": "fender-flares",
    "headlights-old": "headlights",
    "taillights-old": "taillights",
}


def classify_heuristic(
    name: str,
    brand: str,
    current_slug: Optional[str],
) -> Optional[str]:
    """Map (name + brand + optional current slug) to a new leaf slug, or None.

    Rule precedence: the explicit regex rules above run first against
    `name + ' ' + brand`. If none match, we fall back to the
    `_PRIOR_DEFAULTS` map keyed by the old slug. Returns None when both
    fail (caller routes to LLM).
    """
    haystack = f"{name} {brand}"
    for pattern, slug in _RULES:
        if pattern.search(haystack):
            return slug
    if current_slug and current_slug in _PRIOR_DEFAULTS:
        return _PRIOR_DEFAULTS[current_slug]
    return None
