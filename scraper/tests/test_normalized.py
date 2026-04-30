from scraper.normalized import NormalizedPart, WheelSpecs, TireSpecs


def test_normalized_part_round_trip():
    p = NormalizedPart(
        vendor="summit-racing",
        vendor_sku="SUM-12345",
        vendor_url="https://www.summitracing.com/parts/sum-12345",
        brand="Cobb",
        model="Stage 1 Power Package",
        name="Cobb Stage 1 Power Package - Subaru WRX 2015-2021",
        category_hint="Tuning > ECU Tuning",
        image_url=None,
        price_cents=67500,
        in_stock=True,
        fitment_text="Fits 2015-2021 Subaru WRX, all trims",
        wheel_specs=None,
        tire_specs=None,
    )
    d = p.model_dump()
    assert d["vendor"] == "summit-racing"
    assert d["price_cents"] == 67500


def test_wheel_specs_validates_offset_range():
    w = WheelSpecs(diameter_in=18, width_in=9.5, offset_mm=35,
                   bolt_pattern="5x114.3", center_bore_mm=56.0)
    assert w.offset_mm == 35


def test_tire_specs_parses_size_string():
    t = TireSpecs.from_size_string("245/40R18")
    assert t.section_width == 245
    assert t.aspect == 40
    assert t.diameter == 18
