/* ============================================================
   Company data.

   Loads the company's five collections from /api/workspace and asks
   /api/compute for the derived analytics: dashboard rollup, Muhai Score,
   Prophet forecast, tax summary and payroll.

   Firestore used to push writes back to every open tab. A REST API does not,
   so db.js announces each mutation and this provider reloads — see the note
   there. The reload is debounced because a screen that writes an invoice and
   its ledger entry fires twice in the same tick.

   If the compute API is unreachable the dashboard still renders: the same
   aggregations are computed locally and `apiOnline` goes false so the UI can
   say so honestly instead of showing stale or invented numbers.
   ============================================================ */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { loadWorkspace, onChange, vendorCategoryMap } from '../lib/db.js'
import { buildSnapshot, localDashboard, todayIso } from '../lib/analytics.js'
import * as api from '../lib/api.js'
import { useAuth } from './AuthContext.jsx'

const DataContext = createContext(null)

const EMPTY = {
  invoices: [], transactions: [], products: [], employees: [], taxObligations: [],
  vendorCategories: [],
}

// Long enough to coalesce the writes of one user action, short enough that the
// screen updates before the user looks away.
const RELOAD_DEBOUNCE_MS = 150

export function DataProvider({ children }) {
  const { companyId, company: authCompany, refreshCompany } = useAuth()

  const [raw, setRaw] = useState(EMPTY)
  const [company, setCompany] = useState(authCompany)
  const [loading, setLoading] = useState(true)
  const [dbError, setDbError] = useState(null)

  const [dashboard, setDashboard] = useState(null)
  const [score, setScore] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [taxSummary, setTaxSummary] = useState(null)
  const [payroll, setPayroll] = useState(null)
  const [compliance, setCompliance] = useState(null)

  const [apiOnline, setApiOnline] = useState(true)
  const [apiError, setApiError] = useState(null)
  const [computing, setComputing] = useState(false)

  // Keep the company profile in step with the auth context, which owns it
  // between sign-in and the first workspace load.
  useEffect(() => setCompany(authCompany), [authCompany])

  // ── Workspace load ──────────────────────────────────────────────────
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const load = useCallback(async () => {
    if (!companyId) {
      setRaw(EMPTY)
      setLoading(false)
      return
    }
    try {
      const workspace = await loadWorkspace()
      if (!mounted.current) return
      setRaw({
        invoices: workspace.invoices ?? [],
        transactions: workspace.transactions ?? [],
        products: workspace.products ?? [],
        employees: workspace.employees ?? [],
        taxObligations: workspace.taxObligations ?? [],
        vendorCategories: workspace.vendorCategories ?? [],
      })
      if (workspace.company) setCompany(workspace.company)
      setDbError(null)
    } catch (err) {
      if (!mounted.current) return
      console.error('[muhai] could not load the workspace', err)
      setDbError(err)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  // Reload after any write, debounced.
  useEffect(() => {
    if (!companyId) return undefined
    let timer = null
    const unsubscribe = onChange(() => {
      clearTimeout(timer)
      timer = setTimeout(load, RELOAD_DEBOUNCE_MS)
    })
    return () => {
      clearTimeout(timer)
      unsubscribe()
    }
  }, [companyId, load])

  // ── Snapshot posted to the compute API ──────────────────────────────
  const snapshot = useMemo(
    () =>
      buildSnapshot({
        company,
        transactions: raw.transactions,
        invoices: raw.invoices,
        products: raw.products,
        employees: raw.employees,
        // Filing history: the score's two compliance categories are 25% of the
        // total and had nothing to read until this was carried across.
        taxObligations: raw.taxObligations,
        asOf: todayIso(),
      }),
    [
      company, raw.transactions, raw.invoices, raw.products, raw.employees,
      raw.taxObligations,
    ],
  )

  // Compare by content: every reload hands back new array identities, and
  // recomputing a Prophet forecast on each one would be absurd.
  const snapshotKey = useMemo(() => JSON.stringify(snapshot), [snapshot])
  const lastComputed = useRef(null)

  const recompute = useCallback(
    async (payload) => {
      setComputing(true)
      const results = await Promise.allSettled([
        api.getDashboard(payload),
        api.getMuhaiScore(payload),
        api.getForecast(payload, 30),
        api.getTaxSummary(payload),
        api.runPayroll(payload),
        api.getCompliance(payload),
      ])
      const [d, s, f, t, p, c] = results

      const anyOk = results.some((r) => r.status === 'fulfilled')
      setApiOnline(anyOk)
      const firstFailure = results.find((r) => r.status === 'rejected')
      setApiError(anyOk ? null : firstFailure?.reason ?? null)

      setDashboard(
        d.status === 'fulfilled'
          ? d.value
          : localDashboard(
              { company, transactions: raw.transactions, invoices: raw.invoices },
              todayIso(),
            ),
      )
      if (s.status === 'fulfilled') setScore(s.value)
      if (f.status === 'fulfilled') setForecast(f.value)
      if (t.status === 'fulfilled') setTaxSummary(t.value)
      if (p.status === 'fulfilled') setPayroll(p.value)
      // Alerts are derived, never stored: a stale list would accuse the user
      // of a duplicate they have already deleted. Clear it when the check
      // could not run rather than keeping the last answer.
      setCompliance(c.status === 'fulfilled' ? c.value : null)

      if (!anyOk) {
        // Keep whatever the API last returned rather than blanking the panels;
        // the offline badge tells the user those figures are not live.
        console.warn('[muhai] compute API unreachable; showing local aggregation only')
      }
      setComputing(false)
    },
    [company, raw.transactions, raw.invoices],
  )

  useEffect(() => {
    if (loading || !companyId) return
    if (lastComputed.current === snapshotKey) return
    lastComputed.current = snapshotKey
    recompute(snapshot)
  }, [loading, companyId, snapshotKey, snapshot, recompute])

  const refresh = useCallback(async () => {
    lastComputed.current = null
    await load()
    await refreshCompany().catch(() => {})
    return recompute(snapshot)
  }, [load, recompute, refreshCompany, snapshot])

  // The vendor -> category map every classify call is posted with.
  const learnedCategories = useMemo(
    () => vendorCategoryMap(raw.vendorCategories),
    [raw.vendorCategories],
  )

  // Local aggregation is always available, so panels have something to show
  // during the very first round trip.
  const fallback = useMemo(
    () => localDashboard({ company, transactions: raw.transactions, invoices: raw.invoices }, todayIso()),
    [company, raw.transactions, raw.invoices],
  )

  const value = useMemo(
    () => ({
      companyId,
      company,
      loading,
      dbError,
      invoices: raw.invoices,
      transactions: raw.transactions,
      products: raw.products,
      employees: raw.employees,
      taxObligations: raw.taxObligations,
      vendorCategories: raw.vendorCategories,
      learnedCategories,
      snapshot,
      dashboard: dashboard || fallback,
      score,
      forecast,
      taxSummary,
      payroll,
      compliance,
      apiOnline,
      apiError,
      computing,
      isEmpty: !loading && raw.transactions.length === 0 && raw.invoices.length === 0,
      refresh,
    }),
    [
      companyId, company, loading, dbError, raw, snapshot, dashboard, fallback,
      score, forecast, taxSummary, payroll, compliance, learnedCategories,
      apiOnline, apiError, computing, refresh,
    ],
  )

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

export function useData() {
  const ctx = useContext(DataContext)
  if (!ctx) throw new Error('useData must be used inside <DataProvider>')
  return ctx
}
