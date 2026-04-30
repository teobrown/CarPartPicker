import pytest
from scraper.fitment_parser import parse_fitment, ParsedFitment


@pytest.mark.parametrize("text,expected", [
    (
        "Fits 2015-2021 Subaru WRX",
        [ParsedFitment(make="Subaru", model="WRX",
                       year_start=2015, year_end=2021,
                       trims_included=None, status="fits", caveat=None)],
    ),
    (
        "Fits 2022+ Subaru WRX (Premium, Limited)",
        [ParsedFitment(make="Subaru", model="WRX",
                       year_start=2022, year_end=None,
                       trims_included=["Premium", "Limited"],
                       status="fits", caveat=None)],
    ),
    (
        "Fits 2017-2021 Honda Civic Type R FK8",
        [ParsedFitment(make="Honda", model="Civic Type R",
                       year_start=2017, year_end=2021,
                       trims_included=None, status="fits", caveat=None)],
    ),
    (
        "Fits 2015-2023 Ford Mustang GT (requires fender rolling)",
        [ParsedFitment(make="Ford", model="Mustang", year_start=2015,
                       year_end=2023, trims_included=["GT"],
                       status="fits_with_caveat",
                       caveat="requires fender rolling")],
    ),
    ("", []),
    ("Fits all cars", []),
])
def test_parse_fitment(text, expected):
    assert parse_fitment(text) == expected
