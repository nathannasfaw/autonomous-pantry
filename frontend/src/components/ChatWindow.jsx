import { useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import InputBar from './InputBar'
import ClaudeLogo from './ClaudeLogo'

const BoltIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0061A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
)

const RefreshIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0061A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
)

const CompassIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0061A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
  </svg>
)

const GridIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0061A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
  </svg>
)

const SUGGESTIONS = [
  { label: 'Quick weeknight dinner', Icon: BoltIcon, desc: 'Something fast and easy after a long day' },
  { label: 'Use up expiring ingredients', Icon: RefreshIcon, desc: "Build a meal from what's already in the pantry" },
  { label: 'Try something new', Icon: CompassIcon, desc: "Surprise me with a cuisine I haven't tried" },
  { label: 'Meal prep for the week', Icon: GridIcon, desc: 'Batch-cook meals to save time all week' },
]

export default function ChatWindow({ messages, isLoading, sendMessage, conversationId, onItemsAdded }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const lastActiveBuyIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (m.role === 'assistant' && m.cart?.length > 0 &&
          m.stage !== 'confirmed' && m.stage !== 'cancelled') {
        return i
      }
    }
    return -1
  })()

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <div className="h-full flex flex-col relative">
      {/* Subtle top gradient overlay */}
      <div
        className="absolute top-0 left-0 right-0 pointer-events-none"
        style={{
          height: '45%',
          background: 'linear-gradient(180deg, rgba(0,97,160,0.32) 0%, rgba(13,94,157,0.18) 40%, rgba(0,97,160,0.06) 75%, transparent 100%)',
          zIndex: 1,
        }}
      />

      {isEmpty ? (
        /* ── Hero layout: everything grouped and centered on the page ── */
        <div className="flex-1 flex items-center justify-center relative px-6" style={{ zIndex: 2 }}>
          <div className="flex flex-col items-center text-center w-full max-w-3xl" style={{ marginTop: '-5vh' }}>
            {/* Logo */}
            <div className="mb-5 header-fade-in">
              <span className="text-4xl tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                <span style={{ color: '#FFFFFF', fontWeight: 400 }}>Kitchen</span><span style={{ color: '#0061A0', fontWeight: 700 }}>Sync</span><span style={{ color: '#FFFFFF', fontWeight: 400 }}>.</span>
              </span>
            </div>

            {/* Greeting */}
            <h2 className="text-2xl font-semibold mb-1 tracking-tight header-fade-in" style={{ color: 'var(--text-primary)', animationDelay: '0.08s' }}>
              Hope the day's treating you well
            </h2>
            <p className="text-sm mb-8 header-fade-in" style={{ color: 'var(--text-muted)', animationDelay: '0.16s' }}>What would you like to cook today?</p>

            {/* Suggestion cards */}
            <div className="grid grid-cols-2 gap-3 w-full max-w-lg header-fade-in" style={{ animationDelay: '0.22s' }}>
              {SUGGESTIONS.map(({ label, Icon, desc }) => (
                <button
                  key={label}
                  onClick={() => sendMessage(label)}
                  className="suggestion-card flex flex-col items-center text-center rounded-xl px-4 py-4 transition-all"
                  style={{
                    border: '1px solid #2A2B30',
                    color: 'var(--text-primary)',
                    background: 'rgba(30, 31, 35, 0.6)',
                    minHeight: '120px',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(0, 97, 160, 0.12)'
                    e.currentTarget.style.borderColor = 'rgba(0, 97, 160, 0.4)'
                    e.currentTarget.style.transform = 'translateY(-2px)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(30, 31, 35, 0.6)'
                    e.currentTarget.style.borderColor = '#2A2B30'
                    e.currentTarget.style.transform = 'translateY(0)'
                  }}
                >
                  <div className="mb-2.5"><Icon /></div>
                  <div className="text-sm font-semibold">{label}</div>
                  <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{desc}</div>
                </button>
              ))}
            </div>

            {/* Input bar — directly below cards */}
            <div className="w-full mt-8 header-fade-in" style={{ animationDelay: '0.28s' }}>
              <InputBar onSend={sendMessage} isLoading={isLoading} conversationId={conversationId} onItemsAdded={onItemsAdded} />
            </div>
          </div>
        </div>
      ) : (
        /* ── Active chat layout ── */
        <>
          <div className="flex-1 overflow-y-auto pt-8 pb-6 px-6 relative" style={{ zIndex: 2 }}>
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  message={msg}
                  onBuy={i === lastActiveBuyIndex ? () => sendMessage('confirm') : undefined}
                />
              ))}
              {isLoading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          </div>
          <InputBar onSend={sendMessage} isLoading={isLoading} conversationId={conversationId} onItemsAdded={onItemsAdded} />
        </>
      )}
    </div>
  )
}
