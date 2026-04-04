const UtensilsIcon = ({ size = 15, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/>
    <path d="M7 2v20"/>
    <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>
  </svg>
)

export default function RecipeCard({ recipe }) {
  if (!recipe) return null
  const { name, servings, prep_time, cook_time, ingredients = [], source_url } = recipe
  const shown = ingredients.slice(0, 5)
  const remaining = ingredients.length - 5

  return (
    <div className="card-entrance rounded-2xl overflow-hidden border border-gray-100 w-full max-w-sm"
         style={{ boxShadow: 'var(--shadow-card)' }}>
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
      <div className="bg-white px-4 py-3">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Ingredients ({ingredients.length})
        </div>
        <ul className="space-y-1">
          {shown.map((ing, i) => (
            <li key={i} className="text-sm text-gray-700">
              · {ing.quantity} {ing.unit} {ing.item}
            </li>
          ))}
          {remaining > 0 && (
            <li className="text-xs text-gray-400 italic">...and {remaining} more</li>
          )}
        </ul>
        {source_url && (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-3 text-sm text-purple-600 font-medium hover:underline"
          >
            View Full Recipe ↗
          </a>
        )}
      </div>
    </div>
  )
}
