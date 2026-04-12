import { useState, useRef, useEffect } from 'react'
import CameraModal from './CameraModal'

const SendIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L12 22M12 2L6 8M12 2L18 8" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

const CameraIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
)

const PaperclipIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
  </svg>
)

export default function InputBar({ onSend, isLoading, conversationId, onItemsAdded }) {
  const [value, setValue] = useState('')
  const [popping, setPopping] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
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

  const handleItemsAdded = (items) => {
    onItemsAdded?.(items)
  }

  const canSend = value.trim().length > 0 && !isLoading

  return (
    <>
      {/* Fade gradient above input area */}
      <div
        className="pointer-events-none flex-shrink-0"
        style={{
          height: 40,
          marginBottom: -40,
          position: 'relative',
          zIndex: 3,
          background: 'linear-gradient(0deg, var(--bg-page) 0%, transparent 100%)',
        }}
      />

      <div className="px-6 pb-5 pt-4 flex-shrink-0 relative" style={{ zIndex: 4, background: 'var(--bg-page)' }}>
        <div className="max-w-3xl mx-auto">
          <div
            className="rounded-2xl overflow-hidden"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--sidebar-border)',
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
              {/* Left: action buttons */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCameraOpen(true)}
                  disabled={isLoading}
                  title="Scan pantry with camera"
                  className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ color: 'var(--text-muted)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <CameraIcon />
                  Scan
                </button>
              </div>

              {/* Right: send button */}
              <button
                onClick={submit}
                disabled={!canSend}
                className={`w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0 transition-all
                  ${popping ? 'button-pop' : ''}
                `}
                style={{
                  background: canSend
                    ? 'linear-gradient(135deg, #0061A0, #0D5E9D)'
                    : 'var(--sidebar-border)',
                  cursor: canSend ? 'pointer' : 'not-allowed',
                }}
              >
                <SendIcon />
              </button>
            </div>
          </div>

          {/* Footer: model badge + hints */}
          <div className="flex items-center justify-between mt-2 px-1">
            <span
              className="inline-flex items-center gap-1.5 text-[11px] font-medium select-none"
              style={{ color: 'var(--text-muted)' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              Haiku 4.5
            </span>
            <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              <kbd className="px-1 py-0.5 rounded font-mono text-[10px]" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>Enter</kbd> to send
              {' '}&middot;{' '}
              <kbd className="px-1 py-0.5 rounded font-mono text-[10px]" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>Shift+Enter</kbd> new line
            </p>
          </div>
        </div>
      </div>

      {cameraOpen && (
        <CameraModal
          conversationId={conversationId}
          onClose={() => setCameraOpen(false)}
          onItemsAdded={handleItemsAdded}
        />
      )}
    </>
  )
}
