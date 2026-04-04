import { useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import InputBar from './InputBar'

const AsteriskLogo = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round">
    <line x1="12" y1="2" x2="12" y2="22"/>
    <line x1="2" y1="12" x2="22" y2="12"/>
    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
    <line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/>
  </svg>
)

const SUGGESTIONS = ['Sushi', 'Pizza', 'Tacos', 'Pasta', 'Ramen']

export default function ChatWindow() {
  const { messages, isLoading, sendMessage } = useChat()
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
      <div className="flex-1 overflow-y-auto pt-8 pb-36 px-6">
        <div className="max-w-2xl mx-auto space-y-5">

          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[65vh] text-center">
              <div className="text-zinc-300 mb-6">
                <AsteriskLogo />
              </div>
              <h2 className="text-2xl font-semibold text-zinc-900 mb-1 tracking-tight">
                Hope the day's treating you well
              </h2>
              <p className="text-sm text-zinc-400 mb-8">What would you like to cook today?</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {SUGGESTIONS.map((label) => (
                  <button
                    key={label}
                    onClick={() => sendMessage(`I want to make ${label.toLowerCase()}`)}
                    className="rounded-full border border-zinc-200 text-zinc-600 text-sm px-4 py-1.5 hover:bg-zinc-100 hover:border-zinc-300 transition-colors"
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

      <InputBar onSend={sendMessage} isLoading={isLoading} />
    </div>
  )
}
