import ClaudeLogo from './ClaudeLogo'

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <ClaudeLogo size={32} className="flex-shrink-0" />
      <div
        className="flex items-center gap-1.5 px-4 py-3 rounded-2xl rounded-tl-sm"
        style={{ background: '#1E1F23', border: '1px solid #2A2B30' }}
      >
        {[0, 1, 2].map(i => (
          <div
            key={i}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: '#72767D',
              animation: 'typingBounce 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.18}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
