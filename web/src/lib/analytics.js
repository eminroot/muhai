/* ============================================================
   Local derivations over the workspace documents.

   Two jobs:
     1. Build the snapshot payload the compute API expects.
     2. Provide the same headline figures locally, so a backend outage
        degrades the dashboard to "no forecast / no score" instead of a
        blank page. The API remains the authority whenever it answers —
        these are the same aggregations, not a second source of truth.
   ============================================================ */

export const MONTHS_BACK = 12

const round2 = (n) => Math.round(n * 100) / 100
export const monthKey = (isoDate) => String(isoDate || '').slice(0, 7)
export const todayIso = () => new Date().toISOString().slice(0, 10)

/** The last `count` month keys ending at `date`, oldest first. */
export function monthSpan(date = new Date(), count = MONTHS_BACK) {
  const keys = []
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date(date.getFullYear(), date.getMonth() - i, 1)
    keys.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return keys
}

/** Income/expense/profit per month over a gap-free window. */
export function monthlySeries(transactions = [], date = new Date(), count = MONTHS_BACK) {
  const buckets = new Map()
  for (const t of transactions) {
    const key = monthKey(t.date)
    if (!key) continue
    const b = buckets.get(key) || { income: 0, expense: 0 }
    b[t.type === 'income' ? 'income' : 'expense'] += Number(t.amount) || 0
    buckets.set(key, b)
  }
  return monthSpan(date, count).map((key) => {
    const b = buckets.get(key) || { income: 0, expense: 0 }
    return {
      month: key,
      income: round2(b.income),
      expense: round2(b.expense),
      profit: round2(b.income - b.expense),
    }
  })
}

function delta(current, previous) {
  if (!previous) return current > 0 ? 100 : 0
  return Math.round(((current - previous) / Math.abs(previous)) * 1000) / 10
}

const VAT_RATE = 0.2
const vatOfGross = (gross) => round2(Math.max(gross, 0) * (VAT_RATE / (1 + VAT_RATE)))
const netKdv = (income, expense) => round2(Math.max(vatOfGross(income) - vatOfGross(expense), 0))

export function kpiBlock(series) {
  const current = series[series.length - 1] || { income: 0, expense: 0, profit: 0 }
  const previous = series[series.length - 2] || { income: 0, expense: 0, profit: 0 }
  const tax = netKdv(current.income, current.expense)
  const taxPrev = netKdv(previous.income, previous.expense)
  return {
    revenue: current.income,
    revenue_delta: delta(current.income, previous.income),
    expense: current.expense,
    expense_delta: delta(current.expense, previous.expense),
    profit: current.profit,
    profit_delta: delta(current.profit, previous.profit),
    tax,
    tax_delta: delta(tax, taxPrev),
  }
}

/** Expense totals per category for the trailing `months` window. */
export function expenseBreakdown(transactions = [], date = new Date(), months = 1) {
  const window = new Set(monthSpan(date, months))
  const totals = new Map()
  for (const t of transactions) {
    if (t.type !== 'expense' || !window.has(monthKey(t.date))) continue
    const key = t.category || 'other'
    totals.set(key, (totals.get(key) || 0) + (Number(t.amount) || 0))
  }
  return [...totals.entries()]
    .map(([key, value]) => ({ key, value: round2(value) }))
    .sort((a, b) => b.value - a.value)
}

export function isOverdue(invoice, asOf = todayIso()) {
  if (invoice.status === 'paid') return false
  if (invoice.status === 'overdue') return true
  return Boolean(invoice.dueDate && invoice.dueDate < asOf)
}

export function invoiceRollup(invoices = [], asOf = todayIso()) {
  let receivables = 0
  let payables = 0
  let overdueCount = 0
  let paidCount = 0

  for (const inv of invoices) {
    const amount = Number(inv.amount) || 0
    if (inv.status === 'paid') {
      paidCount++
      continue
    }
    if (inv.direction === 'sales') receivables += amount
    else payables += amount
    if (isOverdue(inv, asOf)) overdueCount++
  }

  return {
    receivables: round2(receivables),
    payables: round2(payables),
    overdueCount,
    paidCount,
    pendingCount: invoices.length - paidCount,
    total: invoices.length,
  }
}

/**
 * Cash on hand: the company's opening balance plus everything the ledger has
 * moved since.
 *
 * `cashBalance` on the company is *opening* cash, as the column says. It is a
 * non-nullable 0 for every account that never typed one in, so a reading of
 * "an explicit balance, or else the ledger" could never tell the two apart and
 * reported a flat zero for every real company — which then zeroed the runway,
 * the cash-flow score and the forecast's closing balance.
 */
