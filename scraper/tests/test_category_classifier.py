"""Tests for the heuristic + LLM category classifier.

The heuristic stage maps part name + brand + current-category-slug to a new
leaf slug via ordered regex rules. These tests pin the expected mappings
for representative parts pulled from the real catalog.
"""
import pytest
from scraper.category_classifier import classify_heuristic


@pytest.mark.parametrize("name, brand, current_slug, expected", [
    # Intake splits
    ("AEM Cold Air Intake System", "AEM", "intake-old", "cold-air-intake"),
    ("Injen Short Ram Intake", "Injen", "intake-old", "short-ram-intake"),
    ("Mustang Ram Air Intake", "K&N", "intake-old", "ram-air-intake"),
    ("RBC Intake Manifold Adapter Kit", "Skunk2", "intake-old", "intake-manifold"),
    ("K&N Replacement Panel Air Filter Upgrade", "K&N", "intake-old", "air-filter"),
    ("Silicone Intake Hose Kit", "PRL", "intake-old", "intake-hose"),
    ("MAF Housing Conversion Kit", "PRL", "intake-old", "maf-housing"),

    # Exhaust splits
    ("Borla S-Type Cat-Back Exhaust", "Borla", "catback-old", "catback-exhaust"),
    ("AWE Touring Edition Axle-Back Exhaust", "AWE", "axleback-old", "axleback-exhaust"),
    ("Front Pipe Upgrade for Civic Si", "PRL", "catback-old", "front-pipe"),
    ("J-Pipe Lower Section", "Invidia", "catback-old", "front-pipe"),
    ("Mid-Pipe Section", "MagnaFlow", "catback-old", "front-pipe"),
    ("3 Inch Catted Downpipe", "GrimmSpeed", "downpipe-old", "downpipe"),
    ("Muffler Delete Axle-Back", "C&L", "muffler-delete-old", "muffler-delete"),
    ("4 Inch Polished Exhaust Tip", "Borla", "catback-old", "exhaust-tip"),
    ("Innovate Wideband O2 Sensor", "Innovate", "catback-old", "o2-sensor"),
    ("Oxygen Sensor Replacement", "Bosch", "catback-old", "o2-sensor"),
    # Exhaust hardware catch-all (gaskets, clamps, studs, flanges, O2 bungs)
    ("3 Inch Exhaust Gasket", "GrimmSpeed", "catback-old", "exhaust-hardware"),
    ("Stainless Exhaust Clamp Kit", "Vibrant", "catback-old", "exhaust-hardware"),
    ("Exhaust Stud Set", "ARP", "catback-old", "exhaust-hardware"),
    ("O2 Bung Plug, Stainless", "Generic", "catback-old", "exhaust-hardware"),

    # Forced induction
    ("Mishimoto Top Mount Intercooler", "Mishimoto", "intercooler-old", "intercooler"),
    ("Charge Pipe Kit, Aluminum", "PRL", "intercooler-old", "charge-pipe"),
    ("Forge Diverter Valve DV+", "Forge", "bov-old", "bov"),
    ("Turbosmart Wastegate Hose Kit", "Turbosmart", "bov-old", "wastegate"),

    # Suspension
    ("BC Racing BR Coilover Kit", "BC Racing", "coilovers-old", "coilovers"),
    ("Eibach Pro-Kit Lowering Springs", "Eibach", "springs-old", "lowering-springs"),
    ("Whiteline Front Sway Bar", "Whiteline", "sway-bars-old", "sway-bars"),
    ("Whiteline End Link Kit", "Whiteline", "sway-bars-old", "end-links"),
    ("Audi VW Control Arm Kit - Lemforder", "Lemforder", "coilovers-old", "control-arms"),
    ("Cusco Front Strut Bar", "Cusco", "coilovers-old", "strut-bar"),
    ("SPC Camber Kit, Front", "SPC", "coilovers-old", "camber-kit"),
    ("Whiteline Subframe Bushing Kit", "Whiteline", "coilovers-old", "bushings"),

    # Wheels & tires
    ("Enkei RPF1 Silver 17x9 +35 5x100", "Enkei", "wheels-old", "wheels"),
    ("Yokohama ADVAN Sport V107 245/40R18", "Yokohama", "tires-old", "tires"),
    ("ARP Wheel Stud", "ARP", "wheels-old", "lug-nuts-studs"),
    ("Flyin' Miata aluminum lug nut (set of 16)", "Flyin' Miata", "wheels-old", "lug-nuts-studs"),
    ("FM aluminum tire valve cap", "Flyin' Miata", "wheels-old", "lug-nuts-studs"),
    ("Center cap, for FM Kogeki flow-formed wheels", "Flyin' Miata", "wheels-old", "lug-nuts-studs"),
    ("54.1mm wheel centering rings (set of 4)", "Flyin' Miata", "wheels-old", "lug-nuts-studs"),
    ("H&R Wheel Spacer Pair, 15mm", "H&R", "wheels-old", "wheel-spacers"),
    ("Hub Centric Ring 73.1 to 56.1", "Generic", "wheels-old", "hub-rings"),

    # Body & aero
    ("APR Performance Front Splitter", "APR", "lip-kit-old", "front-lip"),
    ("Front Lip Carbon Fiber", "Seibon", "lip-kit-old", "front-lip"),
    ("Side Skirt Extension Set", "Verus", "lip-kit-old", "side-skirts"),
    ("Rear Diffuser Carbon", "Verus", "spoiler-old", "rear-diffuser"),
    ("Big Wing Spoiler", "Voltex", "spoiler-old", "spoiler-wing"),
    ("Carbon Fiber Hood, Vented", "Seibon", "lip-kit-old", "hood"),
    ("Fender Flares, Wide Body Set", "Liberty Walk", "fender-flares-old", "fender-flares"),
    # Plural / hyphen variants (regression: codex caught these returning None)
    ("Side Skirts, Carbon Fiber Pair", "Seibon", None, "side-skirts"),
    ("Rear Diffusers Set", "Voltex", None, "rear-diffuser"),
    ("Carbon Hoods", "Seibon", None, "hood"),

    # Lighting
    ("Diode Dynamics SS3 Pro Fog Light", "Diode Dynamics", "headlights-old", "fog-lights"),
    ("Fog Lights Pair", "Generic", None, "fog-lights"),
    ("LED Headlight Assembly", "Morimoto", "headlights-old", "headlights"),
    ("LED Taillight Set, Smoked", "Anzo", "taillights-old", "taillights"),
    ("LED Bulb Kit H11", "Diode Dynamics", "headlights-old", "led-bulbs"),
    ("LED Bulbs, 6000K Set", "Diode Dynamics", None, "led-bulbs"),

    # Tuning
    ("COBB Accessport V3", "COBB", "tune-old", "ecu-tune"),
    ("AEM Wideband UEGO Gauge", "AEM", "tune-old", "wideband-gauge"),

    # Brakes (no parts in catalog yet — confirm rules trigger anyway)
    ("Hawk HP+ Brake Pads, Front", "Hawk", None, "brake-pads"),
    ("StopTech Slotted Brake Rotor", "StopTech", None, "brake-rotors"),
    ("Stainless Steel Brake Lines", "Goodridge", None, "brake-lines"),
    ("StopTech ST-40 Big Brake Kit", "StopTech", None, "big-brake-kit"),
])
def test_heuristic_returns_expected_slug(name, brand, current_slug, expected):
    assert classify_heuristic(name, brand, current_slug) == expected


