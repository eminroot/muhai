import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Sparkles, X, ArrowRight } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { useChat } from './useChat.js'
import ChatMessages from './ChatMessages.jsx'
import ChatComposer from './ChatComposer.jsx'

export default function ChatWidget() {
  const { t } = useLang()
  const { messages, loading, send } = useChat()
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Hide the floating widget on the dedicated assistant page
  if (location.pathname.startsWith('/app/assistant')) return null

  const suggestions = ['assistant.suggest1', 'assistant.suggest2', 'assistant.suggest3']

  return (
    <>
      <AnimatePresence>
        {!open && (
          <motion.button
            className="chat-fab"
            onClick={() => setOpen(true)}
            aria-label={t('chatbot.open')}
            initial={{ opacity: 0, scale: 0.8, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 10 }}
            transition={{ type: 'spring', stiffness: 380, damping: 28 }}
          >
            <Sparkles size={18} strokeWidth={1.75} />
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <motion.div
            className="chat-panel"
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          >
            <div className="chat-head">
              <span className="chat-head__av">
                <Sparkles size={16} strokeWidth={1.9} />
              </span>
              <div style={{ flex: 1 }}>
                <div className="chat-head__name">{t('chatbot.title')}</div>
                <div className="chat-head__status">
                  <span className="live-dot" />
                  {t('chatbot.online')}
                </div>
              </div>
              <button className="topbar__icon-btn" onClick={() => setOpen(false)} aria-label="Close" >
                <X size={15} strokeWidth={1.9} />
              </button>
            </div>

            <div className="chat-stream">
              <ChatMessages messages={messages} loading={loading} />
              {messages.length === 0 && !loading && (
                <div className="chat-suggests">
                  {suggestions.map((s) => (
                    <button key={s} className="chat-suggest" onClick={() => send(t(s))}>
                      <ArrowRight size={13} strokeWidth={1.9} />
                      {t(s)}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <ChatComposer onSend={send} loading={loading} />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
