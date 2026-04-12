import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'
const CLIENT_ID_KEY = 'autonomous-pantry-client-id'

function getClientId() {
  const existing = window.localStorage.getItem(CLIENT_ID_KEY)
  if (existing) return existing

  const created = crypto.randomUUID()
  window.localStorage.setItem(CLIENT_ID_KEY, created)
  return created
}

export function useChat() {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [preferences, setPreferences] = useState(null)
  // When viewing a loaded conversation, we track the original ID so saves go to the right place
  const [loadedConvId, setLoadedConvId] = useState(null)
  // Whether the current messages are from a loaded conversation (skip auto-save until user sends a new message)
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

      // Load default preferences
      const prefResp = await fetch(`${API_BASE}/chat/preferences/${data.conversation_id}`)
      if (prefResp.ok) {
        setPreferences(await prefResp.json())
      }
      return data.conversation_id
    } catch (err) {
      console.error('Failed to start chat session:', err)
      setMessages([
        {
          role: 'assistant',
          text: 'Failed to connect to the backend. Please make sure the server is running.',
          recipe: null,
          cart: null,
          stage: 'error',
          orderConfirmed: false,
          orderDetails: null,
        },
      ])
      return null
    }
  }, [])

  // Auto-start session on mount
  useEffect(() => {
    startSession()
  }, [startSession])

  const sendMessage = useCallback(
    async (text) => {
      if (!conversationId || !text.trim()) return

      // Add user message immediately
      const userMsg = {
        role: 'user',
        text: text.trim(),
        recipe: null,
        cart: null,
        stage: null,
        orderConfirmed: false,
        orderDetails: null,
        timestamp: new Date().toISOString(),
      }
      setIsViewingHistory(false)
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)

      try {
        const response = await fetch(`${API_BASE}/chat/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: conversationId,
            message: text.trim(),
          }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `Server error: ${response.status}`)
        }

        const data = await response.json()

        const assistantMsg = {
          role: 'assistant',
          text: data.message,
          recipe: data.recipe || null,
          cart: data.cart || null,
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
            recipe: null,
            cart: null,
            stage: 'error',
            orderConfirmed: false,
            orderDetails: null,
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
      // Optimistic update
      setPreferences(prev => ({ ...prev, ...newPrefs }))
      try {
        await fetch(`${API_BASE}/chat/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: conversationId,
            preferences: newPrefs,
          }),
        })
      } catch (err) {
        console.error('Failed to update preferences:', err)
      }
    },
    [conversationId]
  )

  // Load a saved conversation (shows history, starts new backend session for continuity)
  const loadConversation = useCallback(async (savedConvId, savedMessages) => {
    setIsViewingHistory(true)
    setLoadedConvId(savedConvId)
    // Start a fresh backend session, then restore the saved messages on top
    await startSession()
    setMessages(savedMessages)
  }, [startSession])

  // Reset to a fresh chat
  const resetChat = useCallback(async () => {
    setIsViewingHistory(false)
    setLoadedConvId(null)
    setMessages([])
    await startSession()
  }, [startSession])

  // The effective conversation ID for history saving purposes
  // When viewing a loaded conversation, use the original ID so we don't create duplicates
  const historyConvId = loadedConvId || conversationId

  return {
    messages,
    isLoading,
    sendMessage,
    conversationId,
    preferences,
    updatePreferences,
    resetChat,
    loadConversation,
    historyConvId,
    isViewingHistory,
  }
}
