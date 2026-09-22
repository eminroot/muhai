"""The company workspace API — what replaced direct Firestore access.

The browser used to hold an open connection to Firestore and read/write
documents itself. It now goes through here. The document shapes are unchanged,
so this is deliberately a thin, generic CRUD surface over five collections
rather than five bespoke routers:

    GET    /api/workspace                      company + every collection
    PATCH  /api/workspace/company              update the company profile
    GET    /api/workspace/{collection}
    POST   /api/workspace/{collection}         create one          -> {"id": …}
    POST   /api/workspace/{collection}/bulk    create many         -> {"ids": […]}
    PATCH  /api/workspace/{collection}/{id}
    DELETE /api/workspace/{collection}/{id}
    DELETE /api/workspace/{collection}         clear the collection

Two compound operations are endpoints of their own because they must be atomic
— an invoice and the cash movement that settles it have to appear together or
not at all, or the dashboard shows an invoice whose money never moved:

    POST /api/workspace/invoices/with-ledger
    POST /api/workspace/invoices/{id}/pay

Firestore batched those on the client. A single transaction here is a stronger
guarantee than that ever was.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Response, status
from sqlalchemy import delete, nulls_last, select

from app.api.deps import CurrentCompany, DbSession
from app.services import workspace as ws

router = APIRouter(prefix="/workspace", tags=["workspace"])

# A seeded demo dataset is a few hundred rows; anything far beyond that is a
# mistake or an attack, not a legitimate write.
MAX_BULK_ITEMS = 1000


def _spec(collection: str) -> ws.Collection:
    spec = ws.COLLECTIONS.get(collection)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bilinmeyen koleksiyon: {collection}",
        )
    return spec


def _order(spec: ws.Collection) -> tuple:
    """Newest first, matching the order the Firestore queries used.

    Undated rows sort last rather than first: Postgres puts NULLs at the top of
    a DESC ordering, which would float a half-filled draft above real history.
    """
    if spec.order_by is None:
        return (spec.model.created_at.desc(),)
    column = getattr(spec.model, spec.order_by)
    return (nulls_last(column.desc()), spec.model.created_at.desc())


async def _list(db: DbSession, company_id: str, spec: ws.Collection) -> list[dict]:
    rows = await db.scalars(
        select(spec.model)
        .where(spec.model.company_id == company_id)
        .order_by(*_order(spec))
    )
    return [ws.to_document(spec, row) for row in rows]


async def _get_row(db: DbSession, company_id: str, spec: ws.Collection, item_id: str):
    row = await db.scalar(
        select(spec.model).where(
            spec.model.id == item_id, spec.model.company_id == company_id
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı."
        )
    return row


# ── Whole workspace ───────────────────────────────────────────────────


@router.get("")
async def read_workspace(db: DbSession, company: CurrentCompany) -> dict[str, Any]:
    """Company profile plus every collection, in one round trip.

    The client needs all five to build the compute snapshot, so fetching them
    together avoids a waterfall of requests on every page load.
    """
    payload: dict[str, Any] = {"company": ws.company_document(company)}
    for name, spec in ws.COLLECTIONS.items():
        payload[name] = await _list(db, company.id, spec)
    return payload


@router.get("/company")
async def read_company(company: CurrentCompany) -> dict[str, Any]:
    """Just the profile. Declared before ``/{collection}`` so the literal
    path wins the match."""
    return ws.company_document(company)


@router.patch("/company")
async def update_company(
    db: DbSession,
    company: CurrentCompany,
    patch: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    ws.apply_patch(ws.COMPANY, company, patch)
    db.add(company)
    await db.flush()
    return ws.company_document(company)


# ── Generic collection CRUD ───────────────────────────────────────────


@router.get("/{collection}")
async def list_items(
    db: DbSession, company: CurrentCompany, collection: str = Path(...)
) -> list[dict[str, Any]]:
    return await _list(db, company.id, _spec(collection))


@router.post("/{collection}", status_code=status.HTTP_201_CREATED)
async def create_item(
    db: DbSession,
    company: CurrentCompany,
    collection: str = Path(...),
    document: dict[str, Any] = Body(...),
) -> dict[str, str]:
    spec = _spec(collection)
    row = spec.model(company_id=company.id, **ws.to_columns(spec, document))
    db.add(row)
    await db.flush()
    return {"id": row.id}


@router.post("/{collection}/bulk", status_code=status.HTTP_201_CREATED)
async def create_items(
    db: DbSession,
    company: CurrentCompany,
    collection: str = Path(...),
    documents: list[dict[str, Any]] = Body(...),
) -> dict[str, list[str]]:
    """Insert many documents in one transaction — the demo seeder's write path."""
    if len(documents) > MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Tek seferde en fazla {MAX_BULK_ITEMS} kayıt yazılabilir.",
        )
    spec = _spec(collection)
    rows = [
        spec.model(company_id=company.id, **ws.to_columns(spec, document))
        for document in documents
    ]
    db.add_all(rows)
    await db.flush()
    return {"ids": [row.id for row in rows]}


