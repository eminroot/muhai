import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, FileText, WifiOff } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'

/* Render **bold** inline, leaving the rest as text. */
function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>,
  )
}

/* Turn plain assistant text into paragraphs + bullet lists. */
function FormattedText({ text }) {
  const lines = text.split('\n')
  const blocks = []
  let list = null

  const flush = () => {
    if (list) {
      blocks.push(
        <ul key={`ul-${blocks.length}`}>
          {list.map((li, i) => (
            <li key={i}>{renderInline(li)}</li>
          ))}
        </ul>,
      )
      list = null
    }
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      flush()
      continue
    }
    if (/^[-*•]\s+/.test(line)) {
      if (!list) list = []
      list.push(line.replace(/^[-*•]\s+/, ''))
    } else {
      flush()
      blocks.push(<p key={`p-${blocks.length}`}>{renderInline(line)}</p>)
    }
  }
  flush()
  return <>{blocks}</>
}

export default function ChatMessages({ messages, loading, welcome }) {
  const { t, lang } = useLang()
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  return (
    <>
      {/* welcome message always first */}
      <div className="msg msg--bot">
        <span className="msg__av msg__av--bot">
          <Sparkles size={15} strokeWidth={1.9} />
        </span>
        <div className="msg__bubble">{welcome || t('assistant.welcome')}</div>
      </div>

      {messages.map((m, i) => (
        <motion.div
          key={i}
          className={`msg msg--${m.role === 'user' ? 'user' : 'bot'}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <span className={`msg__av msg__av--${m.role === 'user' ? 'user' : 'bot'}`}>
            {m.role === 'user' ? 'EB' : <Sparkles size={15} strokeWidth={1.9} />}
          </span>
          <div className="msg__bubble">
            <FormattedText text={m.text} />
            {m.source === 'offline' && (
              <div className="msg__offline">
                <WifiOff size={10} strokeWidth={1.9} />
                {t('assistant.offlineBadge')}
              </div>
            )}
            {m.sources?.length > 0 && (
              <div className="msg__sources">
                <span className="msg__sources-label">{t('assistant.sources')}</span>
                {m.sources.map((s) => (
                  <span key={s.id} className="msg__source">
                    <FileText size={10} style={{ marginRight: 3, verticalAlign: '-1px' }} />
                    {s.title}
                  </span>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      ))}

      {loading && (
        <div className="msg msg--bot">
          <span className="msg__av msg__av--bot">
            <Sparkles size={15} strokeWidth={1.9} />
          </span>
          <div className="msg__bubble" style={{ display: 'flex', alignItems: 'center' }}>
            <span className="typing">
              <span />
              <span />
              <span />
            </span>
            <span className="typing-hint">{t('assistant.retrieving')}</span>
          </div>
        </div>
      )}
      <div ref={endRef} />
    </>
  )
}
