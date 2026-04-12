import { useState, useEffect, useRef } from 'react'
import { useChat } from './hooks/useChat'
import { usePantry } from './hooks/usePantry'
import { useConversationHistory } from './hooks/useConversationHistory'
import ChatWindow from './components/ChatWindow'
import PreferencesPanel from './components/PreferencesPanel'
import PantryPanel from './components/PantryPanel'


/* ── Icon components ──────────────────────────────────────────────────────── */

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

const SettingsIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

const SunIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)

const MoonIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)

const HelpIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)

const UserIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
)

const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
)

/* ── Settings dropdown ────────────────────────────────────────────────────── */

function SettingsDropdown({ isOpen, onClose, theme, onToggleTheme }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const menuItem = (icon, label, onClick, extra) => (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors hover:bg-[var(--bg-hover)] text-left"
      style={{ color: 'var(--text-secondary)' }}
    >
      {icon}
      <span className="flex-1">{label}</span>
      {extra}
    </button>
  )

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 right-0 mb-1 rounded-xl overflow-hidden shadow-lg border"
      style={{
        background: 'var(--bg-sidebar)',
        borderColor: 'var(--sidebar-border)',
        zIndex: 50,
      }}
    >
      <div className="p-1.5">
        {menuItem(
          theme === 'dark' ? <SunIcon /> : <MoonIcon />,
          theme === 'dark' ? 'Light mode' : 'Dark mode',
          onToggleTheme,
          <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
            {theme === 'dark' ? '☀' : '☾'}
          </span>
        )}
        {menuItem(<UserIcon />, 'Log in', () => {}, <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>Soon</span>)}
        {menuItem(<HelpIcon />, 'Help & FAQ', () => {}, <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>Soon</span>)}
      </div>
    </div>
  )
}

/* ── Main App ─────────────────────────────────────────────────────────────── */

