from pathlib import Path

from scraper.vendors.rallysport_direct import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "rallysport-direct"
BASE = "https://www.rallysportdirect.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_intakes.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/collections/cold-air-intakes")

    # Sanity: a real Shopify collection page lists ~24-32 products
    assert len(urls) >= 5, f"only found {len(urls)} product URLs"
    # All absolute, on RSD, and look like product detail pages
    assert all(u.startswith(f"{BASE}/products/") for u in urls), urls[:3]
    # All single-segment /products/<slug> paths (no nested routes)
    for u in urls[:5]:
        path = u[len(BASE):]
        assert path.startswith("/products/") and path.count("/") == 2, u
    # No duplicates
    assert len(set(urls)) == len(urls)


def test_parse_product_page_wrx_intake_extracts_required_fields():
    url = f"{BASE}/products/cobb-sf-intake-system-2015-2021-subaru-wrx"
    html = (FIXTURES / "product_cobb_sf_intake_wrx.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url == url
    assert part.vendor_sku == "COBB745120"
    assert part.brand == "COBB"
    assert "Intake" in part.name
    assert "WRX" in part.name
    assert part.price_cents == 54500  # $545.00
    assert part.in_stock is True
    assert part.image_url is not None and part.image_url.startswith("http")
    # Fitment text should carry the year range from the product name so
    # the fitment regex parser can latch on.
    assert "WRX" in part.fitment_text
    assert "2015" in part.fitment_text or "2021" in part.fitment_text


def test_parse_product_page_wrx_sti_intake_extracts_required_fields():
    url = f"{BASE}/products/cobb-02-07-wrx-sti-black-sf-intake"
    html = (FIXTURES / "product_cobb_black_sf_intake_wrx_sti.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_sku == "COBB712100"
    assert part.brand == "COBB"
    assert part.name
    assert part.price_cents == 29000  # $290.00
    assert part.in_stock is True
    assert part.image_url
    # Names like "Cobb Black SF Intake -2002-2007 Subaru WRX / STi" should
    # leave both WRX and STi context in fitment text.
    assert "WRX" in part.fitment_text or "STi" in part.fitment_text
