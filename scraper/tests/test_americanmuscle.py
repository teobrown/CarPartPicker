from pathlib import Path

from scraper.vendors.americanmuscle import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "americanmuscle"
BASE = "https://www.americanmuscle.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_intakes.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/cold-air-intakes.html")

    # Sanity: should find a meaningful number of products on a category page
    assert len(urls) >= 5, f"only found {len(urls)} product URLs"
    # All absolute, on AmericanMuscle, and look like product detail pages
    assert all(u.startswith(f"{BASE}/") for u in urls), urls[:3]
    assert all(u.endswith(".html") for u in urls), urls[:3]
    # All host-root single-segment paths (no subdirectories like /aftermarket-*)
    for u in urls[:5]:
        path = u[len(BASE):]
        assert path.startswith("/") and path.count("/") == 1, u
    # No duplicates
    assert len(set(urls)) == len(urls)


def test_parse_product_page_intake_extracts_required_fields():
    url = f"{BASE}/sr-aluminum-cai-0509gt.html"
    html = (FIXTURES / "product_41334.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url == url
    assert part.vendor_sku == "41334"
    assert part.brand == "SR Performance"
    assert "Cold Air Intake" in part.name
    assert part.price_cents == 14999  # $149.99
    assert part.in_stock is True
    assert part.image_url is not None and part.image_url.startswith("http")
    # Fitment text should carry the H1 fitment hint plus the JSON-LD description.
    assert "Mustang" in part.fitment_text
    assert "05-09" in part.fitment_text or "2005" in part.fitment_text


def test_parse_product_page_exhaust_extracts_required_fields():
    url = (
        f"{BASE}/cnl-mustang-muffler-delete-axle-back-polished-tips-412422.html"
    )
    html = (FIXTURES / "product_412422.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_sku == "412422"
    assert part.brand  # JSON-LD brand
    assert part.name
    assert part.price_cents == 19999  # $199.99
    assert part.in_stock is True
    assert part.image_url
    assert "Mustang" in part.fitment_text