def test_unmatched_returns_none():
    # Generic/ambiguous part name with no current-slug prior.
    assert classify_heuristic("Random Universal Adapter", "Generic", None) is None


def test_fuel_system_parts_classify_to_fuel_system_leaf():
    # User flagged "Hondata Fuel System Upgrade" landing on ecu-tune. Now
    # we have a real fuel-system leaf — fuel pumps, injectors, rails,
    # pressure regulators, and lines route there directly via heuristic
    # so the LLM never has to guess.
    assert classify_heuristic("2017+ Civic Type R/Integra Type S Hondata Fuel System Upgrade", "27WON", None) == "fuel-system"
    assert classify_heuristic("PRL High Volume Fuel Pump Kit", "PRL", None) == "fuel-system"
    assert classify_heuristic("Magnum Fuel Injector Set 1000cc", "Injector Dynamics", None) == "fuel-system"
    assert classify_heuristic("Honda S2000 Fuel Rail Upgrade", "Skunk2", None) == "fuel-system"
    assert classify_heuristic("Adjustable Fuel Pressure Regulator", "Aeromotive", None) == "fuel-system"


def test_fuel_system_plural_titles_classify_to_fuel_system_leaf():
    # Codex regression: the original rule was singular-only, so titles
    # like "fuel injectors" / "fuel lines" / "fuel pumps" / "fuel rails"
    # fell through to LLM/misc. Plural forms must hit the heuristic.
    assert classify_heuristic("ID1050x Fuel Injectors Set", "Injector Dynamics", None) == "fuel-system"
    assert classify_heuristic("Stainless Fuel Lines, Braided", "Russell", None) == "fuel-system"
    assert classify_heuristic("Walbro Fuel Pumps Twin Setup", "Walbro", None) == "fuel-system"
    assert classify_heuristic("Honda K-Series Fuel Rails", "Skunk2", None) == "fuel-system"
    assert classify_heuristic("Aeromotive Fuel Regulators", "Aeromotive", None) == "fuel-system"


