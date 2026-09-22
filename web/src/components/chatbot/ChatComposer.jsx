import { useState, useRef } from 'react'
import { ArrowUp } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'

export default function ChatComposer({ onSend, loading, showDisclaimer = true }) {
  const { t } = useLang()
  const [value, setValue] = useState('')
  const taRef = useRef(null)

  const submit = () => {
    if (!value.trim() || loading) return
    onSend(value)
    setValue('')
    if (taRef.current) taRef.current.style.height = 'auto'
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onInput = (e) => {
    setValue(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 96) + 'px'
  }

  return (
    <div className="chat-composer">
      <div className="chat-input-row">
        <textarea
          ref={taRef}
          rows={1}
          value={value}
          onChange={onInput}
          onKeyDown={onKey}
          placeholder={t('assistant.placeholder')}
          aria-label={t('assistant.placeholder')}
        />
        <button className="chat-send" onClick={submit} disabled={!value.trim() || loading} aria-label={t('assistant.send')}>
          <ArrowUp size={18} strokeWidth={1.9} />
        </button>
      </div>
      {showDisclaimer && <p className="chat-disclaimer">{t('assistant.disclaimer')}</p>}
    </div>
  )
}
