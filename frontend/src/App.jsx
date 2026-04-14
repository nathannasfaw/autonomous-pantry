import { useState } from 'react'
import { useChat } from './hooks/useChat'
import { usePantry } from './hooks/usePantry'
import ChatWindow from './components/ChatWindow'
import PreferencesPanel from './components/PreferencesPanel'
import PantryPanel from './components/PantryPanel'
import SettingsPanel from './components/SettingsPanel'
import LoginModal from './components/LoginModal'
import { ThemeProvider } from './context/ThemeContext'
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
  const { messages, isLoading, sendMessage, conversationId, preferences, updatePreferences } = useChat()
  const { items: pantryItems, loading: pantryLoading, fetchPantry, addItem, deleteItem, updateItem } = usePantry(conversationId)
  const [activeTab, setActiveTab] = useState('chat')

  // Called when camera scan confirms items:
  // 1. Switch to pantry tab to show the update
  // 2. Refresh pantry list from the persistent backend store
  // Chat remains untouched unless the user explicitly starts a conversation.
  const handleItemsAdded = () => {
    setActiveTab('pantry')
    fetchPantry()
  }

  const navItem = (tab, Icon, label, badge) => (
    <button
      onClick={() => setActiveTab(tab)}
      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors"
      style={{
        background: activeTab === tab ? '#3F4147' : 'transparent',
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
    <ThemeProvider>
    <div className="h-screen flex" style={{ background: 'var(--bg-page)' }}>

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className="w-60 flex flex-col flex-shrink-0 py-3"
        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--sidebar-border)' }}
      >
        {/* Brand */}
        <div className="px-4 pb-3 mb-1 flex items-center gap-2.5"
          style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <span className="font-bold text-xl leading-tight tracking-tight">
            <span style={{ color: '#5B8FCC' }}>Kitchen</span><span style={{ color: '#4A9A9A' }}>Sync</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 pt-2 space-y-0.5">
          <button
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left hover:bg-[#3F4147]"
            style={{ color: 'var(--text-secondary)' }}
            onClick={() => { setActiveTab('chat'); sendMessage && window.location.reload() }}
          >
            <PlusIcon /> New Chat
          </button>
          {navItem('chat', ChatIcon, 'Chat')}
          {navItem('pantry', BoxIcon, 'Pantry', pantryItems.length)}
          {navItem('preferences', SlidersIcon, 'Preferences')}
        </nav>

        {/* Footer */}
        <div className="px-4 pt-3" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>AI-powered grocery assistant</p>
          <div className="flex items-center gap-2">
            <SettingsPanel />
            <LoginModal />
          </div>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
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
    </ThemeProvider>
  )
}