def test_intake_old_prior_was_dropped_to_force_subtype_resolution():
    # Old `intake` leaf was an aggregation of 7 new leaves. Codex flagged 53.7%
    # of `intake-old` parts as falling through to cold-air-intake by default
    # when the regex didn't match — silently dumping snorkels, throttle bodies,
    # vacuum pumps into the CAI bucket. Removing the intake-old prior pushes
    # those to the LLM or misc instead.
    assert classify_heuristic("Air Intake Snorkel", "Honda", "intake-old") is None
    assert classify_heuristic("Throttle Body Spacer", "Generic", "intake-old") is None


def test_current_slug_is_a_prior_for_truly_ambiguous_names():
    # "Front Shock" alone has no specific rule; prior-default falls back to
    # the current_slug's mapped leaf.
    assert classify_heuristic("Bilstein B6 Front Shock", "Bilstein", "coilovers-old") == "coilovers"
    # Same name, different prior — uses springs-old's default, not coilovers.
    assert classify_heuristic("Bilstein B6 Front Shock", "Bilstein", "springs-old") == "lowering-springs"


from unittest.mock import patch
from scraper.category_classifier import classify_with_llm, classify


def test_llm_fallback_returns_one_of_the_valid_leaves(monkeypatch, tmp_path):
    """When heuristic and prior both miss, LLM is called and result is filtered
    against the known leaf set."""
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "intercooler"
        out = classify_with_llm("Mystery Aluminum Box", "Mishimoto", current_slug=None)
        assert out == "intercooler"


def test_llm_returning_invalid_slug_yields_none(monkeypatch, tmp_path):
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "fake-slug-not-a-leaf"
        out = classify_with_llm("Strange Thing", "Brand", current_slug=None)
        assert out is None


def test_classify_runs_heuristic_first_then_llm(monkeypatch, tmp_path):
    """Heuristic should win for a clearly-named part; LLM should not be called."""
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "intercooler"
        out = classify("AEM Cold Air Intake", "AEM", "intake-old")
        assert out == "cold-air-intake"
        mock_llm.assert_not_called()


def test_classify_falls_through_to_llm_when_heuristic_misses(monkeypatch, tmp_path):
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "wheels"
        out = classify("Mystery Round Metal Thing", "GenericBrand", current_slug=None)
        assert out == "wheels"
        mock_llm.assert_called_once()


def test_llm_api_failure_returns_none_does_not_cache(monkeypatch, tmp_path):
    """An API error must NOT crash the caller and MUST NOT poison the cache."""
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.side_effect = RuntimeError("simulated API outage")
        out = classify_with_llm("Mystery Item", "Brand", current_slug=None)
        assert out is None
        # Cache directory should be empty — error path must not write.
        cache_dir = tmp_path / "cache"
        if cache_dir.exists():
            assert list(cache_dir.iterdir()) == []


def test_llm_cache_busts_when_classifier_version_changes(monkeypatch, tmp_path):
    """A cache hit from an older classifier version must NOT be replayed.

    Codex regression: cache was keyed only on (name, brand) so a maintenance
    rerun under new prompt or rule logic kept serving stale classifications.
    """
    import json as _json
    import hashlib as _hashlib
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", cache_dir)
    # Plant a stale cache entry with the old (un-versioned) format under
    # what would have been the old key.
    name, brand, current = "Some Part", "Some Brand", None
    new_key = _hashlib.sha256(
        f"v3|{name}|{brand}|".encode("utf-8")
    ).hexdigest()[:32]
    (cache_dir / f"{new_key}.json").write_text(
        _json.dumps({"slug": "wheels"}),  # no version field — stale
        encoding="utf-8",
    )
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "intercooler"
        out = classify_with_llm(name, brand, current_slug=current)
        assert out == "intercooler"  # fresh LLM call, not stale cache
        mock_llm.assert_called_once()


def test_llm_cache_key_includes_current_slug(monkeypatch, tmp_path):
    """Same name+brand with different current_slug must NOT share a cache entry."""
    monkeypatch.setattr("scraper.category_classifier._LLM_CACHE_DIR", tmp_path / "cache")
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.side_effect = ["intercooler", "wheels"]
        a = classify_with_llm("Generic Part", "Brand", current_slug="intercooler-old")
        b = classify_with_llm("Generic Part", "Brand", current_slug="wheels-old")
        assert a == "intercooler"
        assert b == "wheels"
        assert mock_llm.call_count == 2  # both hit the LLM, no shared cache
