from pathlib import Path

from scraper.vendors.win27 import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "27won"
BASE = "https://store.27won.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_civic_si_11th_gen.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/civic-si-11th-gen/")

    # 27WON chassis pages render ~15 products as ``a.product-title`` cards
    # server-side (no JS rendering needed). Healthy page should yield at
    # least 5 PDP URLs.
    assert len(urls) >= 5, f"only found {len(urls)} product URLs"
    # All absolute, on the storefront host, and end with .html.
    assert all(u.startswith(f"{BASE}/") for u in urls), urls[:3]
    assert all(u.endswith(".html") for u in urls), urls[:3]
    # No duplicates.
    assert len(set(urls)) == len(urls)


def test_parse_product_page_civic_si_turbo_extracts_required_fields():
    url = f"{BASE}/2022-civic-integra-1-5t-turbocharger-upgrade.html"
    html = (FIXTURES / "product_si_turbo.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url == url, part.vendor_url
    assert part.vendor_sku == "L15-6-671-12"
    # JSON-LD doesn't carry brand; we default to "27WON" since everything
    # in the store is in-house product.
    assert part.brand == "27WON"
    assert "Civic" in part.name and "1.5T" in part.name
    # AggregateOffer top-level price (default variant).
    assert part.price_cents == 179999  # $1,799.99
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # Fitment text should retain Si + 1.5T context for the regex/LLM tiers.
    assert part.fitment_text
    assert "Civic" in part.fitment_text
    assert "1.5T" in part.fitment_text or "Si" in part.fitment_text


def test_parse_product_page_type_r_turbo_extracts_required_fields():
    url = f"{BASE}/civic-type-r-turbocharger-dropin-upgrade-fk8-fl5-de5-kuro.html"
    html = (FIXTURES / "product_type_r_turbo.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url == url, part.vendor_url
    assert part.vendor_sku == "FK8-6-571-10"
    assert part.brand == "27WON"
    assert "Type R" in part.name or "Type-R" in part.name
    assert part.price_cents == 219999  # $2,199.99
    assert part.in_stock is True
    assert part.image_url
    # Type R fitment should mention chassis codes (FK8/FL5).
    assert part.fitment_text
    assert "FK8" in part.fitment_text or "FL5" in part.fitment_text
