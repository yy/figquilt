from typing import Optional, List, Tuple, Union
from pathlib import Path
from pydantic import BaseModel, Field, field_validator

class LabelStyle(BaseModel):
    enabled: bool = True
    auto_sequence: bool = True
    font_family: str = "Helvetica"
    font_size_pt: float = 8.0
    offset_x_mm: float = 2.0
    offset_y_mm: float = 2.0
    bold: bool = True
    uppercase: bool = True

class Panel(BaseModel):
    id: str
    file: Path
    x: float
    y: float
    width: float
    height: Optional[float] = None  # If None, compute from aspect ratio
    label: Optional[str] = None
    label_style: Optional[LabelStyle] = None

    @field_validator("file")
    @classmethod
    def validate_file(cls, v: Path) -> Path:
        # We don't check existence here to allow validation without side effects,
        # but we could add it if desired. The parser/logic will check it.
        return v

class Page(BaseModel):
    width: float
    height: float
    units: str = "mm"
    dpi: int = 300
    background: Optional[str] = "white"
    label: LabelStyle = Field(default_factory=LabelStyle)

class Layout(BaseModel):
    page: Page
    panels: List[Panel]
