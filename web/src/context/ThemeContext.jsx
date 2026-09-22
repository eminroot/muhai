import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const KEY = 'muhai.theme'
const ThemeContext = createContext(null)

/** Whatever the inline boot script in index.html already painted. */
function current() {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(current)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* private windows and blocked storage: the theme just does not persist */
    }
  }, [theme])

  // Follow the OS only while the user has expressed no preference of their own.
  useEffect(() => {
    let stored = null
    try {
      stored = localStorage.getItem(KEY)
    } catch {
      stored = null
    }
    if (stored) return undefined

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => setTheme(media.matches ? 'dark' : 'light')
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])
  const value = useMemo(() => ({ theme, setTheme, toggle }), [theme, toggle])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  return useContext(ThemeContext) ?? { theme: 'light', toggle: () => {}, setTheme: () => {} }
}
