"""The demo dataset — generated here, on the server.

This was `web/src/lib/seed.js`: the browser manufactured a twelve-month
trading history and POSTed it into whichever workspace had just been created.
The data was real (it went to Postgres like any other write), but the
*generator* shipped in the bundle and ran on every sign-up, so every account
came pre-filled with invented figures.

Now nothing generates business data in the browser. This module holds the only
demo dataset there is, and `scripts/seed_demo.py` writes it into one account
that exists for the purpose. A real sign-up gets an empty workspace.

Deterministic by design: a seeded PRNG (mulberry32, keyed by an FNV-1a hash of
the company id) means the demo company always gets the same figures, so a
screenshot stays true and a rehearsed demo does not move under you.

Documents, not rows. Everything below builds the same camelCase documents the
web client used to send, and `services/workspace.py` maps them to columns —
the one place that knows both vocabularies. So a seeded row is indistinguish-
able from one a user typed, and it reads back through `/api/workspace`
identically.
"""
from __future__ import annotations

import calendar
import datetime as dt
import math
from typing import Any, Callable

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.services import workspace as ws

# ── Deterministic PRNG (mulberry32) ───────────────────────────────────
# A direct port of the JavaScript, down to the 32-bit wrap-around, so the
# dataset this produces is the one the old generator produced.

_MASK = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """JavaScript's ``Math.imul`` — a 32-bit multiply that wraps."""
    return (a * b) & _MASK


def _rng(seed: int) -> Callable[[], float]:
    state = seed & _MASK

    def next_float() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _MASK
        t = _imul(state ^ (state >> 15), 1 | state)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & _MASK) ^ t
        return ((t ^ (t >> 14)) & _MASK) / 4294967296

    return next_float


def _seed_from_string(text: str) -> int:
    """FNV-1a, 32-bit. Turns a company id into a PRNG seed."""
    h = 2166136261
    for char in text:
        h = (h ^ ord(char)) & _MASK
        h = _imul(h, 16777619)
    return h


