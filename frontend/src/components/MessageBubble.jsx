import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import RecipeCard from './RecipeCard'
import CartCard from './CartCard'

const AsteriskIcon = ({ size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.2" strokeLinecap="round" className={className}>
    <line x1="12" y1="2" x2="12" y2="22"/>
    <line x1="2" y1="12" x2="22" y2="12"/>
    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
    <line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/>
  </svg>
)

const CheckIcon = ({ size = 14, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
    <polyline points="22 4 12 14.01 9 11.01"/>
  </svg>
)

function AgentAvatar() {
  const [ping, setPing] = useState(false)
  useEffect(() => {
    setPing(true)
    const t = setTimeout(() => setPing(false), 600)
    return () => clearTimeout(t)
  }, [])

  return (
    <div
      className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-zinc-900 ${ping ? 'avatar-ping' : ''}`}
    >
      <AsteriskIcon size={14} className="text-white" />
    </div>
  )
}

function OrderConfirmationCard({ orderDetails }) {
  return (
    <div className="card-entrance success-pulse rounded-2xl overflow-hidden border border-zinc-200 w-full max-w-sm"
         style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="px-4 py-3 flex items-center gap-2" style={{ background: 'var(--card-success-header)' }}>
        <CheckIcon size={15} className="text-white" />
        <div>
          <div className="text-white font-semibold text-sm">Order Placed!</div>
          <div className="text-white/70 text-xs mt-0.5">
            Estimated delivery: {orderDetails?.estimated_delivery || '45–60 min'}
          </div>
        </div>
      </div>
      <div className="bg-white px-4 py-3 space-y-1">
        <div className="font-mono text-sm text-zinc-600">{orderDetails?.order_id}</div>
        <div className="text-xs text-zinc-400">{orderDetails?.retailer}</div>
        <div className="text-sm text-zinc-700">
          {orderDetails?.items?.length} items · ${(orderDetails?.total || 0).toFixed(2)} total
        </div>
      </div>
    </div>
  )
}

export default function MessageBubble({ message, onBuy }) {
  const { role, text, recipe, cart, orderConfirmed, orderDetails } = message

  if (role === 'user') {
    return (
      <div className="bubble-user flex justify-end">
        <div
          className="max-w-[75%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-white text-sm leading-relaxed"
          style={{ background: 'var(--user-bubble-bg)' }}
        >
          <p className="whitespace-pre-wrap">{text}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bubble-agent flex items-start gap-3">
      <AgentAvatar />
      <div className="flex flex-col gap-3 max-w-[85%]">
        {text && (
          <div
            className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-zinc-800 leading-relaxed border"
            style={{
              background: 'var(--agent-bubble-bg)',
              borderColor: 'var(--agent-bubble-border)',
            }}
          >
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-zinc-900">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-4 space-y-1 mt-1 mb-2">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-4 space-y-1 mt-1 mb-2">{children}</ol>
                ),
                li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
                h3: ({ children }) => (
                  <h3 className="font-semibold text-zinc-900 text-sm mt-2 mb-1">{children}</h3>
                ),
                code: ({ children }) => (
                  <code className="bg-zinc-100 text-zinc-700 px-1 py-0.5 rounded text-xs font-mono">{children}</code>
                ),
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        )}
        {orderConfirmed && orderDetails && (
          <OrderConfirmationCard orderDetails={orderDetails} />
        )}
        {recipe && <RecipeCard recipe={recipe} />}
        {cart && cart.length > 0 && (
          <CartCard cart={cart} onBuy={onBuy} />
        )}
      </div>
    </div>
  )
}
