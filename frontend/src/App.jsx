import { useState, useEffect, useCallback } from 'react'
import { useChat } from './hooks/useChat'
import { usePantry } from './hooks/usePantry'
import ChatWindow from './components/ChatWindow'
import PreferencesPanel from './components/PreferencesPanel'
import PantryPanel from './components/PantryPanel'
import SettingsPanel from './components/SettingsPanel'
import LoginModal from './components/LoginModal'
import { ThemeProvider } from './context/ThemeContext'

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

const CHAT_HISTORY_KEY = 'kitchensync-chat-history'

function loadChatHistory() {
  try {
    return JSON.parse(localStorage.getItem(CHAT_HISTORY_KEY) || '[]')
  } catch { return [] }
}

function saveChatHistory(history) {
  localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history))
}

const TrashSmallIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
)

const ClockIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)

export default function App() {
  const { messages, isLoading, sendMessage, conversationId, preferences, updatePreferences } = useChat()
  const { items: pantryItems, loading: pantryLoading, fetchPantry, addItem, deleteItem, updateItem } = usePantry(conversationId)
  const [activeTab, setActiveTab] = useState('chat')
  const [chatHistory, setChatHistory] = useState(loadChatHistory)

  // Save current chat to history when it has messages and a new conversation starts
  const saveCurrentChat = useCallback(() => {
    if (messages.length > 0 && conversationId) {
      const firstUserMsg = messages.find(m => m.role === 'user')
      const title = firstUserMsg?.text?.slice(0, 50) || 'New chat'
      const entry = {
        id: conversationId,
        title,
        timestamp: Date.now(),
        messageCount: messages.length,
      }
      setChatHistory(prev => {
        const filtered = prev.filter(h => h.id !== conversationId)
        const updated = [entry, ...filtered].slice(0, 20)
        saveChatHistory(updated)
        return updated
      })
    }
  }, [messages, conversationId])

  // Save chat history when messages change
  useEffect(() => {
    if (messages.length > 0) saveCurrentChat()
  }, [messages.length])

  const deleteChat = useCallback((id) => {
    setChatHistory(prev => {
      const updated = prev.filter(h => h.id !== id)
      saveChatHistory(updated)
      return updated
    })
  }, [])

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
        background: activeTab === tab ? '#2A2B30' : 'transparent',
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
        <div className="px-4 pb-3 mb-1 flex items-center gap-2.5 header-fade-in"
          style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <span className="text-xl leading-tight tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
            <span style={{ color: '#FFFFFF', fontWeight: 400 }}>Kitchen</span><span style={{ color: '#0061A0', fontWeight: 700 }}>Sync</span><span style={{ color: '#FFFFFF', fontWeight: 400 }}>.</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="px-2 pt-2 space-y-0.5">
          <button
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left hover:bg-[#2A2B30]"
            style={{ color: 'var(--text-secondary)' }}
            onClick={() => { setActiveTab('chat'); sendMessage && window.location.reload() }}
          >
            <PlusIcon /> New Chat
          </button>
          {navItem('chat', ChatIcon, 'Chat')}
          {navItem('pantry', BoxIcon, 'Pantry', pantryItems.length)}
          {navItem('preferences', SlidersIcon, 'Preferences')}
        </nav>

        {/* Chat History */}
        <div className="flex-1 px-2 pt-3 overflow-y-auto" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <div className="flex items-center gap-2 px-3 py-1.5 mb-1">
            <ClockIcon />
            <span className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>History</span>
          </div>
          {chatHistory.length === 0 ? (
            <p className="px-3 text-xs" style={{ color: 'var(--text-muted)' }}>No conversations yet</p>
          ) : (
            chatHistory.map((entry) => (
              <div
                key={entry.id}
                className="group flex items-center gap-1 px-3 py-2 rounded-lg text-sm cursor-default"
                style={{
                  color: entry.id === conversationId ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: entry.id === conversationId ? '#2A2B30' : 'transparent',
                }}
                title={entry.title}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm">{entry.title}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    {new Date(entry.timestamp).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteChat(entry.id) }}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 hover:bg-red-500/20"
                  style={{ color: '#F87171' }}
                  title="Delete chat"
                >
                  <TrashSmallIcon />
                </button>
              </div>
            ))
          )}
        </div>

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
            conversationId={conversationId}
            onItemsScanned={fetchPantry}
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
