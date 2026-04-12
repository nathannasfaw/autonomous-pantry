import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'
const CLIENT_ID_KEY = 'autonomous-pantry-client-id'
const PREFS_KEY = 'autonomous-pantry-preferences'

function getClientId() {
  const existing = window.localStorage.getItem(CLIENT_ID_KEY)
  if (existing) return existing
  const created = crypto.randomUUID()
  window.localStorage.setItem(CLIENT_ID_KEY, created)
  return created
}

function loadSavedPreferences() {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function persistPreferences(prefs) {
  if (prefs) localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
}

export function useChat() {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [preferences, setPreferences] = useState(() => loadSavedPreferences())
  const [loadedConvId, setLoadedConvId] = useState(null)
  const [isViewingHistory, setIsViewingHistory] = useState(false)

  const startSession = useCallback(async () => {
    try {
      const clientId = getClientId()
      const response = await fetch(`${API_BASE}/chat/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId }),
      })
      if (!response.ok) {
        throw new Error(`Failed to start session: ${response.status}`)
      }
      const data = await response.json()
      setConversationId(data.conversation_id)
      setMessages([])

      // If we have saved preferences, push them to the new session
      const saved = loadSavedPreferences()
      if (saved) {
        setPreferences(saved)
        // Sync to backend
        fetch(`${API_BASE}/chat/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversation_id: data.conversation_id, preferences: saved }),
        }).catch(() => {})
      } else {
        // Load defaults from backend
        const prefResp = await fetch(`${API_BASE}/chat/preferences/${data.conversation_id}`)
        if (prefResp.ok) {
          const prefs = await prefResp.json()
          setPreferences(prefs)
          persistPreferences(prefs)
        }
      }
      return data.conversation_id
    } catch (err) {
      console.error('Failed to start chat session:', err)
      setMessages([
        {
          role: 'assistant',
          text: 'Failed to connect to the backend. Please make sure the server is running.',
          recipe: null, cart: null, stage: 'error',
          orderConfirmed: false, orderDetails: null,
        },
      ])
      return null
    }
  }, [])

  useEffect(() => { startSession() }, [startSession])

  const sendMessage = useCallback(
    async (text) => {
      if (!conversationId || !text.trim()) return
      const userMsg = {
        role: 'user', text: text.trim(),
        recipe: null, cart: null, stage: null,
        orderConfirmed: false, orderDetails: null,
        timestamp: new Date().toISOString(),
      }
      setIsViewingHistory(false)
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)

      try {
        const response = await fetch(`${API_BASE}/chat/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversation_id: conversationId, message: text.trim() }),
        })
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `Server error: ${response.status}`)
        }
        const data = await response.json()
        const assistantMsg = {
          role: 'assistant', text: data.message,
          recipe: data.recipe || null, cart: data.cart || null,
          stage: data.stage,
          orderConfirmed: data.order_confirmed || false,
          orderDetails: data.order_details || null,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMsg])
      } catch (err) {
        console.error('Failed to send message:', err)
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `Sorry, something went wrong: ${err.message}`,
            recipe: null, cart: null, stage: 'error',
            orderConfirmed: false, orderDetails: null,
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [conversationId]
  )

  const updatePreferences = useCallback(
    async (newPrefs) => {
      if (!conversationId) return
      const merged = { ...preferences, ...newPrefs }
      setPreferences(merged)
      persistPreferences(merged)
      try {
        await fetch(`${API_BASE}/chat/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversation_id: conversationId, preferences: newPrefs }),
        })
      } catch (err) {
        console.error('Failed to update preferences:', err)
      }
    },
    [conversationId, preferences]
  )

  const loadConversation = useCallback(async (savedConvId, savedMessages) => {
    setIsViewingHistory(true)
    setLoadedConvId(savedConvId)
    await startSession()
    setMessages(savedMessages)
  }, [startSession])

  const resetChat = useCallback(async () => {
    setIsViewingHistory(false)
    setLoadedConvId(null)
    setMessages([])
    await startSession()
  }, [startSession])

  const historyConvId = loadedConvId || conversationId

  return {
    messages, isLoading, sendMessage, conversationId,
    preferences, updatePreferences, resetChat, loadConversation,
    historyConvId, isViewingHistory,
  }
}
