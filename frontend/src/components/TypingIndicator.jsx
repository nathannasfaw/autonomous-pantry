import chefLogo from '../assets/logo.png'

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <img src={chefLogo} alt="Chef" className="w-8 h-8 rounded-xl flex-shrink-0 object-cover" />
      <div
        className="flex items-center gap-1.5 px-4 py-3 rounded-2xl rounded-tl-sm"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--sidebar-border)' }}
      >
        {[0, 1, 2].map(i => (
          <div
            key={i}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: 'var(--text-muted)',
              animation: 'typingBounce 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
