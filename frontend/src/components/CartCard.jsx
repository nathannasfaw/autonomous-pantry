const CartIcon = ({ size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
)

export default function CartCard({ cart, onBuy }) {
  if (!cart || cart.length === 0) return null
  const total = cart.reduce((sum, item) => sum + (item.estimated_price || 0), 0)

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
        {cart.map((item, i) => (
          <div key={i} className="flex items-center justify-between py-2.5 last:border-0" style={{ borderBottom: '1px solid #3F4147' }}>
            <div>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{item.item}</span>
              <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>{item.quantity} {item.unit}</span>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full" style={{ background: '#1a3a2a', color: '#4ade80' }}>
              ${(item.estimated_price || 0).toFixed(2)}
            </span>
          </div>
        ))}

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
