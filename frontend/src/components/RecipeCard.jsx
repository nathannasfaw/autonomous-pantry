import { useState } from 'react'

const UtensilsIcon = ({ size = 15, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/>
    <path d="M7 2v20"/>
    <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>
  </svg>
)

function RecipeImage({ name, imageUrl }) {
  const [src, setSrc] = useState(imageUrl || null)
  const [failed, setFailed] = useState(false)

  // If LLM image fails or wasn't provided, show a styled placeholder
  if (failed || !src) {
    return (
      <div
        className="w-full h-40 flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #0061A0 0%, #0D5E9D 60%, #1E1F22 100%)',
        }}
      >
        <div className="text-center px-4">
          <UtensilsIcon size={32} className="text-white/60 mx-auto mb-2" />
          <p className="text-white/80 text-sm font-medium">{name}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-40 overflow-hidden">
      <img
        src={src}
        alt={name}
        className="w-full h-full object-cover"
        onError={() => setFailed(true)}
      />
    </div>
  )
}

export default function RecipeCard({ recipe }) {
  if (!recipe) return null
  const { name, servings, prep_time, cook_time, ingredients = [], source_url, image_url } = recipe
  const shown = ingredients.slice(0, 5)
  const remaining = ingredients.length - 5

  return (
    <div className="card-entrance rounded-2xl overflow-hidden w-full"
         style={{ boxShadow: 'var(--shadow-card)', border: '1px solid #3F4147' }}>
      {/* Image thumbnail */}
      <RecipeImage name={name} imageUrl={image_url} />

      {/* Gradient header */}
      <div className="px-4 py-3 flex items-center gap-2" style={{ background: 'var(--card-recipe-header)' }}>
        <UtensilsIcon size={15} className="text-white opacity-90" />
        <div>
          <div className="text-white font-semibold text-sm">{name}</div>
          <div className="text-white/70 text-xs mt-0.5">
            Serves {servings} · Prep {prep_time} · Cook {cook_time}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3" style={{ background: 'var(--bg-card)' }}>
        <div className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
          Ingredients ({ingredients.length})
        </div>
        <ul className="space-y-1">
          {shown.map((ing, i) => (
            <li key={i} className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              · {ing.quantity} {ing.unit} {ing.item}
            </li>
          ))}
          {remaining > 0 && (
            <li className="text-xs italic" style={{ color: 'var(--text-muted)' }}>...and {remaining} more</li>
          )}
        </ul>
        {source_url && (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-3 text-sm font-medium hover:underline"
            style={{ color: '#5B9BD5' }}
          >
            View Full Recipe ↗
          </a>
        )}
      </div>
    </div>
  )
}
