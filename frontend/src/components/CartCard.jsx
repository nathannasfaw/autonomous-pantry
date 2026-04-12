const CartIcon = ({ size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
)

const EditIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
)

const GA_TAX_RATE = 0.04
const DELIVERY_FEE = 4.99

export default function CartCard({ cart, onBuy }) {
  if (!cart || cart.length === 0) return null
  const subtotal = cart.reduce((sum, item) => sum + (item.estimated_price || 0), 0)
  const tax = subtotal * GA_TAX_RATE
  const total = subtotal + tax + DELIVERY_FEE

  return (
    <div className="card-entrance rounded-2xl overflow-hidden w-full"
         style={{ boxShadow: 'var(--shadow-card)', border: '1px solid var(--sidebar-border)' }}>
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
          <div key={i} className="flex items-center justify-between py-2.5 last:border-0" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
            <div>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{item.item}</span>
              <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>{item.quantity} {item.unit}</span>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full"
              style={{ background: 'var(--price-badge-bg)', color: 'var(--price-badge-text)' }}>
              ${(item.estimated_price || 0).toFixed(2)}
            </span>
          </div>
        ))}

        {/* Subtotal */}
        <div className="flex items-center justify-between mt-2 pt-3" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Subtotal</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${subtotal.toFixed(2)}</span>
        </div>

        {/* Tax */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>GA Sales Tax (4%)</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${tax.toFixed(2)}</span>
        </div>

        {/* Delivery Fee */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Delivery Fee</span>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>${DELIVERY_FEE.toFixed(2)}</span>
        </div>

        {/* Total */}
        <div className="flex items-center justify-between mt-2 pt-3" style={{ borderTop: '2px solid var(--sidebar-border)' }}>
          <span className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Total</span>
          <span className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>${total.toFixed(2)}</span>
        </div>

        {/* Action buttons */}
        {onBuy && (
          <div className="mt-4 mb-2 flex gap-2">
            <button
              onClick={onBuy}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-white text-sm font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
              style={{ background: 'linear-gradient(135deg, #0061A0, #0D5E9D)' }}
            >
              <CartIcon size={14} />
              Place Order
            </button>
            <button
              className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{
                background: 'transparent',
                border: '1px solid var(--sidebar-border)',
                color: 'var(--text-secondary)',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              title="Modify your order"
            >
              <EditIcon />
              Edit
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
