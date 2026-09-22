/* ============================================================
   The HTTP client every request goes through.

   One origin, one token. The API is Muhai's own FastAPI service: it holds the
   data, the maths and the sessions. There is no third-party SDK in the path
   any more, and nothing but this file knows where the API lives or how a
   request is authenticated.

   Three rules the rest of the app relies on:
     1. Every call has a timeout. A hanging fetch is worse than a failure.
     2. A failure raises ApiError with a message a business owner can read —
        callers show locally-derived numbers and an "offline" badge rather
        than a blank screen.
     3. A 401 clears the stored session exactly once and tells the app, so an
        expired token lands on the login screen instead of looping.
   ============================================================ */

// Empty in a production build: the app and the API share an origin and nginx
// proxies /api to the backend, so no hostname is baked into the bundle. In
// development the Vite server is on :5173 and the API on :8000.
const RAW_BASE =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

export const apiBaseUrl = RAW_BASE.replace(/\/$/, '')

const TOKEN_KEY = 'muhai.token'
const DEFAULT_TIMEOUT_MS = 20000

export class ApiError extends Error {
  constructor(message, { status = 0, detail = null, cause = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.cause = cause
  }

  /** True when the request never reached the server. */
  get isOffline() {
    return this.status === 0
  }
}

// ── Session token ─────────────────────────────────────────────────────
// localStorage rather than a cookie: the API is stateless and CSRF-free
// because nothing is sent ambiently — every authenticated request carries the
// token in a header this file adds.

let memoryToken = null

export function getToken() {
  if (memoryToken) return memoryToken
  try {
    memoryToken = localStorage.getItem(TOKEN_KEY)
  } catch {
    // Private mode, or storage blocked. The session is then tab-only.
    memoryToken = null
  }
  return memoryToken
}

export function setToken(token) {
  memoryToken = token || null
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* in-memory session only */
  }
}

export function clearToken() {
  setToken(null)
}

// The auth context registers here so an expired token can unwind the session
// from any call site, not just the ones that happen to be inside a component.
let onUnauthenticated = null

export function setUnauthenticatedHandler(fn) {
  onUnauthenticated = fn
}

// ── Requests ──────────────────────────────────────────────────────────

export async function request(
  path,
  { method = 'GET', body, isForm = false, timeout = DEFAULT_TIMEOUT_MS, auth = true } = {},
) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  const token = auth ? getToken() : null

  try {
    const res = await fetch(`${apiBaseUrl}${path}`, {
      method,
      headers: {
        ...(isForm ? {} : body != null ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: isForm ? body : body != null ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })

    if (res.status === 401) {
      clearToken()
      onUnauthenticated?.()
      throw new ApiError('Oturumunuzun süresi doldu. Tekrar giriş yapın.', { status: 401 })
    }

    if (!res.ok) {
      let detail = null
      try {
        detail = (await res.json())?.detail ?? null
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(
        typeof detail === 'string' ? detail : `İstek başarısız (HTTP ${res.status})`,
        { status: res.status, detail },
      )
    }

    if (res.status === 204) return null
    return await res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err.name === 'AbortError') {
      throw new ApiError('Sunucu yanıt vermedi (zaman aşımı).', { status: 0, cause: err })
    }
    throw new ApiError('Sunucuya ulaşılamıyor.', { status: 0, cause: err })
  } finally {
    clearTimeout(timer)
  }
}

export const get = (path, options) => request(path, { ...options, method: 'GET' })
export const post = (path, body, options) => request(path, { ...options, method: 'POST', body })
export const patch = (path, body, options) => request(path, { ...options, method: 'PATCH', body })
export const del = (path, options) => request(path, { ...options, method: 'DELETE' })

/** Liveness probe used by the connection badge. */
export async function ping(timeout = 5000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}
