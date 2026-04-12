import { useState } from 'react'

const DIETARY_OPTIONS = [
  'Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free',
  'Nut-Free', 'Keto', 'Low-Carb', 'Halal', 'Kosher',
  'No Shellfish', 'No Pork', 'No Red Meat',
]

const SKILL_LEVELS = [
  { value: 'beginner', label: 'Beginner', desc: 'Simple recipes, few steps' },
  { value: 'intermediate', label: 'Intermediate', desc: 'Some technique required' },
  { value: 'advanced', label: 'Advanced', desc: 'Complex dishes welcome' },
]

function Section({ title, children }) {
  return (
    <div
      className="rounded-xl p-5"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--sidebar-border)' }}
    >
      <h3 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function SliderField({ label, value, onChange, min, max, step, format, leftLabel, rightLabel }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
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
        className="w-full accent-[#0061A0] h-1.5 rounded-full"
      />
      {(leftLabel || rightLabel) && (
        <div className="flex justify-between">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{leftLabel}</span>
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{rightLabel}</span>
        </div>
      )}
    </div>
  )
}

export default function PreferencesPanel({ preferences, onUpdate }) {
  const [dislikedInput, setDislikedInput] = useState('')

  if (!preferences) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading preferences...</p>
      </div>
    )
  }

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
    <div className="flex-1 overflow-y-auto py-8 px-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header with visual banner */}
        <div
          className="rounded-xl px-5 py-4 mb-2 flex items-center gap-4"
          style={{
            background: 'linear-gradient(135deg, rgba(0,97,160,0.12) 0%, rgba(13,94,157,0.06) 100%)',
            border: '1px solid rgba(0,97,160,0.15)',
          }}
        >
          <span className="text-3xl">⚙️</span>
          <div>
            <h2 className="text-lg font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Preferences
            </h2>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Customize how your grocery assistant finds recipes and builds your cart.
            </p>
          </div>
        </div>

        {/* Quality vs Price */}
        <Section title="Shopping Priority">
          <SliderField
            label={
              preferences.quality_priority <= 0.3
                ? 'Price-focused — find the best deals'
                : preferences.quality_priority >= 0.7
                ? 'Quality-focused — premium ingredients'
                : 'Balanced — good value for quality'
            }
            value={preferences.quality_priority ?? 0.5}
            onChange={v => onUpdate({ quality_priority: v })}
            min={0} max={1} step={0.05}
            format={v => v <= 0.3 ? 'Budget' : v >= 0.7 ? 'Premium' : 'Balanced'}
            leftLabel="Best price"
            rightLabel="Best quality"
          />
          <div className="mt-4">
            <button
              onClick={() => onUpdate({ preferred_organic: !preferences.preferred_organic })}
              className="w-full flex items-center justify-between px-4 py-3 rounded-lg text-sm transition-all"
              style={{
                background: preferences.preferred_organic ? 'rgba(0,97,160,0.15)' : 'var(--bg-input)',
                border: `1px solid ${preferences.preferred_organic ? '#0061A0' : 'var(--sidebar-border)'}`,
                color: 'var(--text-primary)',
              }}
            >
              <span className="font-medium">Prefer organic produce</span>
              <div
                className="w-9 h-5 rounded-full relative transition-all"
                style={{ background: preferences.preferred_organic ? '#0061A0' : 'var(--sidebar-border)' }}
              >
                <div
                  className="w-3.5 h-3.5 rounded-full bg-white absolute top-[3px] transition-all"
                  style={{ left: preferences.preferred_organic ? 19 : 3 }}
                />
              </div>
            </button>
          </div>
        </Section>

        {/* Budget */}
        <Section title="Budget">
          <div className="space-y-5">
            <SliderField
              label="Budget per meal"
              value={preferences.budget_per_order ?? 80}
              onChange={v => onUpdate({ budget_per_order: v })}
              min={10} max={200} step={5}
              format={v => `$${v}`}
              leftLabel="$10"
              rightLabel="$200"
            />
            <SliderField
              label="Budget per person"
              value={preferences.budget_per_person ?? 20}
              onChange={v => onUpdate({ budget_per_person: v })}
              min={5} max={50} step={2.5}
              format={v => `$${v}`}
              leftLabel="$5"
              rightLabel="$50"
            />
          </div>
        </Section>

        {/* Household & Servings */}
        <Section title="Household">
          <div className="space-y-5">
            <SliderField
              label="Servings per meal"
              value={preferences.serving_size ?? 2}
              onChange={v => onUpdate({ serving_size: v })}
              min={1} max={12} step={1}
              leftLabel="1"
              rightLabel="12"
            />
            <SliderField
              label="Household size"
              value={preferences.household_size ?? 2}
              onChange={v => onUpdate({ household_size: v })}
              min={1} max={10} step={1}
              leftLabel="1"
              rightLabel="10"
            />
          </div>
        </Section>

        {/* Cooking */}
        <Section title="Cooking">
          <div className="space-y-5">
            <SliderField
              label="Max prep + cook time"
              value={preferences.max_prep_time ?? 60}
              onChange={v => onUpdate({ max_prep_time: v })}
              min={10} max={120} step={5}
              format={v => v >= 120 ? 'No limit' : `${v} min`}
              leftLabel="Quick"
              rightLabel="No limit"
            />
            <div>
              <p className="text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>Skill level</p>
              <div className="grid grid-cols-3 gap-2">
                {SKILL_LEVELS.map(({ value, label, desc }) => (
                  <button
                    key={value}
                    onClick={() => onUpdate({ skill_level: value })}
                    className="text-left p-3 rounded-lg transition-all"
                    style={{
                      background: preferences.skill_level === value ? 'rgba(0,97,160,0.15)' : 'var(--bg-input)',
                      border: `1px solid ${preferences.skill_level === value ? '#0061A0' : 'var(--sidebar-border)'}`,
                    }}
                  >
                    <div className="text-sm font-medium" style={{ color: preferences.skill_level === value ? '#fff' : 'var(--text-primary)' }}>
                      {label}
                    </div>
                    <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Section>

        {/* Dietary Restrictions */}
        <Section title="Dietary Restrictions">
          <div className="flex flex-wrap gap-2">
            {DIETARY_OPTIONS.map(option => {
              const active = dietary.includes(option.toLowerCase())
              return (
                <button
                  key={option}
                  onClick={() => toggleDietary(option)}
                  className="text-sm px-3.5 py-2 rounded-lg font-medium transition-all"
                  style={{
                    background: active ? 'rgba(0,97,160,0.2)' : 'transparent',
                    color: active ? '#fff' : 'var(--text-secondary)',
                    border: `1px solid ${active ? '#0061A0' : 'var(--sidebar-border)'}`,
                  }}
                >
                  {active && <span className="mr-1.5">&#10003;</span>}
                  {option}
                </button>
              )
            })}
          </div>
        </Section>

        {/* Disliked Ingredients */}
        <Section title="Disliked Ingredients">
          <p className="text-sm mb-3" style={{ color: 'var(--text-muted)' }}>
            These ingredients will never appear in your cart.
          </p>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={dislikedInput}
              onChange={e => setDislikedInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addDisliked()}
              placeholder="e.g. anchovies, cilantro..."
              className="flex-1 text-sm px-3.5 py-2.5 rounded-lg outline-none"
              style={{
                background: 'var(--bg-input)',
                color: 'var(--text-primary)',
                border: '1px solid var(--sidebar-border)',
              }}
            />
            <button
              onClick={addDisliked}
              className="text-sm px-4 py-2.5 rounded-lg font-medium text-white transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, #0061A0, #0D5E9D)' }}
            >
              Add
            </button>
          </div>
          {disliked.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {disliked.map(item => (
                <span
                  key={item}
                  className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg"
                  style={{ background: 'var(--sidebar-border)', color: 'var(--text-secondary)' }}
                >
                  {item}
                  <button
                    onClick={() => removeDisliked(item)}
                    className="hover:text-white transition-colors text-base leading-none"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    &times;
                  </button>
                </span>
              ))}
            </div>
          )}
        </Section>

        {/* Bottom spacer */}
        <div className="h-4" />
      </div>
    </div>
  )
}
