import { useState, useCallback } from 'react'

const STORAGE_KEY = 'fridgy-conversations'

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveHistory(history) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
}

/**
 * Manages a list of past conversations in localStorage.
 * Each entry: { id, title, createdAt, messages }
 */
export function useConversationHistory() {
  const [history, setHistory] = useState(() => loadHistory())

  const saveConversation = useCallback((id, title, messages) => {
    if (!id || messages.length === 0) return
    setHistory(prev => {
      const existing = prev.findIndex(c => c.id === id)
      const entry = {
        id,
        title: title || deriveTitle(messages),
        createdAt: existing >= 0 ? prev[existing].createdAt : new Date().toISOString(),
        messages,
      }
      let updated
      if (existing >= 0) {
        updated = [...prev]
        updated[existing] = entry
      } else {
        updated = [entry, ...prev]
      }
      // Keep last 50 conversations
      updated = updated.slice(0, 50)
      saveHistory(updated)
      return updated
    })
  }, [])

  const deleteConversation = useCallback((id) => {
    setHistory(prev => {
      const updated = prev.filter(c => c.id !== id)
      saveHistory(updated)
      return updated
    })
  }, [])

  const getConversation = useCallback((id) => {
    return loadHistory().find(c => c.id === id) || null
  }, [])

  return { history, saveConversation, deleteConversation, getConversation }
}

function deriveTitle(messages) {
  const firstUser = messages.find(m => m.role === 'user')
  if (!firstUser) return 'New Chat'
  const text = firstUser.text || ''
  return text.length > 40 ? text.slice(0, 40) + '…' : text
}
