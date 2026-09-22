"""Invoice OCR service.

Uses Tesseract 5 (via pytesseract) with the Turkish language pack to read an
uploaded invoice image, then applies regex heuristics to pull out structured
fields with per-field confidence scores.

The public surface is the abstract ``OcrEngine`` interface so a cloud OCR /
LLM-vision provider can be dropped in later without changing the route.
"""
from __future__ import annotations

import io
import re
from abc import ABC, abstractmethod
from datetime import datetime

from dataclasses import asdict

from app.core.config import settings
from app.schemas.ocr import OcrExtractField, OcrExtractResult, ParsedInvoiceOut
from app.services.ocr_parser import parse_invoice_text

CONFIDENCE_THRESHOLD = 0.7

# ── Regex heuristics ───────────────────────────────────────────────────
_INVOICE_NO_RE = re.compile(
    r"(?:fatura\s*(?:no|numaras[ıi])|invoice\s*(?:no|number))\s*[:#]?\s*([A-Z0-9\-/]+)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))")
_VAT_LINE_RE = re.compile(r"(?:kdv|vat)", re.IGNORECASE)
_TOTAL_LINE_RE = re.compile(r"(?:genel\s*toplam|toplam|total|tutar)", re.IGNORECASE)

# A Turkish trading name almost always carries its legal form: "... A.Ş.",
# "... Ltd. Şti.", "... San. ve Tic.". That is a far stronger signal than
# position on the page, which is what the first version relied on — and
# position is exactly what a photograph disturbs, because the top of the frame
# catches glare, the paper edge and the logo before it reaches the name.
_LEGAL_FORM_RE = re.compile(
    r"(?:^|[\s.,])(?:a\.?\s?[şs]\.?|ltd\.?|[şs]ti\.?|san\.?|tic\.?|"
    r"anonim|limited|[şs]irketi|kollektif|komandit)(?:$|[\s.,])",
    re.IGNORECASE,
)

# Document-type banners and party labels sit exactly where the vendor does and
# are mostly alphabetic, so the old "first alphabetic line" rule picked them.
_NOT_VENDOR_RE = re.compile(
    r"^(?:e[-\s]?)?(?:fatura|ar[şs]iv|irsaliye|fi[şs]|makbuz|say[ıi]n|"
    r"al[ıi]c[ıi]|sat[ıi]c[ıi]|m[üu][şs]teri|firma|unvan|adres|tarih|"
    r"vergi|serbest\s+meslek|m[üu]stahsil)",
    re.IGNORECASE,
)

# The vendor sits in the letterhead. Beyond this many lines we are into the
# line items, where a supplier name is not what we would be reading.
_VENDOR_SEARCH_LINES = 10


def _parse_amount(raw: str) -> float | None:
    """Parse a Turkish-formatted number string like '1.234,56' -> 1234.56."""
    s = raw.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


class OcrEngine(ABC):
    """Swappable OCR backend interface."""

    @abstractmethod
    def image_to_text(self, image_bytes: bytes) -> str:  # pragma: no cover
        ...

    def image_to_lines(self, image_bytes: bytes) -> list[tuple[str, float]]:
        """Optional: per-line text with measured confidence in [0, 1].

        An engine that cannot report confidence returns nothing and the field
        rules fall back to their own certainty, so a cloud provider can still
        be dropped in here without implementing this.
        """
        return []


# Tesseract's default page segmentation (PSM 3) runs full layout analysis and
# will happily decide an invoice is two columns — labels on the left, amounts
# on the right. It then emits them as separate lines, and `_extract_fields`
# below matches amounts to labels *per line*, so "Ara Toplam:" arrives with no
# number attached. PSM 6 ("one uniform block") keeps each row intact, which is
# what the field extraction needs. Measured on the sample invoice across four
# simulated capture conditions: 28/32 fields against 26/32 for PSM 3.
_TESSERACT_CONFIG = "--psm 6"

# Tesseract's LSTM wants roughly 30 px of x-height. Below that its accuracy
# collapses regardless of which model is loaded, and a photo taken from across
# a desk lands well under it — upscaling is what rescues those, not a bigger
# traineddata file.
_MIN_WIDTH_PX = 1600


