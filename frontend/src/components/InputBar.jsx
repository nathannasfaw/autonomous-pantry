import { useState, useRef, useEffect } from 'react'

const SendIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L12 22M12 2L6 8M12 2L18 8" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

const DiceIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="3"/>
    <circle cx="8.5" cy="8.5" r="1" fill="currentColor" stroke="none"/>
    <circle cx="15.5" cy="8.5" r="1" fill="currentColor" stroke="none"/>
    <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>
    <circle cx="8.5" cy="15.5" r="1" fill="currentColor" stroke="none"/>
    <circle cx="15.5" cy="15.5" r="1" fill="currentColor" stroke="none"/>
  </svg>
)

export default function InputBar({ onSend, isLoading }) {
  const [value, setValue] = useState('')
  const [popping, setPopping] = useState(false)
  const textareaRef = useRef(null)

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    setPopping(true)
    setTimeout(() => setPopping(false), 200)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const canSend = value.trim().length > 0 && !isLoading

  return (
    <div className="absolute bottom-0 left-0 right-0 px-6 pb-6 pt-3"
      style={{ background: 'linear-gradient(to top, #313338 80%, transparent)', zIndex: 10 }}>
      <div className="max-w-4xl mx-auto">
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: '#3F4147',
            border: '1px solid #4F5159',
            boxShadow: 'var(--shadow-input)',
          }}
        >
          {/* Text area */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="How can I help you today?"
            disabled={isLoading}
            className="w-full resize-none outline-none text-sm bg-transparent px-4 pt-3.5 pb-2 disabled:opacity-50"
            style={{ maxHeight: 160, color: 'var(--text-primary)', caretColor: '#0061A0' }}
          />

          {/* Bottom toolbar */}
          <div className="flex items-center justify-between px-3 pb-3">
            <div className="flex items-center gap-2">
              <span
                className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium select-none"
                style={{ background: '#2B2D31', color: 'var(--text-secondary)' }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                Haiku 4.5
              </span>
            </div>
            <button
              onClick={submit}
              disabled={!canSend}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0 transition-all
                ${popping ? 'button-pop' : ''}
              `}
              style={{
                background: canSend
                  ? 'linear-gradient(135deg, #0061A0, #0D5E9D)'
                  : '#4F5159',
                cursor: canSend ? 'pointer' : 'not-allowed',
              }}
            >
              <SendIcon />
            </button>
          </div>
        </div>
        <p className="text-center text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          Press <kbd className="px-1 py-0.5 rounded font-mono text-[10px]" style={{ background: '#3F4147', color: 'var(--text-secondary)' }}>Enter</kbd> to send · <kbd className="px-1 py-0.5 rounded font-mono text-[10px]" style={{ background: '#3F4147', color: 'var(--text-secondary)' }}>Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  )
}
