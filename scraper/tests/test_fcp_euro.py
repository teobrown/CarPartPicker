from pathlib import Path

from scraper.vendors.fcp_euro import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fcp-euro"
BASE = "https://www.fcpeuro.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_air-intake.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/Volkswagen-parts/Air-Intake/")

    # Sanity: should find a meaningful number of products on a category page
    assert len(urls) >= 5, f"only found {len(urls)} product URLs"
    # All absolute, on FCP Euro, and pointing at /products/
    assert all(u.startswith(f"{BASE}/") for u in urls), urls[:3]
    assert all("/products/" in u for u in urls), urls[:3]
    # No duplicates
    assert len(set(urls)) == len(urls)


def test_parse_product_page_intercooler_extracts_required_fields():
    url = (
        f"{BASE}/products/"
        "vw-performance-intercooler-kit-034motorsport-kit-01804"
    )
    html = (FIXTURES / "product_KIT-01804.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url == url
    assert part.vendor_sku == "KIT-01804"
    assert part.brand == "034Motorsport"
    assert "Intercooler" in part.name
    assert part.price_cents == 118300  # $1,183.00
    assert part.in_stock is True
    assert part.image_url is not None and part.image_url.startswith("http")
    assert part.category_hint == "Air Intake"
    # The fallback fitment text uses the JSON-LD description, which references VW/Audi.
    assert "Volkswagen" in part.fitment_text or "Audi" in part.fitment_text


def test_parse_product_page_intake_manifold_extracts_required_fields():
    url = (
        f"{BASE}/products/"
        "audi-vw-tsi-intake-manifold-kit-febi-kit-01474"
    )
    html = (FIXTURES / "product_KIT-01474.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_sku == "KIT-01474"
    assert part.brand  # JSON-LD says "Genuine VW"
    assert part.name
    assert part.price_cents == 59206  # $592.06
    assert part.in_stock is True
    assert part.image_url
    assert part.category_hint == "Air Intake"
