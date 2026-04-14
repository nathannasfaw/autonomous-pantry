import { useEffect, useRef, useState } from 'react'

const UserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
)

const GoogleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
)

const EyeIcon = ({ off }) => off ? (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
) : (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

export default function LoginModal() {
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [status, setStatus] = useState(null) // null | 'loading' | 'done'
  const overlayRef = useRef(null)

  // Close on overlay click
  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) setOpen(false)
  }

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  const handleSignIn = (e) => {
    e.preventDefault()
    setStatus('loading')
    setTimeout(() => setStatus('done'), 1200)
  }

  const handleClose = () => {
    setOpen(false)
    setStatus(null)
    setEmail('')
    setPassword('')
  }

  const inputStyle = {
    width: '100%',
    padding: '9px 12px',
    borderRadius: 8,
    border: '1px solid var(--input-border)',
    background: 'var(--bg-input)',
    color: 'var(--text-primary)',
    fontSize: 13,
    outline: 'none',
    transition: 'border-color 0.15s',
  }

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center justify-center rounded-lg transition-colors"
        style={{
          width: 32,
          height: 32,
          background: 'var(--icon-btn-bg)',
          color: 'var(--text-secondary)',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--icon-btn-hover)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'var(--icon-btn-bg)' }}
        title="Sign in"
      >
        <UserIcon />
      </button>

      {/* Modal */}
      {open && (
        <div
          ref={overlayRef}
          onClick={handleOverlayClick}
          className="fixed inset-0 flex items-center justify-center"
          style={{ background: 'var(--modal-overlay)', zIndex: 200 }}
        >
          <div
            className="rounded-2xl w-full max-w-sm mx-4 overflow-hidden"
            style={{
              background: 'var(--modal-bg)',
              border: '1px solid var(--modal-border)',
              boxShadow: 'var(--shadow-popover)',
            }}
          >
            {/* Header */}
            <div className="px-6 pt-6 pb-2 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Welcome back
                </h2>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  Sign in to your KitchenSync account
                </p>
              </div>
              <button
                onClick={handleClose}
                className="rounded-lg p-1 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-secondary)' }}
                onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-4">
              {status === 'done' ? (
                <div className="py-6 flex flex-col items-center gap-3 text-center">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{ background: 'rgba(74,154,154,0.15)' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4A9A9A" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    Login coming soon
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Authentication isn't wired up yet, but it'll look exactly like this.
                  </p>
                  <button
                    onClick={handleClose}
                    className="mt-2 text-xs px-4 py-2 rounded-lg"
                    style={{ background: 'var(--icon-btn-hover)', color: 'var(--text-secondary)' }}
                  >
                    Close
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSignIn} className="space-y-3">
                  {/* Google */}
                  <button
                    type="button"
                    className="w-full flex items-center justify-center gap-2.5 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{
                      border: '1px solid var(--input-border)',
                      background: 'var(--bg-input)',
                      color: 'var(--text-secondary)',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--input-focus-border)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--input-border)' }}
                  >
                    <GoogleIcon />
                    Continue with Google
                  </button>

                  {/* Divider */}
                  <div className="flex items-center gap-3 py-1">
                    <div className="flex-1 h-px" style={{ background: 'var(--input-border)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>or</span>
                    <div className="flex-1 h-px" style={{ background: 'var(--input-border)' }} />
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block text-xs mb-1.5 font-medium" style={{ color: 'var(--text-secondary)' }}>
                      Email
                    </label>
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      style={inputStyle}
                      onFocus={e => { e.target.style.borderColor = 'var(--input-focus-border)' }}
                      onBlur={e => { e.target.style.borderColor = 'var(--input-border)' }}
                    />
                  </div>

                  {/* Password */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                        Password
                      </label>
                      <button
                        type="button"
                        className="text-xs transition-colors"
                        style={{ color: '#5B8FCC' }}
                        onMouseEnter={e => { e.currentTarget.style.color = '#7aaee0' }}
                        onMouseLeave={e => { e.currentTarget.style.color = '#5B8FCC' }}
                      >
                        Forgot password?
                      </button>
                    </div>
                    <div className="relative">
                      <input
                        type={showPw ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        style={{ ...inputStyle, paddingRight: 36 }}
                        onFocus={e => { e.target.style.borderColor = 'var(--input-focus-border)' }}
                        onBlur={e => { e.target.style.borderColor = 'var(--input-border)' }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPw(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                        style={{ color: 'var(--text-muted)' }}
                        onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-secondary)' }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)' }}
                      >
                        <EyeIcon off={showPw} />
                      </button>
                    </div>
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity"
                    style={{
                      background: 'linear-gradient(135deg, #0061A0, #0D5E9D)',
                      opacity: status === 'loading' ? 0.7 : 1,
                    }}
                    disabled={status === 'loading'}
                  >
                    {status === 'loading' ? 'Signing in…' : 'Sign in'}
                  </button>

                  {/* Create account */}
                  <p className="text-center text-xs pt-1" style={{ color: 'var(--text-muted)' }}>
                    Don't have an account?{' '}
                    <button
                      type="button"
                      className="transition-colors"
                      style={{ color: '#5B8FCC' }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#7aaee0' }}
                      onMouseLeave={e => { e.currentTarget.style.color = '#5B8FCC' }}
                    >
                      Create one
                    </button>
                  </p>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
