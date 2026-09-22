import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import { translations } from './translations.js'

const LanguageContext = createContext(null)

const STORAGE_KEY = 'muhai.lang'

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    if (typeof window === 'undefined') return 'tr'
    return window.localStorage.getItem(STORAGE_KEY) || 'tr'
  })

  const toggle = useCallback(() => {
    setLang((prev) => {
      const next = prev === 'tr' ? 'en' : 'tr'
      window.localStorage.setItem(STORAGE_KEY, next)
      document.documentElement.lang = next
      return next
    })
  }, [])

  const setLanguage = useCallback((next) => {
    window.localStorage.setItem(STORAGE_KEY, next)
    document.documentElement.lang = next
    setLang(next)
  }, [])

  // t('a.b.c') deep-key lookup with graceful fallback
  const t = useCallback(
    (key) => {
      const dict = translations[lang] || translations.tr
      const value = key.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), dict)
      if (value == null) {
        const fb = key.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), translations.tr)
        return fb == null ? key : fb
      }
      return value
    },
    [lang],
  )

  const value = useMemo(() => ({ lang, t, toggle, setLanguage }), [lang, t, toggle, setLanguage])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLang() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLang must be used within LanguageProvider')
  return ctx
}
