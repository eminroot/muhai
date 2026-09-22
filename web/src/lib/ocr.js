/* ============================================================
   Real client-side OCR with Tesseract.js, Turkish only.
   Recognizes an uploaded invoice image and heuristically
   parses Turkish-invoice fields out of the raw text.
   ============================================================ */
import Tesseract from 'tesseract.js'

/* ---- Vendored Tesseract assets (see web/public/tessdata) ------------
   Left unconfigured, tesseract.js pulls its worker, its wasm core and the
   language data from a CDN on first use, so the on-device OCR mode needs
   internet. Everything is vendored under public/tessdata and pointed at
   here, so this path works with the network unplugged.

   corePath is a *directory*: tesseract.js appends the right filename
   itself, picking tesseract-core-simd-lstm.wasm.js where WebAssembly SIMD
   is available and tesseract-core-lstm.wasm.js where it is not. Both are
   vendored. Only the LSTM cores are needed — the default OEM never asks
   for the legacy engine.

   langPath resolves to `<lang>.traineddata.gz`, hence gzip: true.
   -------------------------------------------------------------------- */
const TESSDATA = `${(import.meta.env.BASE_URL || '/').replace(/\/$/, '')}/tessdata`

/** "1.234,56" -> 1234.56 ; "1,234.56" -> 1234.56 ; "1.234" -> 1234 */
export function parseTRNumber(raw) {
  if (!raw) return NaN
  let s = String(raw).replace(/[^\d.,]/g, '').trim()
  if (!s) return NaN
  if (s.includes(',') && s.includes('.')) {
    // last separator is the decimal one
    if (s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(/\./g, '').replace(',', '.')
    else s = s.replace(/,/g, '')
  } else if (s.includes(',')) {
    s = s.replace(',', '.') // turkish decimal comma
  } else {
    // only dots: treat .000 groups as thousands
    const m = s.match(/\.(\d{3})(?:\D|$)/)
    if (m) s = s.replace(/\.(?=\d{3}(\D|$))/g, '')
  }
  return parseFloat(s)
}

// Currency-like tokens: 1.234,56 / 1,234.56 / 1234,56 / 12345
const NUM_RE = /\d{1,3}(?:[.\s]\d{3})+(?:[,.]\d{2})?|\d+[,.]\d{2}|\d{3,}/g

/** Find an amount on the first line matching any label; take the last number on it
 *  (rate tokens like "%20" sit before the real amount). */
function findAmount(lines, labels) {
  for (const label of labels) {
    const lre = new RegExp(label, 'i')
    for (const line of lines) {
      if (!lre.test(line)) continue
      const nums = line.match(NUM_RE)
      if (nums && nums.length) {
        const n = parseTRNumber(nums[nums.length - 1])
        if (!isNaN(n) && n > 0) return n
      }
    }
  }
  return null
}

/** Pull structured fields from recognized invoice text. */
export function extractFields(text) {
  const clean = text.replace(/\r/g, '')
  const lines = clean
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 1)

  // --- Tax ID (VKN 10 / TCKN 11) ---
  let taxId = ''
  const vknLabel = clean.match(/(?:vergi\s*(?:kimlik\s*)?(?:no|numaras[ıi])?|vkn|tckn)[^\d]{0,14}(\d[\d\s]{8,13}\d)/i)
  if (vknLabel) taxId = vknLabel[1].replace(/\s/g, '')
  if (!taxId || (taxId.length !== 10 && taxId.length !== 11)) {
    const any = clean.match(/\b(\d{11}|\d{10})\b/)
    if (any) taxId = any[1]
  }

  // --- Invoice number ---
  let invoiceNo = ''
  const inv = clean.match(
    /(?:fatura\s*(?:no|numaras[ıi])|belge\s*(?:no|numaras[ıi])|invoice\s*(?:no\.?|number|#)|seri\s*[\/-]?\s*s[ıi]ra)[^A-Z0-9]{0,8}([A-Z0-9][A-Z0-9\-\/.]{4,})/i,
  )
  if (inv) invoiceNo = inv[1].replace(/[.,;]+$/, '')

  // --- Vendor (line with a company suffix, else first meaningful line) ---
  const compRe = /(A\.?\s?Ş\.?|LTD|Ltd|ŞT[İI]|Şti|SAN\.?|T[İI]C\.?|Tic\.?|San\.?|GmbH|Inc\.?|Co\.?|Limited|A\.Ş)/
  let vendor = lines.find((l) => compRe.test(l) && l.length <= 60)
  if (!vendor) vendor = lines.find((l) => /[A-Za-zĞÜŞİÖÇğüşıöç]{4,}/.test(l)) || lines[0] || ''

  // --- Amounts (line-based) ---
  const total = findAmount(lines, ['genel\\s*toplam', 'ödenecek\\s*tutar', 'toplam\\s*tutar', 'grand\\s*total', '\\btotal\\b'])
  const vat = findAmount(lines, ['k\\.?\\s?d\\.?\\s?v\\.?', 'hesaplanan\\s*kdv', '\\bvat\\b', 'tax\\s*amount'])
  let subtotal = findAmount(lines, ['ara\\s*toplam', 'mal\\s*hizmet\\s*toplam', 'matrah', 'sub\\s*total', 'net\\s*tutar'])
  if (subtotal == null && total != null && vat != null) subtotal = Math.max(0, total - vat)

  // fallback: largest currency-formatted number is likely the total
  const allAmts = [...clean.matchAll(/\d{1,3}(?:[.\s]\d{3})*[,.]\d{2}/g)]
    .map((m) => parseTRNumber(m[0]))
    .filter((n) => !isNaN(n) && n > 0)
  const maxAmt = allAmts.length ? Math.max(...allAmts) : null

  return {
    vendor: (vendor || '—').slice(0, 48),
    invoiceNo: invoiceNo || '—',
    taxId: taxId || '—',
    subtotal: subtotal,
    vat: vat,
    total: total ?? maxAmt,
  }
}

/* ---- Worker ---------------------------------------------------------
   `Tesseract.recognize()` cannot set page-segmentation mode, and the default
   (PSM 3, full layout analysis) reads an invoice as two columns — labels in
   one, amounts in the other — so `extractFields` below finds "Ara Toplam:"
   with no number beside it. PSM 6 treats the page as one uniform block and
   keeps each row together. Same finding as the server engine, same fix.

   Turkish alone, not "tur+eng": running both models costs a second pass and
   reconciles two dictionaries against Turkish text, which loses fields rather
   than winning them. Only `tur.traineddata.gz` is vendored now; adding
   English back means putting `eng.traineddata.gz` into public/tessdata as
   well, or tesseract.js will try to fetch it from a CDN and fail offline.

   The worker is created once and reused. Each creation re-fetches and
   re-instantiates ~4 MB of wasm, which is the slowest part of a scan.
   -------------------------------------------------------------------- */
let workerPromise = null
// The worker outlives any one scan, so its logger cannot close over a single
// caller's callback. It reports to whichever scan is currently running.
let activeProgress = null

function getWorker() {
  if (!workerPromise) {
    workerPromise = Tesseract.createWorker('tur', 1, {
      workerPath: `${TESSDATA}/worker.min.js`,
      corePath: TESSDATA,
      langPath: TESSDATA,
      gzip: true,
      logger: (m) => {
        if (m.status === 'recognizing text' && activeProgress) activeProgress(m.progress)
      },
    })
      .then(async (worker) => {
        await worker.setParameters({ tessedit_pageseg_mode: '6' })
        return worker
      })
      .catch((err) => {
        // Never cache a failed init — the next scan should be able to retry.
        workerPromise = null
        throw err
      })
  }
  return workerPromise
}

/**
 * Run OCR on an image (File, Blob, data URL, or <img>/canvas).
 * @param {*} image
 * @param {(progress:number)=>void} onProgress 0..1
 * @returns {Promise<{text:string, confidence:number, fields:object}>}
 */
export async function runOcr(image, onProgress) {
  const worker = await getWorker()
  activeProgress = onProgress || null
  try {
    const { data } = await worker.recognize(image)
    return {
      text: data.text || '',
      confidence: Math.max(0, Math.min(100, Math.round(data.confidence || 0))),
      fields: extractFields(data.text || ''),
    }
  } finally {
    activeProgress = null
  }
}
