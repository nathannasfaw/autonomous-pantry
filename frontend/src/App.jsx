import ChatWindow from './components/ChatWindow'

const AsteriskLogo = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.2" strokeLinecap="round">
    <line x1="12" y1="2" x2="12" y2="22"/>
    <line x1="2" y1="12" x2="22" y2="12"/>
    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
    <line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/>
  </svg>
)

const PlusIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

const ChatIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)

const BoxIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
  </svg>
)

export default function App() {
  return (
    <div className="h-screen flex" style={{ background: 'var(--bg-page)' }}>
      {/* Sidebar */}
      <aside
        className="w-60 flex flex-col flex-shrink-0 py-3"
        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--sidebar-border)' }}
      >
        {/* Brand */}
        <div className="px-4 pb-3 mb-1 flex items-center gap-2.5" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <div className="w-7 h-7 rounded-lg bg-zinc-900 flex items-center justify-center text-white">
            <AsteriskLogo />
          </div>
          <span className="font-semibold text-sm text-zinc-900 leading-tight">Autonomous Pantry</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 pt-2 space-y-0.5">
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors text-left">
            <PlusIcon />
            New Chat
          </button>
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium bg-zinc-100 text-zinc-900 text-left">
            <ChatIcon />
            Chat
          </button>
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-zinc-500 hover:bg-zinc-50 transition-colors text-left">
            <BoxIcon />
            Pantry
          </button>
        </nav>

        {/* Footer */}
        <div className="px-4 pt-3" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <p className="text-xs text-zinc-400">AI-powered grocery assistant</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow />
      </main>
    </div>
  )
}