export default function App() {
  const {
    messages, isLoading, sendMessage, conversationId,
    preferences, updatePreferences, resetChat, loadConversation,
    historyConvId, isViewingHistory,
  } = useChat()
  const { items: pantryItems, loading: pantryLoading, fetchPantry, addItem, deleteItem, updateItem } = usePantry(conversationId)
  const { history, saveConversation, deleteConversation, getConversation, generateTitle } = useConversationHistory()

  const [activeTab, setActiveTab] = useState('chat')
  const [activeConvId, setActiveConvId] = useState(null) // tracks which history entry is active
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('fridgy-theme') || 'dark')

  // Save current conversation to history whenever messages change
  // Skip saving when we're just viewing a loaded conversation (no new messages yet)
  useEffect(() => {
    if (isViewingHistory) return
    if (historyConvId && messages.length > 0) {
      saveConversation(historyConvId, null, messages)
      setActiveConvId(historyConvId)

      // Generate a title after the first assistant response (2 messages = 1 user + 1 assistant)
      const conv = history.find(c => c.id === historyConvId)
      const needsTitle = !conv?.titleGenerated
      const hasFirstExchange = messages.length >= 2 && messages.some(m => m.role === 'assistant')
      if (needsTitle && hasFirstExchange) {
        generateTitle(historyConvId, messages)
      }
    }
  }, [messages, historyConvId, isViewingHistory, saveConversation, generateTitle, history])

  // Apply theme
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('fridgy-theme', theme)
  }, [theme])

  const handleToggleTheme = () => {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
    setSettingsOpen(false)
  }

  const handleNewChat = async () => {
    // Save current conversation before starting new
    if (!isViewingHistory && historyConvId && messages.length > 0) {
      saveConversation(historyConvId, null, messages)
    }
    await resetChat()
    setActiveTab('chat')
    setActiveConvId(null)
  }

  const handleLoadConversation = (conv) => {
    // Save current conversation before switching
    if (!isViewingHistory && historyConvId && messages.length > 0) {
      saveConversation(historyConvId, null, messages)
    }
    setActiveTab('chat')
    setActiveConvId(conv.id)
    loadConversation(conv.id, conv.messages)
  }

  const handleDeleteConversation = (e, id) => {
    e.stopPropagation()
    deleteConversation(id)
    if (activeConvId === id) {
      setActiveConvId(null)
    }
  }

  const handleItemsAdded = () => {
    setActiveTab('pantry')
    fetchPantry()
  }

  const handleDiceRoll = () => {
    setActiveTab('chat')
    sendMessage('What can I make with the ingredients currently in my pantry?')
  }

  // Group history by date
  const groupedHistory = groupByDate(history.filter(c => c.messages.length > 0))

  return (
    <div className="h-screen flex" style={{ background: 'var(--bg-page)' }}>

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className="w-72 flex flex-col flex-shrink-0"
        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--sidebar-border)' }}
      >
        {/* Brand */}
        <div className="px-5 py-4 flex items-center flex-shrink-0"
          style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <span style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.35rem', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1 }}>
            <span style={{ color: 'var(--text-primary)' }}>Kitchen</span>
            <span style={{ color: '#0061A0', fontWeight: 800 }}>Sync</span>
            <span style={{ color: 'var(--text-primary)' }}>.</span>
          </span>
        </div>

        {/* New Chat button */}
        <div className="px-3 pt-3 pb-1 flex-shrink-0">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              border: '1px solid var(--sidebar-border)',
              color: 'var(--text-primary)',
              background: 'transparent',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
          >
            <PlusIcon /> New Chat
          </button>
        </div>

        {/* Nav */}
        <nav className="px-3 pt-2 pb-1 space-y-0.5 flex-shrink-0">
          {[
            { tab: 'chat', Icon: ChatIcon, label: 'Chat' },
            { tab: 'pantry', Icon: BoxIcon, label: 'Pantry', badge: pantryItems.length },
            { tab: 'preferences', Icon: SlidersIcon, label: 'Preferences' },
          ].map(({ tab, Icon, label, badge }) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left ${activeTab === tab ? 'nav-active' : ''}`}
              style={{ color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)' }}
            >
              <Icon /> {label}
              {badge != null && badge > 0 && (
                <span className="ml-auto text-[11px] px-1.5 py-0.5 rounded-full" style={{ background: '#0061A0', color: '#fff' }}>
                  {badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Conversation history */}
        <div className="flex-1 overflow-y-auto px-3 pt-2 pb-2" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          {groupedHistory.length === 0 ? (
            <p className="text-xs text-center py-6" style={{ color: 'var(--text-muted)' }}>
              Your conversations will appear here
            </p>
          ) : (
            groupedHistory.map(({ label, conversations }) => (
              <div key={label} className="mb-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider px-2 py-1.5"
                  style={{ color: 'var(--text-muted)' }}>
                  {label}
                </p>
                {conversations.map(conv => (
                  <button
                    key={conv.id}
                    onClick={() => handleLoadConversation(conv)}
                    className={`group w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm text-left transition-colors mb-0.5 ${activeConvId === conv.id ? 'nav-active' : ''}`}
                    style={{ color: activeConvId === conv.id ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                    onMouseEnter={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = 'var(--bg-hover)' }}
                    onMouseLeave={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = 'transparent' }}
                  >
                    <ChatIcon />
                    <span className="flex-1 truncate">{conv.title}</span>
                    <span
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      className="p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/20"
                      style={{ color: '#F87171' }}
                    >
                      <TrashIcon />
                    </span>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-3 space-y-1 flex-shrink-0" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          <button
            onClick={handleDiceRoll}
            className="nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left"
            style={{ color: 'var(--text-secondary)' }}
            title="Surprise me — suggest a meal from my pantry"
          >
            <DiceIcon /> Surprise Me
          </button>

          <div className="relative">
            <button
              onClick={() => setSettingsOpen(o => !o)}
              className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left ${settingsOpen ? 'nav-active' : ''}`}
              style={{ color: settingsOpen ? 'var(--text-primary)' : 'var(--text-secondary)' }}
            >
              <SettingsIcon /> Settings
            </button>
            <SettingsDropdown
              isOpen={settingsOpen}
              onClose={() => setSettingsOpen(false)}
              theme={theme}
              onToggleTheme={handleToggleTheme}
            />
          </div>

          <p className="text-[11px] px-3 pt-1" style={{ color: 'var(--text-muted)' }}>AI-powered grocery assistant</p>
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

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function groupByDate(conversations) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1)
  const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7)
  const monthAgo = new Date(today); monthAgo.setDate(monthAgo.getDate() - 30)

  const groups = {
    'Today': [],
    'Yesterday': [],
    'Previous 7 Days': [],
    'Previous 30 Days': [],
    'Older': [],
  }

  for (const conv of conversations) {
    const d = new Date(conv.createdAt)
    if (d >= today) groups['Today'].push(conv)
    else if (d >= yesterday) groups['Yesterday'].push(conv)
    else if (d >= weekAgo) groups['Previous 7 Days'].push(conv)
    else if (d >= monthAgo) groups['Previous 30 Days'].push(conv)
    else groups['Older'].push(conv)
  }

  return Object.entries(groups)
    .filter(([, convs]) => convs.length > 0)
    .map(([label, conversations]) => ({ label, conversations }))
}
