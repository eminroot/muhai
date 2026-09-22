/* ============================================================
   Muhai compute API client.

   /api/workspace stores the data; /api/compute computes over it. Every call
   carries the session token, which the backend verifies with the same secret
   that signed it.

   The compute layer reads no table: the browser posts the snapshot it wants
   analysed and gets back the result. That is why a failure here is survivable
   — callers fall back to local aggregation and badge it — while a failure in
   db.js is not.
   ============================================================ */
import { ApiError, apiBaseUrl, ping, request } from './client.js'

const PREFIX = '/api/compute'

export { ApiError, apiBaseUrl, ping }

const compute = (path, body, options = {}) =>
  request(`${PREFIX}${path}`, { method: 'POST', body, ...options })

// ── Endpoints ─────────────────────────────────────────────────────────
export const getDashboard = (snapshot) => compute('/dashboard', snapshot)
export const getMuhaiScore = (snapshot) => compute('/muhai-score', snapshot)
export const getForecast = (snapshot, horizon = 30) =>
  compute(`/forecast?horizon=${horizon}`, snapshot, { timeout: 45000 })
export const getCompliance = (snapshot) => compute('/compliance', snapshot)
export const getTaxSummary = (snapshot) => compute('/tax-summary', snapshot)
export const runPayroll = (snapshot) => compute('/payroll', snapshot)
// `learned` is this company's vendor -> category map. The compute layer reads
// no table, so the browser carries what it has taught the classifier.
export const classifyExpenses = (items, learned = {}) =>
  compute('/classify', { items, learned })
export const askAssistant = (message, snapshot, lang = 'tr') =>
  compute('/chat', { message, snapshot, lang }, { timeout: 40000 })

export function scanInvoice(file) {
  const form = new FormData()
  form.append('file', file)
  return request(`${PREFIX}/ocr`, {
    method: 'POST',
    body: form,
    isForm: true,
    timeout: 60000,
  })
}