# ── Dates ─────────────────────────────────────────────────────────────
# JavaScript's Date rolls an out-of-range day into the next month, so
# `new Date(y, 1, 30)` quietly became 2 March. A due date is clamped to the
# end of its month here instead, which is what a due date means.


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """The (year, month) ``delta`` months from this one. ``month`` is 1-12."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _date(year: int, month: int, day: int) -> dt.date:
    """A calendar date, with the day clamped into the month."""
    return dt.date(year, month, max(1, min(day, _last_day(year, month))))


def _round2(value: float) -> float:
    """``Math.round(n * 100) / 100`` — half away from zero, as JS rounds."""
    return math.floor(value * 100 + 0.5) / 100


# ── Business shape ────────────────────────────────────────────────────

SALES_CUSTOMERS = (
    "Anadolu Tedarik A.Ş.",
    "Marmara Lojistik Ltd.",
    "Ege Ambalaj San. Tic.",
    "Boğaziçi Yazılım A.Ş.",
    "Akdeniz Gıda Ltd.",
    "Kuzey Enerji A.Ş.",
)

# Recurring monthly cost base — category, vendor, share of the month's spend.
RECURRING_COSTS = (
    {"category": "payroll", "vendor": "Personel bordrosu", "share": 0.42,
     "description": "Aylık maaş ödemesi"},
    {"category": "rent", "vendor": "Kadıköy Emlak", "share": 0.14,
     "description": "İşyeri kira ödemesi"},
    {"category": "raw_materials", "vendor": "Ege Ambalaj San. Tic.", "share": 0.16,
     "description": "Hammadde alımı"},
    {"category": "utilities", "vendor": "Enerjisa", "share": 0.06,
     "description": "Elektrik ve doğalgaz faturası"},
    {"category": "software", "vendor": "Google Workspace", "share": 0.04,
     "description": "Yazılım abonelik lisansı"},
    {"category": "marketing", "vendor": "Meta Ads", "share": 0.07,
     "description": "Sosyal medya reklam harcaması"},
    {"category": "shipping", "vendor": "Aras Kargo", "share": 0.05,
     "description": "Kargo ve nakliye gideri"},
    {"category": "fuel", "vendor": "Opet", "share": 0.03,
     "description": "Araç akaryakıt alımı"},
    {"category": "insurance", "vendor": "Anadolu Sigorta", "share": 0.02,
     "description": "İşyeri sigorta poliçesi"},
    {"category": "bank_fees", "vendor": "Ziraat Bankası", "share": 0.01,
     "description": "Banka havale komisyonu"},
)

PRODUCTS = (
    {"name": "A4 Fotokopi Kağıdı (koli)", "sku": "KGT-A4-500", "stock": 128,
     "minStock": 40, "unitPrice": 185, "unit": "koli", "monthlyUsage": 38},
    {"name": "Toner Kartuş HP-26A", "sku": "TNR-HP26A", "stock": 6,
     "minStock": 12, "unitPrice": 420, "unit": "adet", "monthlyUsage": 9},
    {"name": "Dosya Klasör (paket)", "sku": "OFS-KLS-10", "stock": 74,
     "minStock": 25, "unitPrice": 53, "unit": "paket", "monthlyUsage": 18},
    {"name": "Streç Film 50cm", "sku": "AMB-STR-50", "stock": 210,
     "minStock": 60, "unitPrice": 96, "unit": "rulo", "monthlyUsage": 52},
    {"name": "Koli Bandı Şeffaf", "sku": "AMB-BND-45", "stock": 18,
     "minStock": 30, "unitPrice": 24, "unit": "adet", "monthlyUsage": 40},
    {"name": "Palet Ahşap 120x80", "sku": "LOJ-PLT-1208", "stock": 45,
     "minStock": 20, "unitPrice": 310, "unit": "adet", "monthlyUsage": 14},
)

EMPLOYEES = (
    {"name": "Emin Baytar", "role": "Genel Müdür", "grossSalary": 92000,
     "startDate": "2021-02-15", "sgkNo": "1023456781"},
    {"name": "Selin Karaca", "role": "Mali İşler Uzmanı", "grossSalary": 58000,
     "startDate": "2022-09-01", "sgkNo": "1023456782"},
    {"name": "Mert Doğan", "role": "Satış Sorumlusu", "grossSalary": 46000,
     "startDate": "2023-06-12", "sgkNo": "1023456783"},
    {"name": "Ayşe Yılmaz", "role": "Depo Sorumlusu", "grossSalary": 38000,
     "startDate": "2024-03-04", "sgkNo": "1023456784"},
)

VAT_RATE = 0.2

# An OCR field below this lands in the review queue — the same threshold the
# web client applies.
REVIEW_THRESHOLD = 0.7

MONTHS_OF_HISTORY = 12
OPENING_CASH = 180000


def split_vat(gross: float, rate: float = VAT_RATE) -> tuple[float, float]:
    """Split a KDV-inclusive amount into (net, vat)."""
    net = _round2(gross / (1 + rate))
    return net, _round2(gross - net)


# ── Generators ────────────────────────────────────────────────────────


def build_transactions(rand: Callable[[], float], today: dt.date) -> list[dict[str, Any]]:
    """Twelve months of trading.

    Revenue grows ~3%/month with noise; costs follow revenue through the
    recurring cost base, so the margin stays plausible month to month.
    """
    rows: list[dict[str, Any]] = []
    monthly_revenue = 148000.0

    for back in range(MONTHS_OF_HISTORY - 1, -1, -1):
        year, month = _shift_month(today.year, today.month, -back)
        last_day = _last_day(year, month)
        # The current month is partial — only bill through today.
        through_day = today.day if back == 0 else last_day

        revenue = _round2(monthly_revenue * (0.93 + rand() * 0.14))
        expense_total = _round2(revenue * (0.6 + rand() * 0.08))

        # Revenue arrives as 6-9 customer payments spread across the month.
        sale_count = 6 + int(rand() * 4)
        remaining = revenue
        for i in range(sale_count):
            is_last = i == sale_count - 1
            share = remaining if is_last else revenue * (0.6 / sale_count + rand() * 0.12)
            amount = _round2(max(min(share, remaining), 0))
            remaining = _round2(remaining - amount)
            day = max(1, min(through_day, 1 + int(rand() * last_day)))
            if amount <= 0:
                continue
            rows.append({
                "date": _date(year, month, day).isoformat(),
                "amount": amount,
                "type": "income",
                "category": "sales",
                "vendor": SALES_CUSTOMERS[int(rand() * len(SALES_CUSTOMERS))],
                "description": "Satış tahsilatı",
                "demo": True,
            })

        # Costs follow the recurring base, each on a stable day of the month.
        for idx, cost in enumerate(RECURRING_COSTS):
            amount = _round2(expense_total * cost["share"] * (0.9 + rand() * 0.2))
            day = min(through_day, 2 + (idx * 3) % 26)
            if amount <= 0 or day < 1:
                continue
            rows.append({
                "date": _date(year, month, day).isoformat(),
                "amount": amount,
                "type": "expense",
                "category": cost["category"],
                "vendor": cost["vendor"],
                "description": cost["description"],
                "demo": True,
            })

        monthly_revenue = _round2(monthly_revenue * 1.03)

    return rows


def build_invoices(today: dt.date) -> list[dict[str, Any]]:
    """The five invoices.

    Deliberately mixed, so every downstream path is exercised by real data:
    paid and unpaid, sales and purchase, one already past its due date, and
    one OCR-scanned below the confidence threshold so the review queue has
    something in it.
    """
    year, month = today.year, today.month
    prev_year, prev_month = _shift_month(year, month, -1)

    def number(n: int) -> str:
        return f"MUH-{year}-{n:04d}"

    specs = [
        {"number": number(1), "vendor": "Anadolu Tedarik A.Ş.", "taxId": "4830027561",
         "direction": "sales", "gross": 148200,
         "issue": _date(year, month, min(4, today.day)), "due_in_days": 30,
         "status": "paid", "paid_offset_days": 21, "category": "sales",
         "source": "manual", "ocr_confidence": None},
        {"number": number(2), "vendor": "Marmara Lojistik Ltd.", "taxId": "2910044873",
         "direction": "sales", "gross": 64500,
         "issue": _date(year, month, min(9, today.day)), "due_in_days": 14,
         "status": "pending", "paid_offset_days": None, "category": "sales",
         "source": "manual", "ocr_confidence": None},
        {"number": number(3), "vendor": "Ege Ambalaj San. Tic.", "taxId": "3510092204",
         "direction": "purchase", "gross": 92300,
         "issue": _date(prev_year, prev_month, 20), "due_in_days": 30,
         "status": "paid", "paid_offset_days": 26, "category": "raw_materials",
         "source": "ocr", "ocr_confidence": 0.94},
        {"number": number(4), "vendor": "Teknoloji Bilişim A.Ş.", "taxId": "6120038119",
         "direction": "purchase", "gross": 22100,
         "issue": _date(prev_year, prev_month, 8), "due_in_days": 21,
         "status": "overdue", "paid_offset_days": None, "category": "software",
         # Below the threshold — this one lands in the review queue.
         "source": "ocr", "ocr_confidence": 0.61},
        {"number": number(5), "vendor": "Yıldız Matbaa Ltd.", "taxId": "8840051177",
         "direction": "purchase", "gross": 37800,
         "issue": _date(year, month, min(2, today.day)), "due_in_days": 45,
         "status": "pending", "paid_offset_days": None, "category": "marketing",
         "source": "manual", "ocr_confidence": None},
    ]

    invoices: list[dict[str, Any]] = []
    for spec in specs:
        issue: dt.date = spec["issue"]
        net, vat = split_vat(float(spec["gross"]))
        confidence = spec["ocr_confidence"]
        paid_offset = spec["paid_offset_days"]

        # A settled invoice cannot have been settled tomorrow. The offsets are
        # measured from the issue date, and the two invoices raised this month
        # were issued only days ago, so the larger one used to be stamped paid
        # several days into the future. It posted a cash receipt that had not
        # happened: the dashboard's current month carried the outgoing payment
        # but not the incoming one, which is why the demo opened on a loss,
        # and the forecast was fitted over a point beyond the present.
        paid_date = (
            min(issue + dt.timedelta(days=int(paid_offset)), today)
            if paid_offset else None
        )

        invoices.append({
            "number": spec["number"],
            "vendor": spec["vendor"],
            "taxId": spec["taxId"],
            "direction": spec["direction"],
            "issueDate": issue.isoformat(),
            "dueDate": (issue + dt.timedelta(days=int(spec["due_in_days"]))).isoformat(),
            "paidDate": paid_date.isoformat() if paid_date else None,
            "amount": float(spec["gross"]),
            "netAmount": net,
            "vatAmount": vat,
            "vatRate": VAT_RATE,
            "status": spec["status"],
            "category": spec["category"],
            "source": spec["source"],
            "ocrConfidence": confidence,
            "needsReview": confidence is not None and confidence < REVIEW_THRESHOLD,
            "currency": "TRY",
            "demo": True,
        })
    return invoices


def invoice_ledger_entries(invoices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cash movements for the invoices that are already settled."""
    return [
        {
            "date": inv["paidDate"],
            "amount": inv["amount"],
            "type": "income" if inv["direction"] == "sales" else "expense",
            "category": inv["category"],
            "vendor": inv["vendor"],
            "description": f"{inv['number']} · {inv['vendor']}",
            "invoiceNumber": inv["number"],
            "demo": True,
        }
        for inv in invoices
        if inv["status"] == "paid" and inv["paidDate"]
    ]


