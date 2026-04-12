import { useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import InputBar from './InputBar'


const SUGGESTIONS = [
  {
    icon: '🍳',
    title: 'Quick weeknight dinner',
    desc: 'Something fast and easy after a long day',
    prompt: 'Suggest a quick weeknight dinner I can make in under 30 minutes',
  },
  {
    icon: '🧊',
    title: 'Use up expiring ingredients',
    desc: 'Build a meal from what\'s already in the pantry',
    prompt: 'What can I make with the ingredients currently in my pantry?',
  },
  {
    icon: '🌮',
    title: 'Try something new',
    desc: 'Surprise me with a cuisine I haven\'t tried',
    prompt: 'Suggest something adventurous and new for me to cook tonight',
  },
  {
    icon: '📦',
    title: 'Meal prep for the week',
    desc: 'Batch-cook meals to save time all week',
    prompt: 'Help me plan a meal prep session for the week with 3-4 dishes',
  },
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

  return (
    <div className="h-full flex flex-col relative">
      {/* Subtle top gradient overlay */}
      <div
        className="absolute top-0 left-0 right-0 pointer-events-none"
        style={{
          height: '30%',
          background: 'linear-gradient(180deg, rgba(0,97,160,0.22) 0%, rgba(13,94,157,0.12) 50%, transparent 100%)',
          zIndex: 1,
        }}
      />
      <div className="flex-1 overflow-y-auto pt-8 pb-6 px-6 relative" style={{ zIndex: 2 }}>
        <div className="max-w-3xl mx-auto space-y-5">

          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[65vh] text-center">
              <div className="mb-6 welcome-float welcome-float-1">
                <span style={{ fontFamily: "'Playfair Display', serif", fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1 }}>
                  <span style={{ color: 'var(--text-primary)' }}>Kitchen</span>
                  <span style={{ color: '#0061A0', fontWeight: 800 }}>Sync</span>
                  <span style={{ color: 'var(--text-primary)' }}>.</span>
                </span>
              </div>
              <h2 className="text-2xl font-semibold mb-1 tracking-tight welcome-float welcome-float-2" style={{ color: 'var(--text-primary)' }}>
                Hope the day's treating you well
              </h2>
              <p className="text-sm mb-8 welcome-float welcome-float-3" style={{ color: 'var(--text-muted)' }}>What would you like to cook today?</p>
              <div className="grid grid-cols-2 gap-3 w-full max-w-lg welcome-float welcome-float-4">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.title}
                    onClick={() => sendMessage(s.prompt)}
                    className="group text-left p-4 rounded-xl transition-all duration-200"
                    style={{
                      border: '1px solid var(--sidebar-border)',
                      background: 'var(--bg-card)',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = '#0061A0'
                      e.currentTarget.style.background = 'var(--bg-hover)'
                      e.currentTarget.style.transform = 'translateY(-2px)'
                      e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,97,160,0.15)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--sidebar-border)'
                      e.currentTarget.style.background = 'var(--bg-card)'
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <span className="text-xl mb-2 block">{s.icon}</span>
                    <span className="text-sm font-medium block mb-1" style={{ color: 'var(--text-primary)' }}>{s.title}</span>
                    <span className="text-xs leading-relaxed block" style={{ color: 'var(--text-muted)' }}>{s.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <MessageBubble
                key={i}
                message={msg}
                onBuy={i === lastActiveBuyIndex ? () => sendMessage('confirm') : undefined}
              />
            ))
          )}

          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </div>

      <InputBar onSend={sendMessage} isLoading={isLoading} conversationId={conversationId} onItemsAdded={onItemsAdded} />
    </div>
  )
}
