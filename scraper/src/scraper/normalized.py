from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel


class WheelSpecs(BaseModel):
    diameter_in: int
    width_in: float
    offset_mm: int
    bolt_pattern: str
    center_bore_mm: float


class TireSpecs(BaseModel):
    section_width: int
    aspect: int
    diameter: int

    @classmethod
    def from_size_string(cls, s: str) -> "TireSpecs":
        m = re.match(r"\s*(\d{3})/(\d{2})\s*[Rr]\s*(\d{2})\s*", s)
        if not m:
            raise ValueError(f"unrecognized tire size: {s!r}")
        return cls(section_width=int(m[1]), aspect=int(m[2]), diameter=int(m[3]))


class NormalizedPart(BaseModel):
    vendor: str
    vendor_sku: str
    vendor_url: str
    brand: str
    model: str
    name: str
    category_hint: str
    image_url: Optional[str] = None
    price_cents: Optional[int] = None
    in_stock: bool = True
    fitment_text: str = ""
    wheel_specs: Optional[WheelSpecs] = None
    tire_specs: Optional[TireSpecs] = None