class TesseractEngine(OcrEngine):
    @staticmethod
    def _prepare(image):
        """Normalise a photographed document into something Tesseract reads.

        Grayscale, upscale if small, stretch contrast, and sharpen. On a clean
        scan this changes nothing; on an under-exposed or distant photo it is
        the difference between four fields and one.
        """
        from PIL import Image, ImageFilter, ImageOps

        image = image.convert("L")
        width, height = image.size
        if width < _MIN_WIDTH_PX:
            scale = _MIN_WIDTH_PX / width
            image = image.resize(
                (int(width * scale), int(height * scale)), Image.LANCZOS
            )
        # cutoff=1 discards the top and bottom percentile before stretching, so
        # a single dark speck cannot define the black point.
        image = ImageOps.autocontrast(image, cutoff=1)
        return image.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3)
        )

    def image_to_text(self, image_bytes: bytes) -> str:
        return "\n".join(line for line, _ in self.image_to_lines(image_bytes))

    def image_to_lines(self, image_bytes: bytes) -> list[tuple[str, float]]:
        """Read the page once, returning each line with its mean word
        confidence in [0, 1].

        image_to_data rather than image_to_string: the text is the same, but it
        also carries the per-word confidence Tesseract already computed and
        that the old code threw away in favour of hardcoded constants. Words
        scored -1 are layout, not text, and are ignored.
        """
        # Imported lazily so the module imports even when system Tesseract or
        # Pillow is missing (e.g. during unit tests of the parsing helpers).
        import pytesseract
        from PIL import Image

        image = self._prepare(Image.open(io.BytesIO(image_bytes)))
        data = pytesseract.image_to_data(
            image,
            lang=settings.OCR_LANG,
            config=_TESSERACT_CONFIG,
            output_type=pytesseract.Output.DICT,
        )

        grouped: dict[tuple, list[tuple[str, float]]] = {}
        for i, word in enumerate(data["text"]):
            word = (word or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            grouped.setdefault(key, []).append((word, conf))

        out: list[tuple[str, float]] = []
        for key in sorted(grouped):
            words = grouped[key]
            text = " ".join(w for w, _ in words)
            scored = [c for _, c in words if c >= 0]
            out.append((text, (sum(scored) / len(scored) / 100.0) if scored else 0.0))
        return out



def _fold(text: str) -> str:
    """Turkish-aware lowering: İ/I/ı fold together so a regex written in
    lower case matches a shouted letterhead."""
    return (
        text.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    )


def _extract_vendor(lines: list[str]) -> tuple[str | None, float]:
    """Find the supplier's trading name in the letterhead.

    Returns the name and how much the *rule* trusts itself, separately from how
    well the characters were read — those are two different doubts and blending
    them is what made the old number meaningless.
    """
    head = lines[:_VENDOR_SEARCH_LINES]
    candidates = [
        ln for ln in head
        if len(ln) > 3
        and not _NOT_VENDOR_RE.match(_fold(ln))
        and sum(c.isalpha() or c.isspace() for c in ln) > len(ln) * 0.6
    ]

    # A legal form is near-proof: nothing else on an invoice reads "Ltd. Şti."
    for ln in candidates:
        if _LEGAL_FORM_RE.search(_fold(ln)):
            return ln, 0.9

    # Otherwise fall back to the topmost plausible line, and say plainly that
    # this is a guess rather than dressing it up.
    if candidates:
        return candidates[0], 0.5
    return None, 0.0


def _score(certainty: float, line_conf: dict[str, float], value) -> float:
    """Combine how sure the rule is with how cleanly Tesseract read the line.

    Both matter and neither alone is the answer: a confident regex over mush is
    not a confident field, and a crisp scan of the wrong line is not either.
    With no measurement available the rule's own certainty stands, which is the
    old behaviour.
    """
    if value is None:
        return 0.0
    if not line_conf:
        return round(certainty, 2)
    read = _line_confidence_for(str(value), line_conf)
    return round(certainty * read, 2) if read is not None else round(certainty, 2)


def _score_line(
    certainty: float, line_conf: dict[str, float], line: str | None, value
) -> float:
    """Like _score, but the caller already knows which line carried the value.

    Used for amounts, whose parsed form does not appear in the text.
    """
    if value is None:
        return 0.0
    if not line_conf or line is None:
        return round(certainty, 2)
    read = line_conf.get(line)
    if read is None:
        read = _line_confidence_for(line, line_conf)
    return round(certainty * read, 2) if read is not None else round(certainty, 2)


def _line_confidence_for(needle: str, line_conf: dict[str, float]) -> float | None:
    """The measured confidence of whichever OCR line carried this value."""
    folded = _fold(needle).strip()
    if not folded:
        return None
    best = None
    for line, conf in line_conf.items():
        if folded in _fold(line):
            # Prefer the tightest line containing it — a long line averages the
            # value's own characters away.
            if best is None or len(line) < best[0]:
                best = (len(line), conf)
    return best[1] if best else None


def _extract_fields(
    text: str, line_conf: dict[str, float] | None = None
) -> OcrExtractResult:
    line_conf = line_conf or {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    vendor, vendor_certainty = _extract_vendor(lines)
    vendor_field = OcrExtractField(
        value=vendor,
        confidence=_score(vendor_certainty, line_conf, vendor),
    )

    inv_match = _INVOICE_NO_RE.search(text)
    inv_value = inv_match.group(1) if inv_match else None
    invoice_field = OcrExtractField(
        value=inv_value, confidence=_score(0.85, line_conf, inv_value)
    )

    date_match = _DATE_RE.search(text)
    date_value: str | None = None
    if date_match:
        d, m, y = date_match.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            date_value = datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            date_value = None
    date_field = OcrExtractField(
        value=date_value,
        confidence=_score(0.8, line_conf, date_match.group(0) if date_match else None),
    )

    # Total amount: pick the largest amount appearing on a "total" line,
    # otherwise the largest amount anywhere. Each candidate carries the line it
    # came from: the parsed float (14820.0) never appears in the text
    # ("14.820,00"), so looking the value up by string would silently find no
    # line and fall back to the rule's own certainty — which is exactly the
    # hardcoded number this change exists to remove.
    total_candidates: list[tuple[float, str]] = []
    vat_candidates: list[tuple[float, str]] = []
    all_amounts: list[tuple[float, str]] = []
    for ln in lines:
        amounts = [a for a in (_parse_amount(m) for m in _AMOUNT_RE.findall(ln)) if a]
        if not amounts:
            continue
        all_amounts.extend((a, ln) for a in amounts)
        if _VAT_LINE_RE.search(ln):
            vat_candidates.extend((a, ln) for a in amounts)
        if _TOTAL_LINE_RE.search(ln):
            total_candidates.extend((a, ln) for a in amounts)

    pool = total_candidates or all_amounts
    total, total_line = max(pool, key=lambda pair: pair[0]) if pool else (None, None)
    total_field = OcrExtractField(
        value=total,
        confidence=_score_line(0.8 if total_candidates else 0.5, line_conf, total_line, total),
    )

    vat, vat_line = (
        max(vat_candidates, key=lambda pair: pair[0]) if vat_candidates else (None, None)
    )
    vat_field = OcrExtractField(
        value=vat, confidence=_score_line(0.75, line_conf, vat_line, vat)
    )

    fields = [vendor_field, invoice_field, date_field, total_field, vat_field]
    avg_conf = sum(f.confidence for f in fields) / len(fields)
    needs_review = avg_conf < CONFIDENCE_THRESHOLD

    # Rich post-processing (Module 1): identity, tax details, invoice type.
    parsed = parse_invoice_text(text)
    parsed_out = ParsedInvoiceOut(**asdict(parsed))

    # Prefer the parser's total/VAT when the line-based heuristics found nothing.
    if total_field.value is None and parsed.total_amount is not None:
        total_field = OcrExtractField(value=parsed.total_amount, confidence=0.7)
    if vat_field.value is None and parsed.kdv_amount is not None:
        vat_field = OcrExtractField(value=parsed.kdv_amount, confidence=0.7)

    return OcrExtractResult(
        vendor_name=vendor_field,
        invoice_number=invoice_field,
        date=date_field,
        total_amount=total_field,
        vat_amount=vat_field,
        raw_text=text,
        needs_review=needs_review,
        invoice_type=parsed.invoice_type,
        parsed=parsed_out,
    )


# Default engine instance (Tesseract). Swap here for a cloud provider.
_engine: OcrEngine = TesseractEngine()


def scan_invoice(image_bytes: bytes) -> OcrExtractResult:
    """OCR an invoice image and return structured, confidence-scored fields."""
    lines = _engine.image_to_lines(image_bytes)
    if lines:
        text = "\n".join(line for line, _ in lines)
        return _extract_fields(text, {line: conf for line, conf in lines})
    return _extract_fields(_engine.image_to_text(image_bytes))
