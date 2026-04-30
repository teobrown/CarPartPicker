# CarPartPicker Scraper

Python service that scrapes vendor parts catalogs (currently: Summit Racing), normalizes them into a `NormalizedPart` schema, and upserts into Postgres.

## Setup

Requires Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).

```bash
cd scraper
uv sync --all-groups
```

## Running

The orchestrator entry point will be wired up in a later task. For now the package is a skeleton:

```bash
uv run python -c "import scraper; print(scraper.__version__)"
# 0.1.0
```

## Tests

```bash
uv run pytest
```

## Layout

```
scraper/
├── src/scraper/
│   ├── __init__.py
│   └── vendors/         # one module per vendor (summit, fcp, ...)
└── tests/
    └── fixtures/        # captured HTML for offline tests
```
