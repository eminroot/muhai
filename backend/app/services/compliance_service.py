"""AI Compliance Engine (Module 8).

Pure, side-effect-free rule checks over a business's invoices and the tax
calendar. The route layer feeds in plain records and persists/dedupes the
results. Checks that need data sources not built yet (bank reconciliation →
Module 6, SGK/tax payment history → Module 10) are intentionally left as
follow-ups so the engine can grow without changing its contract.

Checks implemented now:
- duplicate invoices (same number, or same amount+date+vendor)
- suspicious invoices (KDV doesn't match a valid rate, totals don't add up,
  abnormal/negative values)
- upcoming tax deadlines (due within their advance-warning window)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.tax_calendar import upcoming_deadlines

# Valid KDV fractions (incl. historical 8/18 for older documents).
VALID_KDV_FRACTIONS = (0.01, 0.08, 0.10, 0.18, 0.20)
KDV_TOLERANCE = 0.01  # absolute tolerance on the implied rate

Severity = str  # "high" | "medium" | "low"
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class InvoiceRecord:
    """Minimal invoice view the checks need (decoupled from the ORM)."""

    id: str
    invoice_number: str | None
    vendor_name: str | None
    amount: float  # gross total
    vat_amount: float
    date: date | None


@dataclass
class DetectedAlert:
    type: str  # "duplicate_invoice" | "suspicious_invoice" | "tax_deadline"
    severity: Severity
    description: str
    ref_id: str | None = None

    @property
    def key(self) -> tuple[str, str, str | None]:
        """Natural identity used to dedupe against stored alerts."""
        return (self.type, self.description, self.ref_id)


def check_duplicate_invoices(invoices: list[InvoiceRecord]) -> list[DetectedAlert]:
    alerts: list[DetectedAlert] = []

    # By invoice number.
    by_number: dict[str, list[InvoiceRecord]] = {}
    for inv in invoices:
        if inv.invoice_number:
            by_number.setdefault(inv.invoice_number.strip().lower(), []).append(inv)
    for number, group in by_number.items():
        if len(group) > 1:
            alerts.append(
                DetectedAlert(
                    type="duplicate_invoice",
                    severity="high",
                    description=(
                        f"'{group[0].invoice_number}' numaralı fatura "
                        f"{len(group)} kez kayıtlı."
                    ),
                    ref_id=group[0].id,
                )
            )

    # By (amount, date, vendor) for invoices without a shared number match.
    flagged_ids = {a.ref_id for a in alerts}
    by_triple: dict[tuple[float, str, str], list[InvoiceRecord]] = {}
    for inv in invoices:
        if inv.date is None or not inv.vendor_name:
            continue
        triple = (round(inv.amount, 2), inv.date.isoformat(), inv.vendor_name.strip().lower())
        by_triple.setdefault(triple, []).append(inv)
    for (amount, iso, vendor), group in by_triple.items():
        if len(group) > 1 and not any(g.id in flagged_ids for g in group):
            alerts.append(
                DetectedAlert(
                    type="duplicate_invoice",
                    severity="medium",
                    description=(
                        f"{group[0].vendor_name} adına {amount:.2f} tutarlı aynı tarihli "
                        f"{len(group)} fatura var."
                    ),
                    ref_id=group[0].id,
                )
            )
    return alerts


def _kdv_rate_is_valid(net: float, vat: float) -> bool:
    if vat == 0:
        return True  # exempt / zero-rated is acceptable
    if net <= 0:
        return False
    implied = vat / net
    return any(abs(implied - r) <= KDV_TOLERANCE for r in VALID_KDV_FRACTIONS)


def check_suspicious_invoices(invoices: list[InvoiceRecord]) -> list[DetectedAlert]:
    alerts: list[DetectedAlert] = []
    for inv in invoices:
        if inv.amount <= 0:
            alerts.append(
                DetectedAlert(
                    "suspicious_invoice",
                    "medium",
                    f"Geçersiz fatura tutarı ({inv.amount:.2f}).",
                    inv.id,
                )
            )
            continue
        if inv.vat_amount < 0 or inv.vat_amount > inv.amount:
            alerts.append(
                DetectedAlert(
                    "suspicious_invoice",
                    "high",
                    "KDV tutarı toplam tutarla tutarsız.",
                    inv.id,
                )
            )
            continue
        net = round(inv.amount - inv.vat_amount, 2)
        if not _kdv_rate_is_valid(net, inv.vat_amount):
            alerts.append(
                DetectedAlert(
                    "suspicious_invoice",
                    "medium",
                    "KDV tutarı geçerli bir orana (%1/%10/%20) uymuyor.",
                    inv.id,
                )
            )
    return alerts


def check_tax_deadlines(today: date | None = None) -> list[DetectedAlert]:
    today = today or date.today()
    alerts: list[DetectedAlert] = []
    for d in upcoming_deadlines(today, count=12):
        if not d.is_due_soon:
            continue
        severity = "high" if d.days_remaining <= 3 else "medium"
        alerts.append(
            DetectedAlert(
                type="tax_deadline",
                severity=severity,
                description=f"{d.name} için son {d.days_remaining} gün ({d.due_date.isoformat()}).",
                ref_id=None,
            )
        )
    return alerts


def run_all_checks(
    invoices: list[InvoiceRecord], today: date | None = None
) -> list[DetectedAlert]:
    alerts = (
        check_duplicate_invoices(invoices)
        + check_suspicious_invoices(invoices)
        + check_tax_deadlines(today)
    )
    alerts.sort(key=lambda a: _SEVERITY_RANK.get(a.severity, 3))
    return alerts
