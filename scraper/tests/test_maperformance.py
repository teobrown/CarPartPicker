from pathlib import Path

from scraper.vendors.maperformance import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "maperformance"
BASE = "https://www.maperformance.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_gr_corolla.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/search?q=gr+corolla&type=product")

    # MAP's keyword-search HTML carries 40+ unique product cards. Even with
    # the conservative dedupe, we expect well above 20.
    assert len(urls) >= 20, f"only found {len(urls)} product URLs"
    # All absolute, on the www-prefixed maperformance.com host (canonical
    # form), and look like /products/<handle> paths.
    assert all(u.startswith(f"{BASE}/products/") for u in urls), urls[:3]
    for u in urls[:5]:
        path = u[len(BASE):]
        assert path.startswith("/products/") and path.count("/") == 2, u
    # No duplicates.
    assert len(set(urls)) == len(urls)


def test_parse_product_page_awe_track_gr_corolla_extracts_required_fields():
    url = f"{BASE}/products/awe-track-edition-exhaust-2023-2024-toyota-gr-corolla-3020-53472"
    html = (FIXTURES / "product_awe_track_gr_corolla.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    # AWE Tuning's MAP-side SKU. ProductGroup.productID and the first
    # variant's sku both carry the "AWE 3020-53472" form.
    assert "3020-53472" in part.vendor_sku
    # Brand resolves through the dict form on the ProductGroup.
    assert "AWE" in part.brand, part.brand
    assert "GR Corolla" in part.name
    assert part.price_cents == 113500  # $1135.00
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # GR Corolla fitment tokens — the regex/LLM tiers latch on these.
    assert "GR Corolla" in part.fitment_text
    assert "2023" in part.fitment_text


def test_parse_product_page_map_header_gr86_extracts_required_fields():
    url = f"{BASE}/products/maperformance-equal-length-header-2013-2024-subaru-brz-toyota-gr86-scion-fr-s-brz86-2g-elh"
    html = (FIXTURES / "product_map_header_gr86.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    assert "BRZ86-2G-ELH" in part.vendor_sku
    # In-house MAP part — brand should resolve to "MAPerformance".
    assert "MAPerformance" in part.brand
    assert part.price_cents == 98900  # $989.00
    assert part.in_stock is True
    assert part.image_url
    # Multi-platform PDP: BRZ + GR86 + FR-S all named in the title; we
    # need every chassis token visible to the fitment tiers.
    ft = part.fitment_text
    assert "BRZ" in ft
    assert "GR86" in ft or "GR 86" in ft
    assert "FR-S" in ft or "FR S" in ft
