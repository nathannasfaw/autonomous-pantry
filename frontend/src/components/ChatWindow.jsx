import { useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import InputBar from './InputBar'
import chefLogo from '../assets/logo.png'

const SUGGESTIONS = ['Sushi', 'Pizza', 'Tacos', 'Pasta', 'Ramen']

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
          background: 'linear-gradient(180deg, rgba(0,97,160,0.18) 0%, rgba(13,94,157,0.10) 50%, transparent 100%)',
          zIndex: 1,
        }}
      />
      <div className="flex-1 overflow-y-auto pt-8 pb-6 px-6 relative" style={{ zIndex: 2 }}>
        <div className="max-w-4xl mx-auto space-y-5">

          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[65vh] text-center">
              <div className="mb-6">
                <img src={chefLogo} alt="Autonomous Pantry" className="w-16 h-16" />
              </div>
              <h2 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: 'var(--text-primary)' }}>
                Hope the day's treating you well
              </h2>
              <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>What would you like to cook today?</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {SUGGESTIONS.map((label) => (
                  <button
                    key={label}
                    onClick={() => sendMessage(`I want to make ${label.toLowerCase()}`)}
                    className="rounded-full text-sm px-4 py-1.5 transition-colors"
                    style={{
                      border: '1px solid #3F4147',
                      color: 'var(--text-secondary)',
                      background: 'transparent',
                    }}
                    onMouseEnter={e => { e.target.style.background = '#3F4147'; e.target.style.borderColor = '#4F5159'; }}
                    onMouseLeave={e => { e.target.style.background = 'transparent'; e.target.style.borderColor = '#3F4147'; }}
                  >
                    {label}
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
