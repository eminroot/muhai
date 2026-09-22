/* ============================================================
   Authentication + company identity.

   One account owns one company. Registration creates both in a single server
   transaction and leaves the workspace empty — the only seeded dataset is the
   demo account the backend's scripts/seed_demo.py writes.

   The session is a JWT issued by Muhai's own API and kept in localStorage. On
   load the app asks /api/auth/me whether that token is still good — one round
   trip, after which `user` and `company` are settled for the session.
   ============================================================ */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  ApiError,
  clearToken,
  get as httpGet,
  getToken,
  post,
  setToken,
  setUnauthenticatedHandler,
} from '../lib/client.js'
import { getCompany, updateCompany } from '../lib/db.js'
import {
  CANCELLED,
  completeRedirectSignIn,
  getGoogleIdToken,
  hasPendingRedirect,
  signOutOfGoogle,
} from '../lib/firebase.js'

const AuthContext = createContext(null)

/** Turn an API failure into a message a business owner can act on. */
export function authErrorMessage(err, lang = 'tr') {
  if (err instanceof ApiError) {
    // The API already answers in Turkish; only the transport errors need a
    // second language.
    if (err.isOffline) {
      return lang === 'en'
        ? 'Could not reach the Muhai server. Check your connection.'
        : 'Muhai sunucusuna ulaşılamadı. Bağlantınızı kontrol edin.'
    }
    return err.message
  }
  return err?.message || (lang === 'en' ? 'Something went wrong.' : 'Bir hata oluştu.')
}

/**
 * Shape the API's user record the way the app reads it.
 * `uid` is kept as the identifier name the screens already use.
 */
function toUser(record) {
  if (!record) return null
  return {
    uid: record.id,
    email: record.email,
    displayName: record.display_name || '',
    businessName: record.business_name || '',
    role: record.role || 'owner',
    companyId: record.company_id ?? null,
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const applySession = useCallback((session) => {
    setUser(toUser(session?.user))
    setCompany(session?.company ?? null)
    setError(null)
  }, [])

  const endSession = useCallback(() => {
    clearToken()
    setUser(null)
    setCompany(null)
  }, [])

  // A 401 from any call — not just the ones a component is awaiting — unwinds
  // the session, so an expired token lands on the login screen once rather
  // than failing every panel separately.
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      setUser(null)
      setCompany(null)
    })
    return () => setUnauthenticatedHandler(null)
  }, [])

  // Restore the stored session on load.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const session = await httpGet('/api/auth/me')
        if (!cancelled) applySession(session)
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 401) {
          // Already cleared by the client; nothing more to do.
        } else {
          console.error('[muhai] could not restore the session', e)
          setError(e)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [applySession])

  /**
   * Create the account and its company in one call.
   *
   * The new workspace is empty, and stays that way until its owner puts
   * something in it. Registration used to generate a year of demo trading in
   * the browser and write it here; the only seeded dataset now is the demo
   * account the backend creates.
   */
  const register = useCallback(
    async ({ email, password, displayName, company: companyInput }) => {
      const session = await post(
        '/api/auth/register',
        {
          email,
          password,
          business_name: companyInput?.name || email,
          display_name: displayName || '',
          company: {
            name: companyInput?.name || '',
            taxId: companyInput?.taxId || '',
            taxOffice: companyInput?.taxOffice || '',
            sector: companyInput?.sector || 'general',
            city: companyInput?.city || '',
            legalForm: companyInput?.legalForm || 'ltd',
          },
        },
        { auth: false },
      )

      setToken(session.access_token)
      applySession(session)

      return session.company?.id ?? null
    },
    [applySession],
  )

  const login = useCallback(
    async ({ email, password }) => {
      const session = await post('/api/auth/login', { email, password }, { auth: false })
      setToken(session.access_token)
      applySession(session)
      return toUser(session.user)
    },
    [applySession],
  )

  /**
   * Turn a Firebase ID token into a Muhai session.
   *
   * The exchange is the whole point: Google proves who the person is, the
   * API decides what they may see. Firebase is never the session, so every
   * later request is authenticated exactly the way a password login is.
   */
  const exchangeGoogleToken = useCallback(
    async (idToken) => {
      const session = await post('/api/auth/google', { id_token: idToken }, { auth: false })
      setToken(session.access_token)
      applySession(session)
      return toUser(session.user)
    },
    [applySession],
  )

  /**
   * Returns the signed-in user, or null when the browser had to fall back to
   * a redirect — in that case the page navigates away and comes back through
   * the effect below, so the caller should simply stop.
   */
  const loginWithGoogle = useCallback(async () => {
    const idToken = await getGoogleIdToken()
    if (!idToken) return null
    return exchangeGoogleToken(idToken)
  }, [exchangeGoogleToken])

  // The return leg of the redirect fallback. Gated on the flag the redirect
  // set, so an ordinary page load never pulls the Firebase SDK in just to be
  // told that nothing happened.
  useEffect(() => {
    if (!hasPendingRedirect()) return undefined
    let cancelled = false
    completeRedirectSignIn()
      .then((idToken) => {
        if (idToken && !cancelled) return exchangeGoogleToken(idToken)
        return null
      })
      .catch((err) => {
        if (!cancelled && !CANCELLED.has(err?.code)) setError(err)
      })
    return () => {
      cancelled = true
    }
  }, [exchangeGoogleToken])

  const logout = useCallback(async () => {
    // Nothing to revoke on our side: the token is stateless and short-lived
    // by policy. Google's session is separate and has to be dropped too, or
    // the next "sign in with Google" silently resumes the account just left.
    await signOutOfGoogle()
    endSession()
  }, [endSession])


  const refreshCompany = useCallback(async () => {
    if (!user?.companyId) return null
    const fresh = await getCompany()
    setCompany(fresh)
    return fresh
  }, [user?.companyId])

  const saveCompany = useCallback(
    async (patch) => {
      if (!user?.companyId) return
      setCompany(await updateCompany(patch))
    },
    [user?.companyId],
  )

  /** Attach a company to an account that registered without one. */
  const createCompanyForAccount = useCallback(
    async (companyInput) => {
      const session = await post('/api/auth/company', companyInput)
      applySession(session)
      return session.company?.id ?? null
    },
    [applySession],
  )

  // ProtectedRoute and the screens read `profile.companyId`; keeping that shape
  // means the routing logic did not have to change with the backend.
  const profile = useMemo(
    () =>
      user
        ? {
            uid: user.uid,
            email: user.email,
            displayName: user.displayName,
            companyId: user.companyId,
            role: user.role,
          }
        : null,
    [user],
  )

  const value = useMemo(
    () => ({
      user,
      profile,
      company,
      companyId: user?.companyId ?? null,
      loading,
      error,
      register,
      login,
      loginWithGoogle,
      logout,
      refreshCompany,
      saveCompany,
      createCompanyForAccount,
    }),
    [
      user, profile, company, loading, error, register, login, loginWithGoogle, logout,
      refreshCompany, saveCompany, createCompanyForAccount,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
