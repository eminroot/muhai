import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowUp, ChevronRight, Maximize2, Plus, Send, Sparkles, X } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'

/**
 * The launcher and welcome panel on the marketing site.
 *
 * It is deliberately NOT the product assistant: signed out there is no
 * company, no ledger and no compute API to answer from, so pretending to
 * reason here would be a lie told in the product's own voice. It answers
 * from the same six questions the FAQ section holds, says plainly that it
 * is doing so, and hands off to the real assistant behind sign-in.
 */
export default function SiteChat() {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
  const [thread, setThread] = useState([])
  const [draft, setDraft] = useState('')
  const streamRef = useRef(null)

  const questions = [1, 2, 3].map((n) => ({ q: t(`landing.faq${n}Q`), a: t(`landing.faq${n}A`) }))

  useEffect(() => {
    const el = streamRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [thread, open])

  // Escape closes the panel, the way every other overlay in the app behaves.
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  function ask(item) {
    setThread((prev) => [...prev, { from: 'user', text: item.q }, { from: 'bot', text: item.a }])
  }

  function submit(e) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    setDraft('')
    setThread((prev) => [...prev, { from: 'user', text }, { from: 'bot', text: t('siteChat.typed'), handoff: true }])
  }

  function openFromPeek(e) {
    e.preventDefault()
    setOpen(true)
    if (draft.trim()) submit(e)
  }

  return (
    <>
      {/* ------------------------------------------------ launcher --
          A composer pill beside the orb, so the first message can be
          typed without opening anything. */}
      <AnimatePresence>
        {!open && (
          <motion.div
            className="sc-launch"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
          >
            <form className="sc-peek" onSubmit={openFromPeek}>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={t('siteChat.peek')}
                aria-label={t('siteChat.peek')}
              />
              <button type="submit" className="sc-peek__go" aria-label={t('siteChat.send')}>
                <ArrowUp size={15} strokeWidth={2.2} />
              </button>
            </form>

            <button className="sc-orb orb orb--wide" onClick={() => setOpen(true)} aria-label={t('siteChat.open')}>
              <span className="orb__skin"><span className="orb__field" /></span>
              <span className="orb__gloss" />
              <Sparkles size={19} strokeWidth={2} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* --------------------------------------------------- panel -- */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="sc-panel"
            initial={{ opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            role="dialog"
            aria-label={t('siteChat.name')}
          >
            <div className="sc-head">
              <button className="sc-head__icon" aria-label={t('siteChat.expand')} disabled>
                <Maximize2 size={15} strokeWidth={1.9} />
              </button>

              <span className="sc-badge">
                <span className="sc-badge__orb orb orb--close">
                  <span className="orb__skin"><span className="orb__field" /></span>
                  <span className="orb__gloss" />
                </span>
                {t('siteChat.name')}
                <i className="sc-badge__dot" />
              </span>

              <button className="sc-head__icon" onClick={() => setOpen(false)} aria-label={t('siteChat.close')}>
                <X size={15} strokeWidth={1.9} />
              </button>
            </div>

            <div className="sc-stream" ref={streamRef}>
              <div className="sc-day">{t('siteChat.today')}</div>

              <p className="sc-say">{t('siteChat.greeting')}</p>
              <p className="sc-say">{t('siteChat.pick')}</p>

              <div className="sc-choices">
                {questions.map((item) => (
                  <button key={item.q} className="sc-choice" onClick={() => ask(item)}>
                    {item.q}
                    <ChevronRight size={16} strokeWidth={1.9} />
                  </button>
                ))}
              </div>

              {thread.map((m, i) => (
                <div key={i} className={`sc-msg sc-msg--${m.from}`}>
                  <div className="sc-bubble">{m.text}</div>
                  {m.handoff && (
                    <div className="sc-handoff">
                      <Link to="/register" className="sc-handoff__go">{t('siteChat.askAssistant')}</Link>
                      <a href="mailto:destek@muhai.com">{t('siteChat.mailUs')}</a>
                    </div>
                  )}
                </div>
              ))}

              {thread.length === 0 && <p className="sc-note">{t('siteChat.note')}</p>}
            </div>

            <form className="sc-compose" onSubmit={submit}>
              <button type="button" className="sc-compose__plus" aria-label={t('siteChat.mailUs')} disabled>
                <Plus size={17} strokeWidth={1.9} />
              </button>
              <div className="sc-compose__field">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder={t('siteChat.placeholder')}
                  aria-label={t('siteChat.placeholder')}
                />
              </div>
              <button type="submit" className="sc-compose__send" aria-label={t('siteChat.send')} disabled={!draft.trim()}>
                <Send size={15} strokeWidth={1.9} />
              </button>
            </form>

            <div className="sc-foot">{t('siteChat.poweredBy')}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
