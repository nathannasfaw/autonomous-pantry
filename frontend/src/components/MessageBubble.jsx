import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import RecipeCard from './RecipeCard'
import CartCard from './CartCard'
import chefLogo from '../assets/logo.png'

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
    <img
      src={chefLogo}
      alt="Chef"
      className={`w-8 h-8 rounded-xl flex-shrink-0 object-cover ${ping ? 'avatar-ping' : ''}`}
    />
  )
}

function OrderConfirmationCard({ orderDetails }) {
  return (
    <div className="card-entrance success-pulse rounded-2xl overflow-hidden w-full max-w-sm"
         style={{ boxShadow: 'var(--shadow-card)', border: '1px solid #3F4147' }}>
      <div className="px-4 py-3 flex items-center gap-2" style={{ background: 'var(--card-success-header)' }}>
        <CheckIcon size={15} className="text-white" />
        <div>
          <div className="text-white font-semibold text-sm">Order Placed!</div>
          <div className="text-white/70 text-xs mt-0.5">
            Estimated delivery: {orderDetails?.estimated_delivery || '45–60 min'}
          </div>
        </div>
      </div>
      <div className="px-4 py-3 space-y-1.5" style={{ background: 'var(--bg-card)' }}>
        <div className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>{orderDetails?.order_id}</div>
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{orderDetails?.retailer}</div>
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-muted)' }}>
          <div className="flex justify-between">
            <span>{orderDetails?.items?.length} items</span>
            <span>${(orderDetails?.subtotal || 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span>{orderDetails?.tax_label || 'Tax'}</span>
            <span>${(orderDetails?.tax || 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span>Delivery</span>
            <span>${(orderDetails?.delivery_fee || 0).toFixed(2)}</span>
          </div>
        </div>
        <div className="flex justify-between text-sm font-semibold pt-1" style={{ color: 'var(--text-primary)', borderTop: '1px solid #3F4147' }}>
          <span>Total</span>
          <span>${(orderDetails?.total || 0).toFixed(2)}</span>
        </div>
      </div>
    </div>
  )
}

function TextBubble({ text }) {
  return (
    <div
      className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed border"
      style={{
        background: 'var(--agent-bubble-bg)',
        borderColor: 'var(--agent-bubble-border)',
        color: 'var(--text-primary)',
      }}
    >
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold" style={{ color: '#ffffff' }}>{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-4 space-y-1 mt-1 mb-2">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-4 space-y-1 mt-1 mb-2">{children}</ol>
          ),
          li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
          h3: ({ children }) => (
            <h3 className="font-semibold text-sm mt-2 mb-1" style={{ color: '#ffffff' }}>{children}</h3>
          ),
          code: ({ children }) => (
            <code className="px-1 py-0.5 rounded text-xs font-mono" style={{ background: '#2B2D31', color: '#7EB8DA' }}>{children}</code>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

export default function MessageBubble({ message, onBuy }) {
  const { role, text, recipe, cart, pantryUsed, orderConfirmed, orderDetails } = message
  const hasCards = (recipe || (cart && cart.length > 0))

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
      <div className="flex flex-col gap-3 min-w-0" style={{ maxWidth: hasCards ? '95%' : '85%' }}>
        {/* Text message at top */}
        {text && <TextBubble text={text} />}

        {/* Order confirmation */}
        {orderConfirmed && orderDetails && (
          <OrderConfirmationCard orderDetails={orderDetails} />
        )}

        {/* Side-by-side: Cart (left) + Recipe (right) */}
        {hasCards && (
          <div className="card-entrance flex gap-3 flex-wrap lg:flex-nowrap">
            {cart && cart.length > 0 && (
              <div className="flex-1 min-w-[240px]">
                <CartCard cart={cart} pantryUsed={pantryUsed} onBuy={onBuy} />
              </div>
            )}
            {recipe && (
              <div className="flex-1 min-w-[240px]">
                <RecipeCard recipe={recipe} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
