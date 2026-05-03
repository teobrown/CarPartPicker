from pathlib import Path

from scraper.vendors.iag_performance import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "iag-performance"
BASE = "https://www.iagperformance.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_catback.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/engine/exhausts/cat-back/")

    # IAG's BigCommerce Stencil category pages render 30 cards per page.
    # Even with a future theme tweak we expect well above 15.
    assert len(urls) >= 15, f"only found {len(urls)} product URLs"
    # All absolute, on the IAG host. PDP slugs sit at the site root, not
    # under any of the category-prefixed system paths.
    for u in urls[:5]:
        assert u.startswith(f"{BASE}/"), u
        path = u[len(BASE):]
        assert not path.startswith(
            (
                "/engine/",
                "/suspension/",
                "/brakes/",
                "/drivetrain/",
                "/iag-parts/",
                "/vehicles/",
            )
        ), f"category-style URL leaked through: {u}"
    # No duplicates.
    assert len(set(urls)) == len(urls)
    # Trailing slash is preserved on PDP URLs (IAG's canonical form).
    assert all(u.endswith("/") for u in urls), [u for u in urls if not u.endswith("/")][
        :3
    ]


def test_parse_product_page_cobb_brz_catback_extracts_required_fields():
    url = (
        f"{BASE}/cobb-titanium-cat-back-exhaust-for-2013-24-subaru-brz-toyota-gt86"
        f"-gr86-scion-frs-5z1160/"
    )
    html = (FIXTURES / "product_cobb_catback_brz.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/"), part.vendor_url
    assert part.vendor_url.endswith("/"), part.vendor_url
    # MPN is the clean manufacturer part number (sku ships with a noisy
    # ``ds_FMKH_`` BigCommerce dropship prefix; we prefer mpn).
    assert part.vendor_sku == "5Z1160", part.vendor_sku
    # Brand resolves through the dict-form JSON-LD payload.
    assert part.brand == "COBB", part.brand
    assert "Subaru BRZ" in part.name
    assert part.price_cents == 164000  # $1640.00
    assert part.in_stock is True
    assert part.image_url and part.image_url.startswith("http")
    # Multi-platform PDP: BRZ + GR86 + FR-S all named in the title; we
    # need every chassis token visible to the fitment tiers.
    ft = part.fitment_text
    assert "BRZ" in ft
    assert "GR86" in ft or "GR 86" in ft
    assert "FR-S" in ft or "FR S" in ft or "FRS" in ft
    assert "2013" in ft


def test_parse_product_page_iag_aos_wrx_extracts_iag_house_brand():
    url = f"{BASE}/iag-air-oil-separator-aos-fits-2022-24-subaru-wrx/"
    html = (FIXTURES / "product_iag_aos_wrx.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    # IAG-house parts brand to "IAG Performance" via the JSON-LD dict
    # form. This is the Subaru-specialist signature product line that
    # RallySport Direct doesn't carry.
    assert part.brand == "IAG Performance", part.brand
    # MPN = clean part number (sku ships with a color suffix
    # IAG-ENG-7188BK; mpn drops it).
    assert part.vendor_sku == "IAG-ENG-7188", part.vendor_sku
    # Price is a non-integer dollar amount ($499.99) — verify the
    # integer-dollar JSON-LD parsing on the BRZ catback didn't regress
    # the float parsing path.
    assert part.price_cents == 49999, part.price_cents
    assert part.in_stock is True
    # WRX year-range tokens visible to the fitment tiers.
    ft = part.fitment_text
    assert "WRX" in ft
    assert "2022" in ft
    # PDPs without a trailing -<part-number>/ suffix still parse cleanly
    # — vendor_url should round-trip the URL we passed in (slug only,
    # no -DDD/ suffix).
    assert part.vendor_url.endswith("subaru-wrx/"), part.vendor_url
