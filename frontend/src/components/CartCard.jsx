const CartIcon = ({ size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
)

export default function CartCard({ cart, onBuy }) {
  if (!cart || cart.length === 0) return null
  const total = cart.reduce((sum, item) => sum + (item.estimated_price || 0) * (item.quantity || 1), 0)

  return (
    <div className="card-entrance rounded-2xl overflow-hidden border border-gray-100 w-full max-w-sm"
         style={{ boxShadow: 'var(--shadow-card)' }}>
      {/* Gradient header */}
      <div className="px-4 py-3 flex items-center gap-2" style={{ background: 'var(--card-cart-header)' }}>
        <CartIcon size={15} className="text-white opacity-90" />
        <div>
          <div className="text-white font-semibold text-sm">Your Order</div>
          <div className="text-white/70 text-xs">{cart.length} items</div>
        </div>
      </div>

      {/* Items */}
      <div className="bg-white px-4 py-2">
        {cart.map((item, i) => (
          <div key={i} className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
            <div>
              <span className="text-sm font-medium text-gray-800">{item.item}</span>
              <span className="text-xs text-gray-400 ml-2">{item.quantity} {item.unit}</span>
            </div>
            <span className="text-xs font-semibold bg-green-50 text-green-700 px-2.5 py-1 rounded-full">
              ${(item.estimated_price || 0).toFixed(2)}
            </span>
          </div>
        ))}

        {/* Total */}
        <div className="flex items-center justify-between mt-2 pt-3 border-t-2 border-gray-100">
          <span className="text-sm font-semibold text-gray-700">Total</span>
          <span className="text-base font-bold text-gray-900">${total.toFixed(2)}</span>
        </div>

        {/* Buy button */}
        {onBuy && (
          <button
            onClick={onBuy}
            className="mt-3 mb-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-white text-sm font-semibold transition-all hover:bg-zinc-700 active:scale-[0.98] bg-zinc-900"
          >
            <CartIcon size={14} />
            Place Order
          </button>
        )}
      </div>
    </div>
  )
}
