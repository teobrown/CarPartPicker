from pathlib import Path

from scraper.vendors.flyin_miata import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "flyin-miata"
BASE = "https://flyinmiata.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_handling.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/collections/na-handling")

    # FM's ``var meta`` blob is empty on collection pages, so we anchor-scrape.
    # Even the slimmest categories (e.g. NA-handling) carry ~8 unique products.
    assert len(urls) >= 1, f"only found {len(urls)} product URLs"
    # All absolute, on the bare-apex flyinmiata.com host (FM's canonical
    # form), and look like /products/<handle> paths.
    assert all(u.startswith(f"{BASE}/products/") for u in urls), urls[:3]
    for u in urls[:5]:
        path = u[len(BASE):]
        assert path.startswith("/products/") and path.count("/") == 2, u
    # No duplicates.
    assert len(set(urls)) == len(urls)


def test_parse_product_page_kogeki_na_nb_wheels_extracts_required_fields():
    url = f"{BASE}/products/kogeki-15x9-flow-formed-wheels-for-na-nb"
    html = (FIXTURES / "product_kogeki_na_nb_wheels.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    # FM's canonical link is the bare-apex form that already matches the
    # seeded vendor.baseUrl host — no www-coercion needed.
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    assert part.vendor_sku == "16-53040~GM"
    # FM resells Konig-built wheels under the Kōgeki brand for FM.
    assert part.brand and len(part.brand) > 0
    assert "geki" in part.name.lower() or "wheel" in part.name.lower()
    assert part.price_cents == 20900  # $209.00
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # Fitment text should retain NA/NB chassis tokens — Miata parts split
    # cleanly on chassis and the regex/LLM tiers latch on those.
    assert "NA" in part.fitment_text or "NB" in part.fitment_text
    assert part.fitment_text  # non-empty


def test_parse_product_page_nd_fox_suspension_extracts_required_fields():
    url = f"{BASE}/products/flyin-miata-fox-suspension-for-nd-chassis"
    html = (FIXTURES / "product_flyin_miata_fox_suspension_for_nd_chassis.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/products/"), part.vendor_url
    assert part.vendor_sku == "13-16175~RF"
    # In-house FM part — brand should resolve to "Flyin' Miata".
    assert "Flyin" in part.brand
    assert "ND" in part.name
    assert part.price_cents == 239900  # $2399.00
    assert part.in_stock is True
    assert part.image_url
    # ND fitment text should carry the ND chassis token.
    assert "ND" in part.fitment_text
