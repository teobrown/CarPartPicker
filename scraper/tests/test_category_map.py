from scraper.category_map import map_category


def test_exact_match_intake():
    assert map_category("Cold Air Intake Systems") == "intake"


def test_exact_match_catback():
    assert map_category("Cat-Back Exhaust Systems") == "catback"


def test_fuzzy_match_when_no_exact():
    assert map_category("Performance Cold-Air Intake System") == "intake"


def test_unknown_returns_none():
    assert map_category("Random Truck Accessory Bundle") is None
