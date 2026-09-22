/* ============================================================
   Firebase — auth only, and only for "sign in with Google".

   This is the one third-party service in the app, and it is
   deliberately confined: it authenticates a person and hands
   back an ID token, which `AuthContext` posts to
   /api/auth/google. The backend verifies that token against
   Google's published certificates and issues Muhai's own JWT.
   **Firebase never holds the session** and no Firebase call
   goes near company data — that still lives in Postgres behind
   Muhai's own token, which is still what scopes every query.

   Analytics and the Realtime Database are deliberately not
   initialised. The project's config carries a `databaseURL` and
   a `measurementId` because the console emits them for every
   app; loading either here would pull in a second SDK, start
   collecting behavioural data without asking, and park a
   third-party store next to a ledger. Auth is all that is
   wanted, so auth is all that is loaded.

   **The SDK is loaded on demand.** Imported at the top level it
   cost 160 kB raw / ~34 kB gzipped on every page load —
   including the marketing page, where nobody has asked to sign
   in to anything. Everything below imports it inside the
   function that needs it, so the cost lands on the click.

   The keys are Firebase's *public* client identifiers: the same
   values ship in any web bundle using Firebase and authorise
   nothing on their own. Access is governed by the project's
   authorised-domain list and by the backend's checks. They are
   overridable through VITE_FIREBASE_* so a fork can point at
   its own project without editing source.
   ============================================================ */

const env = import.meta.env

const firebaseConfig = {
  apiKey: env.VITE_FIREBASE_API_KEY || 'AIzaSyBddU5RNPQuFg6sKr8JzW1RKZNd90Dz7Jc',
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN || 'cyberxbank-7dc0b.firebaseapp.com',
  projectId: env.VITE_FIREBASE_PROJECT_ID || 'cyberxbank-7dc0b',
  storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET || 'cyberxbank-7dc0b.firebasestorage.app',
  messagingSenderId: env.VITE_FIREBASE_SENDER_ID || '448176780627',
  appId: env.VITE_FIREBASE_APP_ID || '1:448176780627:web:463aab01136eef36c85da6',
}

/** Set just before a redirect leaves the page, read on the way back in. */
const REDIRECT_FLAG = 'muhai.googleRedirect'

/** Codes that mean "the person changed their mind", not "something broke". */
export const CANCELLED = new Set([
  'auth/popup-closed-by-user',
  'auth/cancelled-popup-request',
  'auth/user-cancelled',
])

/** A popup was blocked or cannot work here — fall back, do not fail. */
const POPUP_FALLBACK = new Set([
  'auth/popup-blocked',
  'auth/operation-not-supported-in-this-environment',
  'auth/web-storage-unsupported',
])

let sdkPromise = null

/** Load and initialise the SDK once, on first real use. */
function loadSdk() {
  if (!sdkPromise) {
    sdkPromise = (async () => {
      const [{ initializeApp, getApps, getApp }, authMod] = await Promise.all([
        import('firebase/app'),
        import('firebase/auth'),
      ])
      // getApps() first: Vite's HMR re-runs this and initializeApp throws on
      // a duplicate name.
      const app = getApps().length ? getApp() : initializeApp(firebaseConfig)
      const auth = authMod.getAuth(app)
      const provider = new authMod.GoogleAuthProvider()
      // Always show the chooser. Without it a machine with one Google session
      // signs straight back in, which is baffling right after a sign-out.
      provider.setCustomParameters({ prompt: 'select_account' })
      return { auth, provider, authMod }
    })()
  }
  return sdkPromise
}

/**
 * Run the Google flow and return a fresh Firebase ID token.
 *
 * Popup first, because it keeps the page — and any half-filled form on it —
 * alive. Where a popup cannot work it falls back to a redirect and returns
 * null; the caller should stop, because the page is already navigating away
 * and will come back through `completeRedirectSignIn`.
 */
export async function getGoogleIdToken() {
  const { auth, provider, authMod } = await loadSdk()
  try {
    const result = await authMod.signInWithPopup(auth, provider)
    return await result.user.getIdToken()
  } catch (err) {
    if (POPUP_FALLBACK.has(err?.code)) {
      try {
        sessionStorage.setItem(REDIRECT_FLAG, '1')
      } catch {
        /* private mode; the redirect still works, it just costs a load */
      }
      await authMod.signInWithRedirect(auth, provider)
      return null
    }
    throw err
  }
}

/** True only on the load that follows a redirect we started. */
export function hasPendingRedirect() {
  try {
    return sessionStorage.getItem(REDIRECT_FLAG) === '1'
  } catch {
    return false
  }
}

/**
 * The other half of the redirect path. Returns a token when this load is the
 * return leg, else null.
 *
 * Guarded by the flag so the ordinary load of a marketing page never pulls
 * the SDK in just to be told nothing happened.
 */
export async function completeRedirectSignIn() {
  if (!hasPendingRedirect()) return null
  try {
    sessionStorage.removeItem(REDIRECT_FLAG)
  } catch {
    /* nothing to clear */
  }
  const { auth, authMod } = await loadSdk()
  const result = await authMod.getRedirectResult(auth)
  if (!result?.user) return null
  return result.user.getIdToken()
}

/**
 * Drop the Firebase session too.
 *
 * Muhai's own sign-out clears its JWT; without this the Google session
 * lingers and the next "sign in with Google" silently resumes the account the
 * person just left. It must never block signing out of Muhai — and it must
 * not drag the SDK in for someone who signed in with a password.
 */
export async function signOutOfGoogle() {
  if (!sdkPromise) return
  try {
    const { auth, authMod } = await loadSdk()
    await authMod.signOut(auth)
  } catch {
    /* already gone, or storage unavailable */
  }
}
