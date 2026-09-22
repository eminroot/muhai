import { useCallback, useState } from 'react'
import { askAssistant } from '../../lib/api.js'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { useData } from '../../context/DataContext.jsx'

/**
 * Shared chat state for the floating widget and the Assistant page.
 *
 * The question goes to the backend together with this company's snapshot, so
 * the reply is grounded in real figures. The Gemini key stays server-side
 * (F3) — nothing about the model is reachable from the browser bundle.
 */
export function useChat() {
  const { lang, t } = useLang()
  const { snapshot } = useData()
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  const send = useCallback(
    async (text) => {
      const trimmed = text.trim()
      if (!trimmed || loading) return

      setMessages((m) => [...m, { role: 'user', text: trimmed }])
      setLoading(true)

      try {
        const res = await askAssistant(trimmed, snapshot, lang)
        setMessages((m) => [
          ...m,
          { role: 'assistant', text: res.reply || t('assistant.error'), source: res.source },
        ])
      } catch (e) {
        console.error('[muhai] assistant error', e)
        setMessages((m) => [...m, { role: 'assistant', text: e.message || t('assistant.error'), error: true }])
      } finally {
        setLoading(false)
      }
    },
    [lang, loading, snapshot, t],
  )

  const clear = useCallback(() => setMessages([]), [])

  return { messages, loading, send, clear }
}
