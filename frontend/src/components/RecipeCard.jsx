import { useState } from 'react'

const UtensilsIcon = ({ size = 15, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/>
    <path d="M7 2v20"/>
    <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>
  </svg>
)

function RecipeImage({ name, imageUrl, onFail }) {
  return (
    <div className="w-full h-40 overflow-hidden">
      <img
        src={imageUrl}
        alt={name}
        className="w-full h-full object-cover"
        onError={onFail}
      />
    </div>
  )
}

function RecipeFallbackVisual() {
  return (
    <div
      className="w-full h-28 flex items-center justify-center overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, rgba(0,97,160,0.15) 0%, rgba(13,94,157,0.08) 50%, var(--bg-card) 100%)',
      }}
    >
      <div className="flex items-center gap-4 opacity-30">
        <span className="text-3xl">🍽</span>
        <span className="text-3xl">🥘</span>
        <span className="text-3xl">🧑‍🍳</span>
      </div>
    </div>
  )
}

export default function RecipeCard({ recipe }) {
  if (!recipe) return null
  const { name, servings, prep_time, cook_time, ingredients = [], source_url, image_url } = recipe
  const shown = ingredients.slice(0, 5)
  const remaining = ingredients.length - 5
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = image_url && !imageFailed

  return (
    <div className="card-entrance rounded-2xl overflow-hidden w-full"
         style={{ boxShadow: 'var(--shadow-card)', border: '1px solid var(--sidebar-border)' }}>
      {showImage ? (
        <RecipeImage name={name} imageUrl={image_url} onFail={() => setImageFailed(true)} />
      ) : (
        <RecipeFallbackVisual />
      )}

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
