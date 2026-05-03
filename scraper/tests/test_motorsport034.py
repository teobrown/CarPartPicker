from pathlib import Path

from scraper.vendors.motorsport034 import (
    VENDOR_SLUG,
    parse_category_page,
    parse_product_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "034motorsport"
BASE = "https://www.034motorsport.com"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_intakes.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    urls = parse_category_page(html, base_url=f"{BASE}/cold-air-intakes.html")

    # 034's Magento 2 cold-air-intakes category renders 24 product
    # cards inline. Even with theme tweaks we expect well above 15.
    assert len(urls) >= 15, f"only found {len(urls)} product URLs"
    # All absolute, on the 034 host. PDP slugs sit at the site root
    # with the ``.html`` suffix (Magento convention).
    for u in urls[:5]:
        assert u.startswith(f"{BASE}/"), u
        assert u.endswith(".html"), u
        path = u[len(BASE):]
        # Drop any nav/blog/service paths that might leak through the
        # selector — must NOT start with these prefixes.
        assert not path.startswith(
            ("/blog/", "/service/", "/customer/", "/checkout/")
        ), f"non-PDP path leaked through: {u}"
    # No duplicates.
    assert len(set(urls)) == len(urls)


def test_parse_product_page_turbo_inlet_aggregate_offer_extracts_required_fields():
    """B9 Audi S4/S5/SQ5 turbo inlet pipe — multi-variant PDP.

    034's multi-variant PDPs (this one ships in two finishes — black
    coated vs. raw) emit an ``AggregateOffer`` JSON-LD shape with a
    nested ``offers`` array. We pick the first concrete Offer and
    fall back to ``lowPrice`` when the nested array is empty. Also
    verifies the trailing-slash strip on ``sku``
    (``034-108-5012/`` -> ``034-108-5012``).
    """
    url = f"{BASE}/turbo-inlet-pipe-b9-b9-5-audi-s4-s5-sq5-3-0t.html"
    html = (FIXTURES / "product_turbo_inlet_b9_audi_s4.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.vendor_url.startswith(f"{BASE}/"), part.vendor_url
    assert part.vendor_url.endswith(".html"), part.vendor_url
    # SKU: the JSON-LD payload carries ``"034-108-5012/"`` (trailing
    # slash) — we strip it so the catalog-side dedupe key is clean.
    assert part.vendor_sku == "034-108-5012", part.vendor_sku
    # Brand resolves through the dict-form JSON-LD payload — 034 house
    # brand on every house-engineered part.
    assert part.brand == "034Motorsport", part.brand
    # Multi-variant PDP: first Offer in the nested ``offers`` array
    # has ``price: "129.00"``; we pull that even though ``offers``
    # itself is an AggregateOffer wrapper.
    assert part.price_cents == 12900, part.price_cents
    assert part.in_stock is True
    # Fitment text — multi-platform PDP names every chassis the part
    # fits (B9, B9.5, S4, S5, SQ5, 3.0T).
    ft = part.fitment_text
    assert "B9" in ft
    assert "S4" in ft and "S5" in ft and "SQ5" in ft
    assert "3.0T" in ft or "3.0t" in ft.lower()


def test_parse_product_page_p34_intake_single_offer_audi_vw_multiplatform():
    """P34 MQB intake — single-Offer PDP with multi-platform fitment.

    Single-variant PDP emits ``offers`` as a bare ``Offer`` dict with
    a top-level ``price`` field (no AggregateOffer wrapper). Verifies
    the cheaper offer-shape branch and the multi-chassis fitment text
    path: this product fits 8V Audi A3/S3, 8S TT/TTS, MkVII VW
    Golf/GTI/R simultaneously, so every chassis token must reach the
    fitment tiers.
    """
    url = (
        f"{BASE}/p34-performance-cold-air-intake-8v-audi-a3-s3-tt-tts-mkvii-"
        f"volkswagen-golf-gti-r-1-8t-2-0t-gen-3-mqb.html"
    )
    html = (FIXTURES / "product_p34_intake_mqb_golf_r.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    part = parse_product_page(html, url=url)

    assert part is not None
    assert part.vendor == VENDOR_SLUG
    assert part.brand == "034Motorsport", part.brand
    # SKU has no trailing slash on this PDP — verify we don't
    # over-strip when there's nothing to strip.
    assert part.vendor_sku == "034-108-1011", part.vendor_sku
    # Price comes from the bare Offer dict (no AggregateOffer wrapper).
    # Float-cents path: $344.70 -> 34470 cents.
    assert part.price_cents == 34470, part.price_cents
    assert part.in_stock is True
    # Multi-chassis VW + Audi fitment — both make-tier names visible.
    ft = part.fitment_text
    assert "Audi" in ft and "Volkswagen" in ft
    # 8V Audi A3/S3 + MkVII VW Golf/GTI/R coverage tokens.
    assert "A3" in ft and "S3" in ft
    assert "Golf" in ft and "GTI" in ft
    assert "MkVII" in ft or "MKVII" in ft.upper()
    # Trailing ``.html`` preserved on canonical URL (Magento convention).
    assert part.vendor_url.endswith(".html"), part.vendor_url
