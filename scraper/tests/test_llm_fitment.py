from unittest.mock import MagicMock, patch

import pytest

from scraper.llm_fitment import (
    extract_fitment_from_html,
    parse_fitment_with_llm,
)


def test_parse_fitment_with_llm_returns_empty_when_no_api_key(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    # Point the cache somewhere ephemeral so prior runs don't pollute the test.
    monkeypatch.setattr("scraper.llm_fitment.CACHE_DIR", tmp_path)
    out = parse_fitment_with_llm("Fits 2015-2021 Subaru WRX")
    assert out == []  # no key -> fail open


def test_parse_fitment_with_llm_returns_empty_for_empty_text():
    out = parse_fitment_with_llm("")
    assert out == []


def test_parse_fitment_with_llm_filters_unsupported_platforms(
    monkeypatch, tmp_path
):
    """LLM hallucinates a Forester (not in our 11 supported platforms);
    a real WRX rule comes through. Only the WRX should survive."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr("scraper.llm_fitment.CACHE_DIR", tmp_path)

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        '{"rules":['
        '{"make":"Subaru","model":"Forester","year_start":2018,'
        '"year_end":2020,"status":"fits"},'
        '{"make":"Subaru","model":"WRX","year_start":2015,'
        '"year_end":2021,"status":"fits"}'
        ']}'
    )

    with patch("scraper.llm_fitment.OpenAI") as fake_oai:
        fake_oai.return_value.chat.completions.create.return_value = fake_resp
        out = parse_fitment_with_llm("Fits Forester and WRX")

    # Forester is not in our supported list -> filtered out; WRX kept.
    assert len(out) == 1
    assert out[0].make == "Subaru"
    assert out[0].model == "WRX"
    assert out[0].year_start == 2015
    assert out[0].year_end == 2021
    assert out[0].status == "fits"


def test_extract_fitment_from_html_strips_noise_and_caches(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr("scraper.llm_fitment.CACHE_DIR", tmp_path)
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        '{"rules":[{"make":"Subaru","model":"WRX","year_start":2015,'
        '"year_end":2021,"status":"fits"}]}'
    )
    with patch("scraper.llm_fitment.OpenAI") as fake_oai:
        fake_oai.return_value.chat.completions.create.return_value = fake_resp
        out1 = extract_fitment_from_html(
            "<script>junk</script><p>Fits 2015-2021 Subaru WRX</p>"
        )
    assert len(out1) == 1
    assert out1[0].model == "WRX"
    # second call should hit cache, not the API
    with patch("scraper.llm_fitment.OpenAI") as fake_oai2:
        out2 = extract_fitment_from_html(
            "<script>junk</script><p>Fits 2015-2021 Subaru WRX</p>"
        )
    assert len(out2) == 1
    assert fake_oai2.return_value.chat.completions.create.call_count == 0
