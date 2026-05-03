from pathlib import Path

from scraper.vendors.steeda import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "steeda"
BASE = "https://www.steeda.com"


def test_parse_category_page_finds_product_links():
    """The ``category_suspension.html`` fixture is a Searchspring
    native-format JSON response (not actual HTML) — Steeda's category
    pages are JS-rendered and the only stable product list is the
    Searchspring API. We expect 100 product URLs (Searchspring caps
    at 100 per page; the 144-product 2024-2026 Suspension category is
    truncated by the API itself, not the fixture).
    """
    text = (FIXTURES / "category_suspension.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(text, base_url=f"{BASE}/2024-mustang-suspension")

    # Searchspring page-1 returns up to 100 results. We expect well
    # above the 15-anchor threshold IAG / FCP use.
    assert len(urls) >= 50, f"only found {len(urls)} product URLs"
    # All absolute, on the Steeda host. Steeda PDP slugs sit at the
    # site root, never under a year/chassis prefix.
    for u in urls[:5]:
        assert u.startswith(f"{BASE}/"), u
        path = u[len(BASE):]
        assert not path.startswith(
            ("/2024-", "/2023-", "/s550-", "/s650-", "/blog/", "/cdn/")
        ), f"category-style URL leaked through: {u}"
    # No duplicates.
    assert len(set(urls)) == len(urls)
    # No query strings (orchestrator dedup keys on canonical URL).
    assert all("?" not in u for u in urls), [u for u in urls if "?" in u][:3]


def test_parse_product_page_steeda_drag_springs_extracts_required_fields():
    """Steeda-house drag springs PDP. Tests the dict-form ``brand``
    extraction, the ``mpn`` preference over ``sku`` (sku has an
    embedded space — ``"555 8231"`` — vs the clean dashed mpn
    ``"555-8231"``), and the multi-chassis (S550 + S650) fitment text.
    """
    url = f"{BASE}/steeda-555-8231-s550-drag-springs"
    html = (FIXTURES / "product_steeda_drag_springs_gt.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/"), part.vendor_url
    # MPN is the clean dashed manufacturer part number (sku ships with
    # an embedded space — ``"555 8231"`` — that we'd rather not key on).
    assert part.vendor_sku == "555-8231", part.vendor_sku
    # Brand resolves through the dict-form JSON-LD payload.
    assert part.brand == "Steeda Autosports", part.brand
    assert "Mustang GT" in part.name
    assert part.price_cents == 41995  # $419.95
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # Multi-chassis PDP: covers 2015-2026, which spans S550 (2015-2023)
    # and S650 (2024-2026). The fitment tiers need both year tokens
    # visible.
    ft = part.fitment_text
    assert "Mustang" in ft
    assert "2015" in ft or "2016" in ft
    assert "2024" in ft or "2025" in ft or "2026" in ft


def test_parse_product_page_steeda_pro_action_struts_handles_multi_trim_and_html_url():
    """Steeda Pro-Action shocks/struts PDP. This product:

    - Carries a multi-trim fitment string ("GT/V6/EcoBoost") that
      every trim regex tier needs to see.
    - Has a legacy ``.html`` suffix on its URL — Steeda's catalog
      mixes flat-slug PDPs (``/steeda-555-8231-s550-drag-springs``)
      with legacy ``.html``-suffixed PDPs (``/...-555-8157.html``).
      The parser must round-trip the URL we passed in unchanged
      (modulo query strip).
    - Prices well into four digits ($1194.95) — verifies the price
      parsing path doesn't choke on values past $999.99.
    """
    url = f"{BASE}/steeda-s550-mustang-pro-action-shocks-struts-kit-555-8157.html"
    html = (FIXTURES / "product_steeda_pro_action_ecoboost.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.brand == "Steeda Autosports", part.brand
    assert part.vendor_sku == "555-8157", part.vendor_sku
    assert part.price_cents == 119495, part.price_cents
    assert part.in_stock is True
    # Multi-trim coverage: GT, V6, and EcoBoost should all appear in
    # the fitment text (name + JSON-LD description). EcoBoost is the
    # tightest constraint — verifies the description was concatenated
    # in (the name only carries "GT/V6/EcoBoost" because Steeda
    # rolls all three into one PDP).
    ft = part.fitment_text
    assert "EcoBoost" in ft or "Ecoboost" in ft
    assert "GT" in ft
    # Legacy ``.html`` suffix round-trips through the canonical link
    # (BigCommerce emits link[rel=canonical] on every PDP).
    assert part.vendor_url.endswith(("555-8157.html", "555-8157")), part.vendor_url
