import { useState, useRef, useEffect } from 'react'

const SendIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L12 22M12 2L6 8M12 2L18 8" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round" fill="none"/>
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
      style={{ background: 'linear-gradient(to top, var(--bg-page) 80%, transparent)' }}>
      <div className="max-w-2xl mx-auto">
        <div
          className="rounded-2xl border border-zinc-200 bg-white overflow-hidden"
          style={{ boxShadow: 'var(--shadow-input)' }}
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
            className="w-full resize-none outline-none text-sm text-zinc-800 placeholder-zinc-400 bg-transparent px-4 pt-3.5 pb-2 disabled:opacity-50"
            style={{ maxHeight: 160 }}
          />

          {/* Bottom toolbar */}
          <div className="flex items-center justify-between px-3 pb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-600 font-medium select-none">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                Haiku 4.5
              </span>
            </div>
            <button
              onClick={submit}
              disabled={!canSend}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0 transition-all
                ${canSend ? 'bg-zinc-900 hover:bg-zinc-700' : 'bg-zinc-200 cursor-not-allowed'}
                ${popping ? 'button-pop' : ''}
              `}
            >
              <SendIcon />
            </button>
          </div>
        </div>
        <p className="text-center text-xs text-zinc-400 mt-2">
          Press <kbd className="px-1 py-0.5 rounded text-zinc-500 bg-zinc-100 font-mono text-[10px]">Enter</kbd> to send · <kbd className="px-1 py-0.5 rounded text-zinc-500 bg-zinc-100 font-mono text-[10px]">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  )
}
