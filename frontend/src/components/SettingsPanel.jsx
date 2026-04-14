import { useEffect, useRef, useState } from 'react'
import { useTheme } from '../context/ThemeContext'

const GearIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

const SunIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)

const MoonIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)

export default function SettingsPanel() {
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Close when clicking outside
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const isDark = theme === 'dark'

  return (
    <div ref={ref} className="relative">
      {/* Popover */}
      {open && (
        <div
          className="absolute bottom-10 left-0 w-56 rounded-xl overflow-hidden"
          style={{
            background: 'var(--bg-popover)',
            border: '1px solid var(--modal-border)',
            boxShadow: 'var(--shadow-popover)',
            zIndex: 100,
          }}
        >
          {/* Header */}
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--modal-border)' }}>
            <p className="text-xs font-semibold tracking-wider uppercase" style={{ color: 'var(--text-muted)' }}>
              Settings
            </p>
          </div>

          {/* Theme row */}
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span style={{ color: 'var(--text-muted)' }}>
                {isDark ? <MoonIcon /> : <SunIcon />}
              </span>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {isDark ? 'Dark mode' : 'Light mode'}
              </span>
            </div>
            {/* Toggle switch */}
            <button
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              className="relative flex-shrink-0 rounded-full transition-colors duration-200"
              style={{
                width: 36,
                height: 20,
                background: isDark ? '#5B8FCC' : '#C9CBCE',
              }}
              aria-label="Toggle theme"
            >
              <span
                className="absolute top-0.5 rounded-full transition-transform duration-200"
                style={{
                  width: 16,
                  height: 16,
                  background: '#fff',
                  transform: isDark ? 'translateX(17px)' : 'translateX(2px)',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                }}
              />
            </button>
          </div>
        </div>
      )}

      {/* Trigger button */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center justify-center rounded-lg transition-colors"
        style={{
          width: 32,
          height: 32,
          background: open ? 'var(--icon-btn-hover)' : 'var(--icon-btn-bg)',
          color: 'var(--text-secondary)',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--icon-btn-hover)' }}
        onMouseLeave={e => { e.currentTarget.style.background = open ? 'var(--icon-btn-hover)' : 'var(--icon-btn-bg)' }}
        title="Settings"
      >
        <GearIcon />
      </button>
    </div>
  )
}
