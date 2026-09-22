import { motion } from 'framer-motion'
import { Sparkles, Database, Trash2, ArrowRight } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { useChat } from '../components/chatbot/useChat.js'
import ChatMessages from '../components/chatbot/ChatMessages.jsx'
import ChatComposer from '../components/chatbot/ChatComposer.jsx'

export default function Assistant() {
  const { t } = useLang()
  const { apiOnline } = useData()
  const { messages, loading, send, clear } = useChat()

  const suggestions = ['assistant.suggest1', 'assistant.suggest2', 'assistant.suggest3', 'assistant.suggest4']

  return (
    <div className="page">
      <div className="page-head page-head-row">
        <div>
          <div className="page-eyebrow">
            <Sparkles size={14} strokeWidth={1.9} />
            <span className="label">{t('nav.groupAi')}</span>
          </div>
          <h1 className="page-title">{t('assistant.title')}</h1>
          <p className="page-sub">{t('assistant.subtitle')}</p>
        </div>
        <div className="page-actions">
          <span className="rag-badge">
            <Database size={13} strokeWidth={1.9} /> {apiOnline ? t('assistant.ragOn') : t('assistant.ragOffline')}
          </span>
          {messages.length > 0 && (
            <button className="btn btn--ghost btn--sm" onClick={clear}><Trash2 size={15} /> {t('assistant.clear')}</button>
          )}
        </div>
      </div>

      <motion.div className="assistant-main" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="chat-stream">
          <ChatMessages messages={messages} loading={loading} />
          {messages.length === 0 && !loading && (
            <div className="assistant-suggest-grid">
              {suggestions.map((s) => (
                <button key={s} className="chat-suggest" onClick={() => send(t(s))}>
                  <Sparkles size={15} strokeWidth={1.9} />
                  {t(s)}
                  <ArrowRight size={14} strokeWidth={1.9} style={{ marginLeft: 'auto', opacity: 0.5 }} />
                </button>
              ))}
            </div>
          )}
        </div>
        <ChatComposer onSend={send} loading={loading} />
      </motion.div>
    </div>
  )
}
