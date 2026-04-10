import { useState } from 'react'
import { useChat } from './hooks/useChat'
import { usePantry } from './hooks/usePantry'
import ChatWindow from './components/ChatWindow'
import PreferencesPanel from './components/PreferencesPanel'
import PantryPanel from './components/PantryPanel'
import chefLogo from './assets/logo.png'

const PlusIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

const ChatIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)

const BoxIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
  </svg>
)

const SlidersIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
    <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
    <line x1="1" y1="14" x2="7" y2="14"/>
    <line x1="9" y1="8" x2="15" y2="8"/>
    <line x1="17" y1="16" x2="23" y2="16"/>
  </svg>
)

const SettingsIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

const DiceIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="3"/>
    <circle cx="8.5" cy="8.5" r="1.2" fill="currentColor" stroke="none"/>
    <circle cx="15.5" cy="8.5" r="1.2" fill="currentColor" stroke="none"/>
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>
    <circle cx="8.5" cy="15.5" r="1.2" fill="currentColor" stroke="none"/>
    <circle cx="15.5" cy="15.5" r="1.2" fill="currentColor" stroke="none"/>
  </svg>
)

export default function App() {
  const { messages, isLoading, sendMessage, conversationId, preferences, updatePreferences } = useChat()
  const { items: pantryItems, loading: pantryLoading, fetchPantry, addItem, deleteItem, updateItem } = usePantry(conversationId)
  const [activeTab, setActiveTab] = useState('chat')

  const handleItemsAdded = () => {
    setActiveTab('pantry')
    fetchPantry()
  }

  const handleDiceRoll = () => {
    setActiveTab('chat')
    sendMessage('What can I make with the ingredients currently in my pantry?')
  }

  const navItem = (tab, Icon, label, badge) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium text-left ${activeTab === tab ? 'nav-active' : ''}`}
      style={{
        color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
      }}
    >
      <Icon />
      {label}
      {badge != null && badge > 0 && (
        <span className="ml-auto text-xs px-1.5 py-0.5 rounded-full"
          style={{ background: '#0061A0', color: '#fff' }}>
          {badge}
        </span>
      )}
    </button>
  )

  return (
    <div className="h-screen flex" style={{ background: 'var(--bg-page)' }}>

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className="w-72 flex flex-col flex-shrink-0 py-4"
        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--sidebar-border)' }}
      >
        {/* Brand */}
        <div className="px-5 pb-4 mb-1 flex items-center gap-3"
          style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <img src={chefLogo} alt="Fridgy" className="w-9 h-9 rounded-xl object-cover" />
          <span className="font-semibold text-base leading-tight" style={{ color: 'var(--text-primary)' }}>
            Fridgy
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 pt-3 space-y-1">
          <button
            className="nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium text-left"
            style={{ color: 'var(--text-secondary)' }}
            onClick={() => { setActiveTab('chat'); window.location.reload() }}
          >
            <PlusIcon /> New Chat
          </button>
          {navItem('chat', ChatIcon, 'Chat')}
          {navItem('pantry', BoxIcon, 'Pantry', pantryItems.length)}
          {navItem('preferences', SlidersIcon, 'Preferences')}
        </nav>

        {/* Footer actions */}
        <div className="px-3 pt-3 space-y-1" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <button
            onClick={handleDiceRoll}
            className="nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium text-left"
            style={{ color: 'var(--text-secondary)' }}
            title="Surprise me — suggest a meal from my pantry"
          >
            <DiceIcon /> Surprise Me
          </button>
          <button
            onClick={() => setActiveTab('preferences')}
            className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium text-left ${activeTab === 'preferences' ? 'nav-active' : ''}`}
            style={{ color: activeTab === 'preferences' ? 'var(--text-primary)' : 'var(--text-muted)' }}
          >
            <SettingsIcon /> Settings
          </button>
          <p className="text-xs px-3 pt-1" style={{ color: 'var(--text-muted)' }}>AI-powered grocery assistant</p>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden" style={{ zoom: 1.15 }}>
        {activeTab === 'chat' && (
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            sendMessage={sendMessage}
            conversationId={conversationId}
            onItemsAdded={handleItemsAdded}
          />
        )}
        {activeTab === 'pantry' && (
          <PantryPanel
            items={pantryItems}
            loading={pantryLoading}
            onAdd={addItem}
            onDelete={deleteItem}
            onUpdate={updateItem}
          />
        )}
        {activeTab === 'preferences' && (
          <PreferencesPanel preferences={preferences} onUpdate={updatePreferences} />
        )}
      </main>
    </div>
  )
}
