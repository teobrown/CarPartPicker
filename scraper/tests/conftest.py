import os
from pathlib import Path

ENV_LOCAL = Path(__file__).resolve().parents[2] / ".env.local"
if ENV_LOCAL.exists() and "DATABASE_URL" not in os.environ:
    for line in ENV_LOCAL.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)