def build_tax_obligations(
    today: dt.date,
    monthly_revenue: float,
    monthly_expense: float,
    payroll: float,
) -> list[dict[str, Any]]:
    """The next few statutory obligations, sized from the seeded trading."""
    year, month = today.year, today.month
    next_year, next_month = _shift_month(year, month, 1)
    kdv = max(_round2((monthly_revenue - monthly_expense) * (VAT_RATE / (1 + VAT_RATE))), 0)
    period = f"{year}-{month:02d}"
    quarter = (month - 1) // 3 + 1
    # The quarterly return falls in the month after the quarter closes.
    gecici_year, gecici_month = _shift_month(year, (quarter - 1) * 3 + 1, 4)

    return [
        {"type": "kdv", "name": "KDV Beyannamesi", "period": period,
         "dueDate": _date(next_year, next_month, 28).isoformat(),
         "amount": kdv, "status": "draft", "demo": True},
        {"type": "muhtasar", "name": "Muhtasar ve Prim Hizmet Beyannamesi",
         "period": period,
         "dueDate": _date(next_year, next_month, 26).isoformat(),
         "amount": _round2(payroll * 0.15), "status": "draft", "demo": True},
        {"type": "sgk", "name": "SGK Primi", "period": period,
         "dueDate": _date(next_year, next_month, 30).isoformat(),
         "amount": _round2(payroll * 0.345), "status": "draft", "demo": True},
        {"type": "gecici", "name": "Geçici Vergi (Kurumlar)",
         "period": f"{year}-Q{quarter}",
         "dueDate": _date(gecici_year, gecici_month, 17).isoformat(),
         "amount": _round2(max(monthly_revenue - monthly_expense, 0) * 3 * 0.25),
         "status": "draft", "demo": True},
    ]


