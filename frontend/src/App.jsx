import { useState } from 'react'
import { useChat } from './hooks/useChat'
import ChatWindow from './components/ChatWindow'
import PreferencesPanel from './components/PreferencesPanel'
import chefLogo from './assets/logo.png'

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

const SlidersIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
    <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
    <line x1="1" y1="14" x2="7" y2="14"/>
    <line x1="9" y1="8" x2="15" y2="8"/>
    <line x1="17" y1="16" x2="23" y2="16"/>
  </svg>
)

export default function App() {
  const { messages, isLoading, sendMessage, preferences, updatePreferences } = useChat()
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div className="h-screen flex" style={{ background: 'var(--bg-page)' }}>
      {/* Sidebar */}
      <aside
        className="w-60 flex flex-col flex-shrink-0 py-3"
        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--sidebar-border)' }}
      >
        {/* Brand */}
        <div className="px-4 pb-3 mb-1 flex items-center gap-2.5" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <img src={chefLogo} alt="Fridgy" className="w-7 h-7 rounded-lg object-cover" />
          <span className="font-semibold text-sm leading-tight" style={{ color: 'var(--text-primary)' }}>Fridgy</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 pt-2 space-y-0.5">
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left hover:bg-[#3F4147]" style={{ color: 'var(--text-secondary)' }}>
            <PlusIcon />
            New Chat
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors"
            style={{
              background: activeTab === 'chat' ? '#3F4147' : 'transparent',
              color: activeTab === 'chat' ? 'var(--text-primary)' : 'var(--text-secondary)',
            }}
          >
            <ChatIcon />
            Chat
          </button>
          <button
            onClick={() => setActiveTab('preferences')}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors"
            style={{
              background: activeTab === 'preferences' ? '#3F4147' : 'transparent',
              color: activeTab === 'preferences' ? 'var(--text-primary)' : 'var(--text-secondary)',
            }}
          >
            <SlidersIcon />
            Preferences
          </button>
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left hover:bg-[#3F4147]" style={{ color: 'var(--text-muted)' }}>
            <BoxIcon />
            Pantry
          </button>
        </nav>

        {/* Footer */}
        <div className="px-4 pt-3" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>AI-powered grocery assistant</p>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 flex flex-col overflow-hidden" style={{ zoom: 1.2 }}>
        {activeTab === 'chat' && (
          <ChatWindow messages={messages} isLoading={isLoading} sendMessage={sendMessage} />
        )}
        {activeTab === 'preferences' && (
          <PreferencesPanel preferences={preferences} onUpdate={updatePreferences} />
        )}
      </main>
    </div>
  )
}
