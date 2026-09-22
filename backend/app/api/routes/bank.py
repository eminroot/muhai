"""Bank statements — the one place Muhai talks to something outside itself.

    GET  /api/bank/status          is a bank connected, and if not, why not
    GET  /api/bank/accounts        accounts the credentials can see
    POST /api/bank/transactions    fetch a statement for a date range
    POST /api/bank/import          the same, from an uploaded CSV
    POST /api/bank/reconcile       match movements against posted invoices
    POST /api/bank/sync            fetch + reconcile in one round trip

Two properties are deliberate and worth keeping.

**No table.** Like ``/api/compute``, this router reads and writes nothing. The
browser posts the invoices it already holds and gets matches back, and a
movement becomes a ledger entry only when the user asks — through
``/api/workspace``, the one write path. So there is no bank mirror to keep in
sync with the statement, and nothing to reconcile twice.

**The bank is optional.** Every endpoint except ``/accounts`` works with no
credentials at all, because the CSV path lands in the same normaliser as the
API path. A company whose bank has no API keeps the whole feature; it just
exports a file first. ``/status`` says which of the two the UI should offer.

Credentials live in the environment and belong to the deployment — see
``services/bank_providers.py``. Nothing about a bank connection is stored per
company, and no credential ever reaches the browser.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.schemas.bank import (
    BankAccountOut,
    BankStatusOut,
    BankTxnModel,
    BankTxnOut,
    FetchRequest,
    MatchOut,
    ReconcileRequest,
    StatementOut,
    StatementSummary,
    SyncRequest,
    TransactionsOut,
)
from app.services import bank_service as bs
from app.services.bank_client import BankApiError, BankNotConfigured, build_client

router = APIRouter(prefix="/bank", tags=["bank"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_WINDOW_DAYS = 30


def _window(since: dt.date | None, until: dt.date | None) -> tuple[dt.date, dt.date]:
    """Default to the last 30 days, and never let the range run backwards."""
    end = until or dt.date.today()
    start = since or (end - dt.timedelta(days=DEFAULT_WINDOW_DAYS))
    return (end, start) if start > end else (start, end)


def _row_out(row: bs.BankTxn) -> BankTxnOut:
    return BankTxnOut(
        **{
            **row.as_document(),
            "ledger": bs.to_transaction_document(row),
        }
    )


def _as_txn(model: BankTxnModel) -> bs.BankTxn:
    """A posted row back into the engine's own type.

    ``/reconcile`` takes rows the client already has — from a CSV import, or
    from a fetch the user is still looking at — so a round trip through the
    API must not lose the sign or the date.
    """
    return bs.BankTxn(
        date=model.date,
        description=model.description,
        amount=model.amount,
        currency=model.currency,
        balance=model.balance,
        reference=model.reference,
        counterparty=model.counterparty,
        category=model.category,
        source=model.source,
    )


def _invoice_refs(payload: ReconcileRequest) -> list[bs.InvoiceRef]:
    return [
        bs.InvoiceRef(
            id=inv.id,
            amount=float(inv.amount),
            date=inv.date,
            vendor=inv.vendor,
            number=inv.number,
            direction=inv.direction,
            status=inv.status,
        )
        for inv in payload.invoices
    ]


def _handle(exc: BankApiError) -> HTTPException:
    """Bank failures, mapped to statuses the frontend already knows.

    503 means "not configured" — the UI answers that with the CSV path rather
    than an error. 504 is a bank that did not answer, 502 one that answered
    with a problem. None of them are the caller's fault, so none are 4xx.
    """
    if isinstance(exc, BankNotConfigured):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.status == 0:
        code = status.HTTP_504_GATEWAY_TIMEOUT
    else:
        code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=code, detail=exc.message)


# ── Connection ────────────────────────────────────────────────────────


@router.get("/status", response_model=BankStatusOut)
async def bank_status(caller: CurrentUser) -> BankStatusOut:
    """Whether a bank is connected — and when it is not, the missing setting."""
    return BankStatusOut(**build_client().status())


@router.get("/accounts", response_model=list[BankAccountOut])
async def bank_accounts(caller: CurrentUser) -> list[BankAccountOut]:
    try:
        return [BankAccountOut(**account) for account in build_client().list_accounts()]
    except BankApiError as exc:
        raise _handle(exc) from exc


# ── Fetch ─────────────────────────────────────────────────────────────


@router.post("/transactions", response_model=TransactionsOut)
async def bank_transactions(
    payload: FetchRequest, caller: CurrentUser
) -> TransactionsOut:
    """Pull a statement from the bank and categorise it. Nothing is stored."""
    since, until = _window(payload.since, payload.until)
    client = build_client()
    try:
        rows = client.list_transactions(
            payload.account_id, since, until, limit=payload.limit
        )
    except BankApiError as exc:
        raise _handle(exc) from exc

    bs.categorise_all(rows)
    return TransactionsOut(
        rows=[_row_out(r) for r in rows],
        summary=StatementSummary(**bs.summarise(rows, [])),
        source="mock" if client.provider.auth == "none" else "api",
        account_id=payload.account_id or None,
        since=since,
        until=until,
    )


@router.post("/import", response_model=TransactionsOut)
async def bank_import(
    caller: CurrentUser, file: UploadFile = File(...)
) -> TransactionsOut:
    """The path that needs no bank API: a statement exported from banking.

    Encoding matters more than it looks. Turkish banks export
    windows-1254/latin-5 as often as UTF-8, and a vendor name mangled here
    silently costs every vendor match downstream.
    """
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Boş dosya."
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Dosya 5 MB sınırını aşıyor.",
        )

    text = ""
    for encoding in ("utf-8-sig", "cp1254", "iso-8859-9", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosya okunamadı (kodlama tanınmadı).",
        )

    rows = bs.parse_bank_csv(text)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ekstrede işlem satırı bulunamadı. Tarih ve tutar sütunları gerekli.",
        )

    bs.categorise_all(rows)
    dates = [r.date for r in rows if r.date]
    return TransactionsOut(
        rows=[_row_out(r) for r in rows],
        summary=StatementSummary(**bs.summarise(rows, [])),
        source="csv",
        since=min(dates) if dates else None,
        until=max(dates) if dates else None,
    )


# ── Match ─────────────────────────────────────────────────────────────


@router.post("/reconcile", response_model=StatementOut)
async def bank_reconcile(
    payload: ReconcileRequest, caller: CurrentUser
) -> StatementOut:
    """Match posted movements against posted invoices. A pure function."""
    rows = [_as_txn(row) for row in payload.rows]
    bs.categorise_all(rows, payload.learned)
    matches = bs.reconcile(
        rows,
        _invoice_refs(payload),
        date_window_days=payload.date_window_days,
        amount_tol_pct=payload.amount_tolerance_pct,
    )
    return StatementOut(
        rows=[_row_out(r) for r in rows],
        matches=[MatchOut(**vars(m)) for m in matches],
        summary=StatementSummary(**bs.summarise(rows, matches)),
        source="csv" if rows and rows[0].source == "csv" else "api",
    )


@router.post("/sync", response_model=StatementOut)
async def bank_sync(payload: SyncRequest, caller: CurrentUser) -> StatementOut:
    """Fetch the statement and reconcile it in one call — the screen's button."""
    since, until = _window(payload.since, payload.until)
    client = build_client()
    try:
        rows = client.list_transactions(
            payload.account_id, since, until, limit=payload.limit
        )
    except BankApiError as exc:
        raise _handle(exc) from exc

    bs.categorise_all(rows, payload.learned)
    matches = bs.reconcile(
        rows,
        _invoice_refs(payload),
        date_window_days=payload.date_window_days,
        amount_tol_pct=payload.amount_tolerance_pct,
    )
    return StatementOut(
        rows=[_row_out(r) for r in rows],
        matches=[MatchOut(**vars(m)) for m in matches],
        summary=StatementSummary(**bs.summarise(rows, matches)),
        source="mock" if client.provider.auth == "none" else "api",
        account_id=payload.account_id or None,
        since=since,
        until=until,
    )
