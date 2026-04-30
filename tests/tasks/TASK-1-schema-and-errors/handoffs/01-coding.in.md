# Coding Brief: TASK-1 — OutputRecord schema and RowError model

## Branch
Create and work on: `feature/TASK-1-schema-and-errors` (branch from `develop`)

## What to build
See full brief at: tasks/TASK-1-schema-and-errors/brief.md

### Files to create (all paths relative to /var/home/leo/Documents/ice/)

**src/vendor_normalizer/__init__.py** — empty, just marks the package

**src/vendor_normalizer/schema.py** — OutputRecord pydantic v2 model:
```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

class OutputRecord(BaseModel):
    sku: str = Field(min_length=1)
    product_name: str
    quantity: int = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    delivery_date: date
    vendor_id: str

    @field_validator("sku", "product_name", "currency", mode="before")
    @classmethod
    def strip_strings(cls, v):
        return v.strip() if isinstance(v, str) else v
```

**src/vendor_normalizer/errors.py** — RowError pydantic v2 model:
```python
class RowError(BaseModel):
    row_index: int
    field: str | None
    value: str | None
    error: str
    suggestion: str | None
```

**src/vendor_normalizer/sources/__init__.py** — stub (raise NotImplementedError or pass)
**src/vendor_normalizer/sources/xlsx.py** — stub
**src/vendor_normalizer/sources/gsheet.py** — stub

**tests/__init__.py** — empty
**tests/fixtures/.gitkeep** — empty
**tests/test_schema.py** — pytest tests covering:
- Valid OutputRecord construction with all fields
- strip_strings validator strips leading/trailing whitespace on sku, product_name, currency
- Empty sku raises ValidationError
- Negative quantity raises ValidationError
- Lowercase currency raises ValidationError (pattern mismatch)
- Negative unit_price raises ValidationError
- Valid RowError construction with all fields including None fields

## Constraints
- Working directory for all commands: /var/home/leo/Documents/ice/
- Use `uv run pytest tests/test_schema.py` to verify tests pass
- Use `uv run ruff check src/ tests/` to lint before committing
- Commit message: `feat(schema): add OutputRecord and RowError pydantic models`
- Open PR from feature/TASK-1-schema-and-errors into develop

## Done condition
Report back with:
- List of files created
- pytest output showing tests pass
- Coverage % for schema.py and errors.py
- PR URL or confirmation PR opened