# ── Writing it ────────────────────────────────────────────────────────


async def clear_company_data(db: AsyncSession, company: Company) -> None:
    """Empty every collection this company owns. Makes reseeding idempotent."""
    for spec in ws.COLLECTIONS.values():
        await db.execute(delete(spec.model).where(spec.model.company_id == company.id))


def build_dataset(company_id: str, today: dt.date | None = None,
                  seed_key: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """The whole demo dataset as workspace documents. Writes nothing."""
    today = today or dt.date.today()
    rand = _rng(_seed_from_string(seed_key or company_id))

    invoices = build_invoices(today)
    transactions = build_transactions(rand, today) + invoice_ledger_entries(invoices)

    this_month = f"{today.year}-{today.month:02d}"
    month_rows = [t for t in transactions if str(t["date"]).startswith(this_month)]
    monthly_revenue = _round2(sum(t["amount"] for t in month_rows if t["type"] == "income"))
    monthly_expense = _round2(sum(t["amount"] for t in month_rows if t["type"] == "expense"))
    payroll = sum(float(e["grossSalary"]) for e in EMPLOYEES)

    return {
        "transactions": transactions,
        "invoices": invoices,
        "products": [{**p, "demo": True} for p in PRODUCTS],
        "employees": [{**e, "demo": True} for e in EMPLOYEES],
        "taxObligations": build_tax_obligations(
            today, monthly_revenue, monthly_expense, payroll
        ),
    }


async def seed_company(
    db: AsyncSession,
    company: Company,
    today: dt.date | None = None,
    seed_key: str | None = None,
    replace: bool = True,
) -> dict[str, int]:
    """Write the demo dataset into ``company``.

    Returns the row count per collection. With ``replace`` the company's
    existing rows go first, so running this twice leaves one dataset rather
    than two.
    """
    dataset = build_dataset(company.id, today=today, seed_key=seed_key)

    if replace:
        await clear_company_data(db, company)

    for name, documents in dataset.items():
        spec = ws.COLLECTIONS[name]
        for document in documents:
            values = ws.to_columns(spec, document)
            db.add(spec.model(company_id=company.id, **values))

    # Opening cash, so the runway and the Muhai Score have a balance to work
    # from rather than starting at zero. Opening only: the clients add the
    # movement history to it, so folding the seeded net flow in here as well
    # would count a year of trading twice.
    company.cash_balance = _round2(OPENING_CASH)
    company.seeded = True
    company.seeded_at = dt.datetime.now(dt.timezone.utc).isoformat()
    db.add(company)

    await db.flush()
    return {name: len(rows) for name, rows in dataset.items()}
