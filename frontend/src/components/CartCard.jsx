const CartIcon = ({ size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
)

const CheckCircleIcon = ({ size = 14, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
    <polyline points="22 4 12 14.01 9 11.01"/>
  </svg>
)

const STORE_COLORS = {
  publix: { bg: '#1a2e1a', color: '#4ade80', label: 'Publix' },
  kroger: { bg: '#1a1a2e', color: '#60a5fa', label: 'Kroger' },
  both: { bg: '#2a2a1a', color: '#a3a3a3', label: '' },
}

const GA_TAX_RATE = 0.04
const DELIVERY_FEE = 7.99

export default function CartCard({ cart, pantryUsed, onBuy }) {
  if (!cart || cart.length === 0) return null
  const subtotal = cart.reduce((sum, item) => sum + (item.estimated_price || 0), 0)
  const tax = subtotal * GA_TAX_RATE
  const total = subtotal + tax + DELIVERY_FEE

  return (
    <div className="card-entrance rounded-2xl overflow-hidden w-full"
         style={{ boxShadow: 'var(--shadow-card)', border: '1px solid #3F4147' }}>
      {/* Gradient header */}
      <div className="px-4 py-3 flex items-center gap-2" style={{ background: 'var(--card-cart-header)' }}>
        <CartIcon size={15} className="text-white opacity-90" />
        <div>
          <div className="text-white font-semibold text-sm">Your Order</div>
          <div className="text-white/70 text-xs">{cart.length} items</div>
        </div>
      </div>

      {/* Items */}
      <div className="px-4 py-2" style={{ background: 'var(--bg-card)' }}>
        {cart.map((item, i) => {
          const storeInfo = STORE_COLORS[item.store] || STORE_COLORS.both
          return (
            <div key={i} className="flex items-center justify-between py-2.5 last:border-0" style={{ borderBottom: '1px solid #3F4147' }}>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  {item.brand
                    ? <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{item.brand}</span>
                    : <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{item.item}</span>
                  }
                  {storeInfo.label && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                          style={{ background: storeInfo.bg, color: storeInfo.color }}>
                      {storeInfo.label}
                    </span>
                  )}
                </div>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{item.quantity} {item.unit}</span>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full" style={{ background: '#1a3a2a', color: '#4ade80' }}>
                ${(item.estimated_price || 0).toFixed(2)}
              </span>
            </div>
          )
        })}

        {/* Pantry items used */}
        {pantryUsed && pantryUsed.length > 0 && (
          <>
            <div className="flex items-center gap-2 mt-3 mb-1">
              <CheckCircleIcon size={13} className="opacity-60" style={{ color: '#4ade80' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>From Your Pantry</span>
            </div>
            {pantryUsed.map((item, i) => (
              <div key={`pantry-${i}`} className="flex items-center justify-between py-1.5">
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {item.item}
                  <span className="ml-2 opacity-60">{item.quantity} {item.unit}</span>
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: '#1a3a2a', color: '#4ade80', opacity: 0.7 }}>
                  on hand
                </span>
              </div>
            ))}
          </>
        )}

        {/* Subtotal */}
        <div className="flex items-center justify-between mt-2 pt-3" style={{ borderTop: '1px solid #4F5159' }}>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Subtotal</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${subtotal.toFixed(2)}</span>
        </div>

        {/* Tax */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>GA State Tax (4%)</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${tax.toFixed(2)}</span>
        </div>

        {/* Delivery Fee */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Delivery Fee</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${DELIVERY_FEE.toFixed(2)}</span>
        </div>

        {/* Total */}
        <div className="flex items-center justify-between mt-2 pt-3" style={{ borderTop: '2px solid #4F5159' }}>
          <span className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Total</span>
          <span className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>${total.toFixed(2)}</span>
        </div>

        {/* Buy button */}
        {onBuy && (
          <button
            onClick={onBuy}
            className="mt-3 mb-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-white text-sm font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
            style={{ background: 'linear-gradient(135deg, #0061A0, #0D5E9D)' }}
          >
            <CartIcon size={14} />
            Place Order
          </button>
        )}
      </div>
    </div>
  )
}
