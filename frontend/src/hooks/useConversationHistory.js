import { useState, useCallback } from 'react'

const STORAGE_KEY = 'fridgy-conversations'
const API_BASE = 'http://localhost:8000'

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
 * Each entry: { id, title, titleGenerated, createdAt, messages }
 */
export function useConversationHistory() {
  const [history, setHistory] = useState(() => loadHistory())

  const saveConversation = useCallback((id, title, messages) => {
    if (!id || messages.length === 0) return
    setHistory(prev => {
      const existing = prev.findIndex(c => c.id === id)
      const entry = {
        id,
        title: title || (existing >= 0 ? prev[existing].title : 'New Chat'),
        titleGenerated: title ? true : (existing >= 0 ? prev[existing].titleGenerated : false),
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
      updated = updated.slice(0, 50)
      saveHistory(updated)
      return updated
    })
  }, [])

  const updateTitle = useCallback((id, title) => {
    setHistory(prev => {
      const updated = prev.map(c =>
        c.id === id ? { ...c, title, titleGenerated: true } : c
      )
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

  // Request a summarized title from the backend
  const generateTitle = useCallback(async (id, messages) => {
    try {
      const res = await fetch(`${API_BASE}/chat/summarize-title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.title) {
          updateTitle(id, data.title)
        }
      }
    } catch (err) {
      console.error('Failed to generate title:', err)
    }
  }, [updateTitle])

  return { history, saveConversation, deleteConversation, getConversation, updateTitle, generateTitle }
}
