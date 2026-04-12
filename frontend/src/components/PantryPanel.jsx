import { useState } from 'react'

const UNITS = ['count', 'lbs', 'oz', 'cups', 'tbsp', 'tsp', 'bottle', 'bag', 'can',
               'bunch', 'cloves', 'package', 'jar', 'box', 'loaf', 'head', 'stick', 'piece', 'sheets']

const TrashIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
)

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

const SearchIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
)

const EMPTY_FORM = { item: '', quantity: '1', unit: 'count' }

export default function PantryPanel({ items, loading, onAdd, onDelete, onUpdate }) {
  const [search, setSearch]     = useState('')
  const [form, setForm]         = useState(EMPTY_FORM)
  const [addOpen, setAddOpen]   = useState(false)
  const [adding, setAdding]     = useState(false)
  const [editKey, setEditKey]   = useState(null)   // item name being inline-edited
  const [editQty, setEditQty]   = useState('')

  const filtered = items.filter(i =>
    i.item.toLowerCase().includes(search.toLowerCase())
  )

  const handleAdd = async () => {
    if (!form.item.trim()) return
    setAdding(true)
    await onAdd({
      item: form.item.toLowerCase().trim(),
      quantity: parseFloat(form.quantity) || 1,
      unit: form.unit,
      confidence: 1.0,
    })
    setForm(EMPTY_FORM)
    setAddOpen(false)
    setAdding(false)
  }

  const startEdit = (item) => {
    setEditKey(item.item)
    setEditQty(String(item.quantity))
  }

  const commitEdit = async (item) => {
    const qty = parseFloat(editQty)
    if (!isNaN(qty) && qty > 0) await onUpdate(item.item, { quantity: qty })
    setEditKey(null)
  }

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--bg-page)' }}>

      {/* ── header ──────────────────────────────────────────────────────────── */}
      <div className="px-6 py-5" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              My Pantry
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {items.length} item{items.length !== 1 ? 's' : ''} · used by the AI for recipe recommendations
            </p>
          </div>
          <button
            onClick={() => setAddOpen(o => !o)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all hover:brightness-110"
            style={{ background: 'linear-gradient(135deg,#0061A0,#0D5E9D)', color: '#fff' }}
          >
            <PlusIcon /> Add item
          </button>
        </div>

        {/* search */}
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}>
            <SearchIcon />
          </span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search pantry…"
            className="w-full pl-9 pr-4 py-2 rounded-xl text-sm outline-none"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--sidebar-border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      </div>

      {/* ── add form ────────────────────────────────────────────────────────── */}
      {addOpen && (
        <div className="px-6 py-4" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--sidebar-border)' }}>
          <p className="text-xs font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
            NEW ITEM
          </p>
          <div className="flex gap-2">
            <input
              value={form.item}
              onChange={e => setForm(f => ({ ...f, item: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
              placeholder="Item name"
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--sidebar-border)', color: 'var(--text-primary)' }}
              autoFocus
            />
            <input
              type="number"
              min="0"
              step="0.5"
              value={form.quantity}
              onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
              className="w-20 px-3 py-2 rounded-lg text-sm outline-none text-center"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--sidebar-border)', color: 'var(--text-primary)' }}
            />
            <select
              value={form.unit}
              onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}
              className="px-2 py-2 rounded-lg text-sm outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--sidebar-border)', color: 'var(--text-secondary)' }}
            >
              {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
            <button
              onClick={handleAdd}
              disabled={!form.item.trim() || adding}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: 'linear-gradient(135deg,#0061A0,#0D5E9D)' }}
            >
              {adding ? '…' : 'Add'}
            </button>
          </div>
        </div>
      )}

      {/* ── item list ───────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading pantry…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-10">
            <span className="text-4xl">📦</span>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {search ? 'No items match your search.' : 'Your pantry is empty. Add items or use the camera scanner.'}
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {filtered.map(item => (
              <div
                key={item.item}
                className="flex items-center gap-3 px-4 py-3 rounded-xl group"
                style={{ background: 'var(--bg-card)', border: '1px solid transparent' }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--sidebar-border)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}
              >
                {/* confidence dot */}
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    background: (item.confidence ?? 1) >= 0.75 ? '#34D399' : '#FBBF24',
                  }}
                  title={`Confidence: ${Math.round((item.confidence ?? 1) * 100)}%`}
                />

                {/* name */}
                <span className="flex-1 text-sm font-medium capitalize"
                  style={{ color: 'var(--text-primary)' }}>
                  {item.item}
                </span>

                {/* quantity — click to edit inline */}
                <div className="flex items-center gap-1.5">
                  {editKey === item.item ? (
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={editQty}
                      onChange={e => setEditQty(e.target.value)}
                      onBlur={() => commitEdit(item)}
                      onKeyDown={e => { if (e.key === 'Enter') commitEdit(item); if (e.key === 'Escape') setEditKey(null) }}
                      className="w-14 px-2 py-0.5 rounded text-sm text-center outline-none"
                      style={{ background: 'var(--sidebar-border)', color: 'var(--text-primary)', border: '1px solid #0061A0' }}
                      autoFocus
                    />
                  ) : (
                    <button
                      onClick={() => startEdit(item)}
                      className="text-sm px-2 py-0.5 rounded hover:bg-[var(--bg-hover)] transition-colors"
                      style={{ color: 'var(--text-secondary)' }}
                      title="Click to edit quantity"
                    >
                      {item.quantity}
                    </button>
                  )}
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {item.unit}
                  </span>
                </div>

                {/* delete */}
                <button
                  onClick={() => onDelete(item.item)}
                  className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/20"
                  style={{ color: '#F87171' }}
                  title="Remove from pantry"
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
