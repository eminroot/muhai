/* ============================================================
   Company data access.

   One company per account. The signed-in token *is* the company scope: the
   API resolves it server-side, so no call here passes a company id and no
   client-side code can ask for another company's rows. That replaced the
   Firestore security rules with something the database enforces itself.

   The document shapes are unchanged from when Firestore held them:

     invoices        number, vendor, direction, issueDate, dueDate, paidDate,
                     netAmount, vatAmount, amount, status, category, source,
                     ocrConfidence, needsReview
     transactions    date, amount, type, category, description, vendor
     products        name, sku, stock, minStock, unitPrice, monthlyUsage
     employees       name, role, grossSalary, startDate, sgkNo
     taxObligations  type, name, period, dueDate, amount, status

   Dates stay ISO "YYYY-MM-DD" strings rather than timestamps: they are
   calendar dates (an invoice is dated the 5th regardless of timezone), they
   sort lexicographically, and they cross the API boundary unchanged.
   ============================================================ */
import { del, get, patch, post } from './client.js'

export const COLLECTIONS = {
  invoices: 'invoices',
  transactions: 'transactions',
  products: 'products',
  employees: 'employees',
  taxObligations: 'taxObligations',
}

/*
   Learned vendor → category corrections. Deliberately *outside* COLLECTIONS:
   Settings iterates that object to wipe the demo dataset, and what the
   classifier has learned from a human is not demo data. It gets its own
   "forget" button instead.
*/
export const VENDOR_CATEGORIES = 'vendorCategories'

const BASE = '/api/workspace'

// ── Vendor keys ───────────────────────────────────────────────────────
/*
   Must agree character for character with `vendor_key` in the backend's
   expense_classifier.py — the browser writes the key and the API looks it up.
   Punctuation is deleted rather than spaced so "A.Ş." and "AŞ" are one vendor.
*/
const VENDOR_FOLD = {
  ı: 'i', İ: 'i', ş: 's', Ş: 's', ğ: 'g', Ğ: 'g', ü: 'u', Ü: 'u',
  ö: 'o', Ö: 'o', ç: 'c', Ç: 'c', â: 'a', î: 'i', û: 'u',
}

export function vendorKey(vendor) {
  if (!vendor) return ''
  const folded = String(vendor)
    .toLowerCase()
    .replace(/[ıİşŞğĞüÜöÖçÇâîû]/g, (ch) => VENDOR_FOLD[ch] || ch)
  // Keep letters, digits and whitespace; drop everything else outright.
  return folded.replace(/[^\p{L}\p{N}\s]/gu, '').split(/\s+/).filter(Boolean).join(' ')
}

// ── Change notification ───────────────────────────────────────────────
/*
   Firestore pushed every write back to the app, so a screen that saved
   something saw it appear without asking. A REST API does not, and making
   each of the seven calling screens remember to refetch would be a bug
   waiting to happen — the one that forgets shows stale figures.

   So every mutation below announces itself here and DataContext reloads. The
   round trip is the cost of not needing an open socket; a company's whole
   dataset is a few hundred rows.
*/
const listeners = new Set()

/** Subscribe to workspace mutations. Returns the unsubscribe function. */
export function onChange(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function notify(collection) {
  for (const listener of listeners) {
    try {
      listener(collection)
    } catch (e) {
      console.error('[muhai] workspace change listener failed', e)
    }
  }
}

// ── Company ───────────────────────────────────────────────────────────

/**
 * Company profile plus all five collections, in one round trip.
 * The app needs every collection to build the compute snapshot, so fetching
 * them together avoids a request waterfall on each load.
 */
export function loadWorkspace() {
  return get(BASE, { timeout: 30000 })
}

export function getCompany() {
  return get(`${BASE}/company`)
}

export async function updateCompany(patchDoc) {
  const company = await patch(`${BASE}/company`, patchDoc)
  notify('company')
  return company
}

// ── Generic collection access ─────────────────────────────────────────

export function listAll(name) {
  return get(`${BASE}/${name}`, { timeout: 30000 })
}

export async function addItem(name, data) {
  const { id } = await post(`${BASE}/${name}`, data)
  notify(name)
  return id
}

export async function updateItem(name, id, patchDoc) {
  const doc = await patch(`${BASE}/${name}/${id}`, patchDoc)
  notify(name)
  return doc
}

export async function removeItem(name, id) {
  await del(`${BASE}/${name}/${id}`)
  notify(name)
}

/**
 * Write many documents at once.
 * The server takes up to 1000 per call and commits them in one transaction;
 * this chunks so a larger dataset still arrives as a few whole batches rather
 * than several hundred separate requests.
 */
export async function addMany(name, items) {
  const CHUNK = 500
  const ids = []
  for (let i = 0; i < items.length; i += CHUNK) {
    const res = await post(`${BASE}/${name}/bulk`, items.slice(i, i + CHUNK), {
      timeout: 60000,
    })
    ids.push(...res.ids)
  }
  notify(name)
  return ids
}

// ── Learned vendor categories ─────────────────────────────────────────

/**
 * Build the `vendorKey -> category` map the compute API expects.
 * A duplicate key (two rows for one vendor, which the table does not forbid)
 * resolves to the most recently created row.
 */
export function vendorCategoryMap(rows = []) {
  const byKey = new Map()
  for (const row of rows) {
    const key = row.vendorKey || vendorKey(row.vendor)
    if (!key || !row.category) continue
    const seen = byKey.get(key)
    if (!seen || String(row.createdAt || '') >= String(seen.createdAt || '')) {
      byKey.set(key, row)
    }
  }
  return Object.fromEntries([...byKey].map(([key, row]) => [key, row.category]))
}

/**
 * Teach the classifier that this vendor belongs to this category.
 *
 * Upserts by hand because the workspace router is generic CRUD with no
 * conflict handling — see the model's docstring. `rows` is the collection the
 * caller already has, so the common case costs one write and no extra read.
 */
export async function rememberVendorCategory(rows, vendor, category, corrected = true) {
  const key = vendorKey(vendor)
  if (!key || !category) return null

  const existing = rows.find((r) => (r.vendorKey || vendorKey(r.vendor)) === key)
  if (existing) {
    if (existing.category === category) return existing.id
    await updateItem(VENDOR_CATEGORIES, existing.id, { category, corrected })
    return existing.id
  }
  return addItem(VENDOR_CATEGORIES, {
    vendorKey: key,
    vendor: String(vendor).trim(),
    category,
    corrected,
  })
}

/** Forget one learned vendor. */
export function forgetVendorCategory(id) {
  return removeItem(VENDOR_CATEGORIES, id)
}

/** Delete every document in a collection. Used by "reset demo data". */
export async function clearCollection(name) {
  const res = await del(`${BASE}/${name}`, { timeout: 30000 })
  notify(name)
  return res?.deleted ?? 0
}

// ── Invoice → ledger ──────────────────────────────────────────────────

/**
 * Save an invoice and, when it is already paid, the matching cash movement.
 * The server does both in one transaction, so the dashboard can never show an
 * invoice whose money never moved (or the reverse).
 */
export async function saveInvoiceWithLedger(invoice) {
  const { id } = await post(`${BASE}/invoices/with-ledger`, invoice)
  notify('invoices')
  return id
}

/** Flip an invoice to paid and post the cash movement in the same transaction. */
export async function markInvoicePaid(invoice, paidDate) {
  const result = await post(
    `${BASE}/invoices/${invoice.id}/pay`,
    paidDate ? { paidDate } : {},
  )
  notify('invoices')
  return result
}
