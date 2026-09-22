/* ============================================================
   KDV arithmetic.

   Lived in `lib/seed.js` until the demo generator moved to the backend —
   which meant every screen that splits a gross amount imported the demo
   dataset to get at one function. It is not demo code: an invoice typed by
   hand needs the same split as a seeded one.
   ============================================================ */

/** The general KDV rate. The reduced rates (10%, 1%) are picked per line. */
export const VAT_RATE = 0.2

const round2 = (n) => Math.round(n * 100) / 100

/** Split a gross (KDV-inclusive) amount into net + VAT. */
export function splitVat(gross, rate = VAT_RATE) {
  const net = round2(gross / (1 + rate))
  return { net, vat: round2(gross - net) }
}
