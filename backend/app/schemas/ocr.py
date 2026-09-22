"""Schemas for OCR extraction.

Was ``schemas/invoice.py`` and carried the CRUD models for the user-scoped
``/api/invoices`` routes alongside these. Those routes and their table are
gone; what survived is the structured result ``/api/compute/ocr`` returns and
``ocr_service`` builds.
"""
import datetime as dt

from pydantic import BaseModel, Field


class OcrExtractField(BaseModel):
    value: str | float | None
    confidence: float = Field(ge=0, le=1)


class ParsedInvoiceOut(BaseModel):
    """Rich structured fields from the OCR post-processing layer (Module 1)."""

    invoice_type: str  # "e_fatura" | "e_arsiv" | "paper"
    vkn: str | None = None
    tckn: str | None = None
    mersis: str | None = None
    tax_office: str | None = None
    currency: str = "TRY"
    payment_method: str | None = None
    due_date: dt.date | None = None
    kdv_rate: int | None = None
    kdv_amount: float | None = None
    net_amount: float | None = None
    total_amount: float | None = None
    stopaj_amount: float | None = None
    is_kdv_inclusive: bool | None = None
    tevkifat: bool = False
    istisna: bool = False
    ihrac_kayitli: bool = False
    detected_phrases: list[str] = Field(default_factory=list)


class OcrExtractResult(BaseModel):
    """Structured OCR extraction returned by POST /invoices/scan."""

    vendor_name: OcrExtractField
    invoice_number: OcrExtractField
    date: OcrExtractField
    total_amount: OcrExtractField
    vat_amount: OcrExtractField
    raw_text: str
    needs_review: bool
    # Module 1 rich extraction. Optional so existing clients keep working.
    invoice_type: str = "paper"
    parsed: ParsedInvoiceOut | None = None
