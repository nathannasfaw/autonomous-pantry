import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'

export function useChat() {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [preferences, setPreferences] = useState(null)

  // Auto-start session on mount
  useEffect(() => {
    const startSession = async () => {
      try {
        const response = await fetch(`${API_BASE}/chat/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
        if (!response.ok) {
          throw new Error(`Failed to start session: ${response.status}`)
        }
        const data = await response.json()
        setConversationId(data.conversation_id)

        // Load default preferences
        const prefResp = await fetch(`${API_BASE}/chat/preferences/${data.conversation_id}`)
        if (prefResp.ok) {
          setPreferences(await prefResp.json())
        }
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
      }
    }

    startSession()
  }, [])

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
      }
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
          pantryUsed: data.pantry_used || null,
          stage: data.stage,
          orderConfirmed: data.order_confirmed || false,
          orderDetails: data.order_details || null,
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

  return { messages, isLoading, sendMessage, conversationId, preferences, updatePreferences }
}
