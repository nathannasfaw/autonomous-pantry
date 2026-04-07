import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'

export function usePantry(conversationId) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchPantry = useCallback(async () => {
    if (!conversationId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/pantry/${conversationId}`)
      if (!res.ok) return
      const data = await res.json()
      setItems(data.pantry ?? [])
    } catch (err) {
      console.error('Failed to fetch pantry:', err)
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  // Load on mount and whenever conversationId changes
  useEffect(() => { fetchPantry() }, [fetchPantry])

  const addItem = useCallback(async (item) => {
    // Optimistic update
    setItems(prev => {
      const exists = prev.find(p => p.item.toLowerCase() === item.item.toLowerCase())
      if (exists) return prev.map(p =>
        p.item.toLowerCase() === item.item.toLowerCase() ? { ...p, ...item } : p
      )
      return [...prev, item]
    })
    try {
      await fetch(`${API_BASE}/pantry/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, items: [item], replace: false }),
      })
    } catch (err) {
      console.error('Failed to add pantry item:', err)
      fetchPantry() // revert on failure
    }
  }, [conversationId, fetchPantry])

  const deleteItem = useCallback(async (itemName) => {
    const newItems = items.filter(i => i.item.toLowerCase() !== itemName.toLowerCase())
    setItems(newItems)
    try {
      await fetch(`${API_BASE}/pantry/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, items: newItems, replace: true }),
      })
    } catch (err) {
      console.error('Failed to delete pantry item:', err)
      fetchPantry()
    }
  }, [items, conversationId, fetchPantry])

  const updateItem = useCallback(async (itemName, changes) => {
    const newItems = items.map(i =>
      i.item.toLowerCase() === itemName.toLowerCase() ? { ...i, ...changes } : i
    )
    setItems(newItems)
    try {
      await fetch(`${API_BASE}/pantry/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, items: newItems, replace: true }),
      })
    } catch (err) {
      console.error('Failed to update pantry item:', err)
      fetchPantry()
    }
  }, [items, conversationId, fetchPantry])

  return { items, loading, fetchPantry, addItem, deleteItem, updateItem }
}
