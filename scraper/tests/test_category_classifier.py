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

    # Lighting
    ("Diode Dynamics SS3 Pro Fog Light", "Diode Dynamics", "headlights-old", "fog-lights"),
    ("LED Headlight Assembly", "Morimoto", "headlights-old", "headlights"),
    ("LED Taillight Set, Smoked", "Anzo", "taillights-old", "taillights"),
    ("LED Bulb Kit H11", "Diode Dynamics", "headlights-old", "led-bulbs"),

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


def test_current_slug_is_a_prior_for_truly_ambiguous_names():
    # "Front Shock" alone has no specific rule; prior-default falls back to
    # the current_slug's mapped leaf.
    assert classify_heuristic("Bilstein B6 Front Shock", "Bilstein", "coilovers-old") == "coilovers"
    # Same name, different prior — uses springs-old's default, not coilovers.
    assert classify_heuristic("Bilstein B6 Front Shock", "Bilstein", "springs-old") == "lowering-springs"


from unittest.mock import patch
from scraper.category_classifier import classify_with_llm, classify


def test_llm_fallback_returns_one_of_the_valid_leaves():
    """When heuristic and prior both miss, LLM is called and result is filtered
    against the known leaf set."""
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "intercooler"
        out = classify_with_llm("Mystery Aluminum Box", "Mishimoto", current_slug=None)
        assert out == "intercooler"


def test_llm_returning_invalid_slug_yields_none():
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "fake-slug-not-a-leaf"
        out = classify_with_llm("Strange Thing", "Brand", current_slug=None)
        assert out is None


def test_classify_runs_heuristic_first_then_llm():
    """Heuristic should win for a clearly-named part; LLM should not be called."""
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "intercooler"
        out = classify("AEM Cold Air Intake", "AEM", "intake-old")
        assert out == "cold-air-intake"
        mock_llm.assert_not_called()


def test_classify_falls_through_to_llm_when_heuristic_misses():
    with patch("scraper.category_classifier._call_deepseek") as mock_llm:
        mock_llm.return_value = "wheels"
        out = classify("Mystery Round Metal Thing", "GenericBrand", current_slug=None)
        assert out == "wheels"
        mock_llm.assert_called_once()
