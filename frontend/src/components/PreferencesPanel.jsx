import { useState } from 'react'

const DIETARY_OPTIONS = [
  'Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free',
  'Nut-Free', 'Keto', 'Low-Carb', 'Halal', 'Kosher',
  'No Shellfish', 'No Pork', 'No Red Meat',
]

const SKILL_LEVELS = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
]

const SliderField = ({ label, value, onChange, min, max, step, format }) => (
  <div className="space-y-1.5">
    <div className="flex justify-between items-center">
      <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
        {format ? format(value) : value}
      </span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={e => onChange(parseFloat(e.target.value))}
      className="w-full accent-[#0061A0]"
      style={{ height: 4 }}
    />
  </div>
)

export default function PreferencesPanel({ preferences, onUpdate }) {
  const [dislikedInput, setDislikedInput] = useState('')

  if (!preferences) return null

  const dietary = preferences.dietary_flags || []
  const disliked = preferences.disliked_ingredients || []

  const toggleDietary = (flag) => {
    const normalized = flag.toLowerCase()
    const updated = dietary.includes(normalized)
      ? dietary.filter(f => f !== normalized)
      : [...dietary, normalized]
    onUpdate({ dietary_flags: updated })
  }

  const addDisliked = () => {
    const item = dislikedInput.trim().toLowerCase()
    if (item && !disliked.includes(item)) {
      onUpdate({ disliked_ingredients: [...disliked, item] })
    }
    setDislikedInput('')
  }

  const removeDisliked = (item) => {
    onUpdate({ disliked_ingredients: disliked.filter(d => d !== item) })
  }

  return (
    <div className="flex flex-col gap-4 px-3 py-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 120px)' }}>

      {/* Quality vs Price */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Priority
        </div>
        <SliderField
          label={preferences.quality_priority <= 0.3 ? '💰 Price-focused' : preferences.quality_priority >= 0.7 ? '✨ Quality-focused' : '⚖️ Balanced'}
          value={preferences.quality_priority ?? 0.5}
          onChange={v => onUpdate({ quality_priority: v })}
          min={0} max={1} step={0.1}
          format={v => v <= 0.3 ? 'Budget' : v >= 0.7 ? 'Premium' : 'Balanced'}
        />
      </div>

      {/* Budget */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Budget
        </div>
        <div className="space-y-3">
          <SliderField
            label="Per meal"
            value={preferences.budget_per_order ?? 80}
            onChange={v => onUpdate({ budget_per_order: v })}
            min={10} max={200} step={5}
            format={v => `$${v}`}
          />
          <SliderField
            label="Per person"
            value={preferences.budget_per_person ?? 20}
            onChange={v => onUpdate({ budget_per_person: v })}
            min={5} max={50} step={2.5}
            format={v => `$${v}`}
          />
        </div>
      </div>

      {/* Servings & Household */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Household
        </div>
        <div className="space-y-3">
          <SliderField
            label="Servings per meal"
            value={preferences.serving_size ?? 2}
            onChange={v => onUpdate({ serving_size: v })}
            min={1} max={12} step={1}
          />
          <SliderField
            label="Household size"
            value={preferences.household_size ?? 2}
            onChange={v => onUpdate({ household_size: v })}
            min={1} max={10} step={1}
          />
        </div>
      </div>

      {/* Max Prep Time */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Cooking
        </div>
        <SliderField
          label="Max prep time"
          value={preferences.max_prep_time ?? 60}
          onChange={v => onUpdate({ max_prep_time: v })}
          min={10} max={120} step={5}
          format={v => v >= 120 ? 'No limit' : `${v} min`}
        />
        <div className="flex gap-1.5 mt-2">
          {SKILL_LEVELS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onUpdate({ skill_level: value })}
              className="flex-1 text-[11px] py-1.5 rounded-lg font-medium transition-all"
              style={{
                background: preferences.skill_level === value ? '#0061A0' : '#3F4147',
                color: preferences.skill_level === value ? '#fff' : 'var(--text-secondary)',
                border: `1px solid ${preferences.skill_level === value ? '#0061A0' : '#4F5159'}`,
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Dietary Restrictions */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Dietary
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DIETARY_OPTIONS.map(option => {
            const active = dietary.includes(option.toLowerCase())
            return (
              <button
                key={option}
                onClick={() => toggleDietary(option)}
                className="text-[11px] px-2.5 py-1 rounded-full font-medium transition-all"
                style={{
                  background: active ? '#0061A0' : 'transparent',
                  color: active ? '#fff' : 'var(--text-secondary)',
                  border: `1px solid ${active ? '#0061A0' : '#4F5159'}`,
                }}
              >
                {option}
              </button>
            )
          })}
        </div>
      </div>

      {/* Organic */}
      <div>
        <button
          onClick={() => onUpdate({ preferred_organic: !preferences.preferred_organic })}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all"
          style={{
            background: preferences.preferred_organic ? 'rgba(0,97,160,0.15)' : '#3F4147',
            border: `1px solid ${preferences.preferred_organic ? '#0061A0' : '#4F5159'}`,
            color: 'var(--text-primary)',
          }}
        >
          <span className="text-xs font-medium">Prefer organic</span>
          <div
            className="w-8 h-4 rounded-full relative transition-all"
            style={{ background: preferences.preferred_organic ? '#0061A0' : '#4F5159' }}
          >
            <div
              className="w-3 h-3 rounded-full bg-white absolute top-0.5 transition-all"
              style={{ left: preferences.preferred_organic ? 18 : 2 }}
            />
          </div>
        </button>
      </div>

      {/* Disliked Ingredients */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
          Disliked ingredients
        </div>
        <div className="flex gap-1.5 mb-2">
          <input
            type="text"
            value={dislikedInput}
            onChange={e => setDislikedInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addDisliked()}
            placeholder="Add item..."
            className="flex-1 text-xs px-2.5 py-1.5 rounded-lg outline-none"
            style={{ background: '#3F4147', color: 'var(--text-primary)', border: '1px solid #4F5159' }}
          />
          <button
            onClick={addDisliked}
            className="text-xs px-2.5 py-1.5 rounded-lg font-medium text-white"
            style={{ background: '#0061A0' }}
          >
            Add
          </button>
        </div>
        {disliked.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {disliked.map(item => (
              <span
                key={item}
                className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full"
                style={{ background: '#4F5159', color: 'var(--text-secondary)' }}
              >
                {item}
                <button
                  onClick={() => removeDisliked(item)}
                  className="hover:text-white ml-0.5"
                  style={{ color: 'var(--text-muted)' }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