@router.patch("/{collection}/{item_id}")
async def update_item(
    db: DbSession,
    company: CurrentCompany,
    collection: str = Path(...),
    item_id: str = Path(...),
    patch: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    spec = _spec(collection)
    row = await _get_row(db, company.id, spec, item_id)
    ws.apply_patch(spec, row, patch)
    db.add(row)
    await db.flush()
    return ws.to_document(spec, row)


@router.delete("/{collection}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    db: DbSession,
    company: CurrentCompany,
    collection: str = Path(...),
    item_id: str = Path(...),
) -> Response:
    spec = _spec(collection)
    row = await _get_row(db, company.id, spec, item_id)
    await db.delete(row)
    await db.flush()
    # Returned explicitly: a 204 must carry no body, and FastAPI refuses to
    # build a route that could serialise one.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{collection}")
async def clear_collection(
    db: DbSession, company: CurrentCompany, collection: str = Path(...)
) -> dict[str, int]:
    """Delete every document in one collection. Backs "reset demo data"."""
    spec = _spec(collection)
    result = await db.execute(
        delete(spec.model).where(spec.model.company_id == company.id)
    )
    await db.flush()
    return {"deleted": result.rowcount or 0}


# ── Invoice ↔ ledger, atomically ──────────────────────────────────────


def _ledger_entry(company_id: str, invoice_doc: dict[str, Any], invoice_id: str):
    """The cash movement that corresponds to a settled invoice."""
    spec = ws.COLLECTIONS["transactions"]
    document = {
        "date": invoice_doc.get("paidDate") or invoice_doc.get("issueDate"),
        "amount": invoice_doc.get("amount", 0),
        "type": "income" if invoice_doc.get("direction") == "sales" else "expense",
        "category": invoice_doc.get("category") or "other",
        "description": f"{invoice_doc.get('number', '')} · {invoice_doc.get('vendor', '')}".strip(
            " ·"
        ),
        "vendor": invoice_doc.get("vendor") or "",
        "invoiceId": invoice_id,
    }
    return spec.model(company_id=company_id, **ws.to_columns(spec, document))


@router.post("/invoices/with-ledger", status_code=status.HTTP_201_CREATED)
async def create_invoice_with_ledger(
    db: DbSession,
    company: CurrentCompany,
    document: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Save an invoice and, when it is already paid, its cash movement."""
    spec = ws.COLLECTIONS["invoices"]
    invoice = spec.model(company_id=company.id, **ws.to_columns(spec, document))
    db.add(invoice)
    await db.flush()

    transaction_id: str | None = None
    if document.get("status") == "paid":
        entry = _ledger_entry(company.id, document, invoice.id)
        db.add(entry)
        await db.flush()
        transaction_id = entry.id

    return {"id": invoice.id, "transactionId": transaction_id}


@router.post("/invoices/{item_id}/pay")
async def mark_invoice_paid(
    db: DbSession,
    company: CurrentCompany,
    item_id: str = Path(...),
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Flip an invoice to paid and post the matching cash movement."""
    spec = ws.COLLECTIONS["invoices"]
    invoice = await _get_row(db, company.id, spec, item_id)

    paid_date = body.get("paidDate") or dt.date.today().isoformat()
    ws.apply_patch(spec, invoice, {"status": "paid", "paidDate": paid_date})
    db.add(invoice)

    document = ws.to_document(spec, invoice)
    entry = _ledger_entry(company.id, document, invoice.id)
    db.add(entry)
    await db.flush()

    return {"invoice": ws.to_document(spec, invoice), "transactionId": entry.id}
