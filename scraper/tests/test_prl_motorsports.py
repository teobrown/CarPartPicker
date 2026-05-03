from pathlib import Path

from scraper.vendors.prl_motorsports import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prl-motorsports"
BASE = "https://www.prlmotorsports.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_intake.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/collections/intake")

    # PRL category pages embed the full ~50-product listing in a
    # ``var meta = {...};`` blob (the visible cards are JS-rendered),
    # so we should pull at least a few dozen on a healthy page.
    assert len(urls) >= 10, f"only found {len(urls)} product URLs"
    # All absolute, on the www host (we coerce away PRL's apex canonical)
    # and look like /products/<handle> paths.
    assert all(u.startswith(f"{BASE}/products/") for u in urls), urls[:3]
    for u in urls[:5]:
        path = u[len(BASE):]
        assert path.startswith("/products/") and path.count("/") == 2, u
    # No duplicates.
    assert len(set(urls)) == len(urls)


def test_parse_product_page_type_r_fk8_intake_extracts_required_fields():
    url = f"{BASE}/products/2017-civic-type-r-fk8-stage-1-intake-system"
    html = (FIXTURES / "product_type_r_fk8_stage1_intake.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    # Canonical link points at the apex; we coerce to www so the stored
    # vendor_url matches the seeded vendor.baseUrl host.
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    assert part.vendor_sku == "PRL-HCR-INT-S1"
    assert part.brand == "PRL Motorsports"
    assert "Type-R" in part.name and "FK8" in part.name
    assert part.price_cents == 14900  # $149.00
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # Fitment text should retain the chassis + year-range tokens so the
    # regex / LLM tiers can latch on.
    assert "FK8" in part.fitment_text
    assert "2017" in part.fitment_text or "2021" in part.fitment_text


def test_parse_product_page_civic_si_intake_extracts_required_fields():
    url = f"{BASE}/products/2017-honda-civic-si-1-5t-cobra-cold-air-intake-system"
    html = (FIXTURES / "product_civic_si_cobra_intake.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    assert part.vendor_sku == "PRL-HC10-INT-CAI-B"
    assert part.brand == "PRL Motorsports"
    assert "Si" in part.name and "1.5T" in part.name
    assert part.price_cents == 43000  # $430.00
    # First (rich) JSON-LD block reports OutOfStock.
    assert part.in_stock is False
    assert part.image_url
    # Si fitment text should carry both Si trim and 1.5T engine context.
    assert "Si" in part.fitment_text
    assert "1.5T" in part.fitment_text or "Civic" in part.fitment_text