export function cashBalance(company, transactions = []) {
  const opening = Number(company?.cashBalance) || 0
  const movement = transactions.reduce(
    (sum, t) => sum + (t.type === 'income' ? 1 : -1) * (Number(t.amount) || 0),
    0,
  )
  return round2(opening + movement)
}

/**
 * How many statutory obligations came due, and how many were filed on time.
 *
 * Only obligations whose due date has passed count: a draft for next month is
 * not late yet, and counting it would read as a missed deadline. Without this
 * the score engine saw no history at all and scored both compliance
 * categories — a quarter of the total — at a flat 100%.
 */
function complianceCounts(obligations = [], matches, asOf) {
  let total = 0
  let onTime = 0
  for (const o of obligations) {
    if (!matches(o) || !o.dueDate || o.dueDate > asOf) continue
    total++
    if (o.status !== 'filed') continue
    // Filed with no recorded date: credit it rather than penalise missing
    // metadata, the same way the backend treats a paid invoice.
    if (!o.paidDate || o.paidDate <= o.dueDate) onTime++
  }
  return { total, onTime }
}

/**
 * The payload posted to /api/compute/*. Trimmed to what the engines read,
 * so a company with thousands of movements still sends a compact body.
 */
export function buildSnapshot({
  company,
  transactions = [],
  invoices = [],
  products = [],
  employees = [],
  taxObligations = [],
  asOf,
}) {
  const date = asOf || todayIso()
  const horizonStart = new Date(new Date(date).getTime() - 400 * 86400000)
    .toISOString()
    .slice(0, 10)

  const tax = complianceCounts(taxObligations, (o) => o.type !== 'sgk', date)
  const sgk = complianceCounts(taxObligations, (o) => o.type === 'sgk', date)

  return {
    as_of: date,
    cash_balance: cashBalance(company, transactions),
    tax_deadlines_total: tax.total,
    tax_deadlines_on_time: tax.onTime,
    sgk_payments_total: sgk.total,
    sgk_payments_on_time: sgk.onTime,
    transactions: transactions
      .filter((t) => t.date && t.date >= horizonStart && t.date <= date)
      .map((t) => ({
        date: t.date,
        amount: Math.abs(Number(t.amount) || 0),
        type: t.type === 'income' ? 'income' : 'expense',
        category: t.category || null,
        description: t.description || null,
        vendor: t.vendor || null,
      })),
    invoices: invoices.map((i) => ({
      // The compliance checks name the offending document, so unlike the
      // other engines they need the id and the printed number.
      id: i.id || null,
      number: i.number || null,
      date: i.issueDate || null,
      due_date: i.dueDate || null,
      paid_date: i.paidDate || null,
      amount: Number(i.amount) || 0,
      vat_amount: Number(i.vatAmount) || 0,
      vendor: i.vendor || null,
      status: i.status || 'pending',
      direction: i.direction === 'sales' ? 'sales' : 'purchase',
    })),
    products: products.map((p) => ({
      name: p.name,
      stock: Number(p.stock) || 0,
      min_stock: Number(p.minStock) || 0,
      unit_price: Number(p.unitPrice) || 0,
      monthly_usage: Number(p.monthlyUsage) || 0,
    })),
    employees: employees.map((e) => ({
      name: e.name,
      gross_salary: Number(e.grossSalary) || 0,
      start_date: e.startDate || null,
    })),
  }
}

/** Everything the dashboard needs, computed locally. Shape matches the API. */
export function localDashboard({ company, transactions, invoices }, asOf = todayIso()) {
  const date = new Date(asOf)
  const series = monthlySeries(transactions, date)
  const rollup = invoiceRollup(invoices, asOf)
  return {
    kpis: kpiBlock(series),
    monthly: series,
    expense_breakdown: expenseBreakdown(transactions, date),
    cash_balance: cashBalance(company, transactions),
    receivables: rollup.receivables,
    payables: rollup.payables,
    overdue_count: rollup.overdueCount,
    deadlines: [],
    insight: '',
    local: true,
  }
}

export function lowStock(products = []) {
  return products.filter((p) => (Number(p.stock) || 0) <= (Number(p.minStock) || 0))
}

export function inventoryValue(products = []) {
  return round2(
    products.reduce((s, p) => s + (Number(p.stock) || 0) * (Number(p.unitPrice) || 0), 0),
  )
}

/** Months of stock left at the recorded usage rate; null when usage is unknown. */
export function monthsOfCover(product) {
  const usage = Number(product.monthlyUsage) || 0
  if (usage <= 0) return null
  return Math.round(((Number(product.stock) || 0) / usage) * 10) / 10
}
