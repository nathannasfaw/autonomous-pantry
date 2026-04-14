export default function ClaudeLogo({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect width="48" height="48" rx="12" fill="#0061A0" />
      <g transform="translate(8, 10)">
        {/* Stylized Claude sparkle / asterisk mark */}
        <path
          d="M16 2 L18.5 11.5 L28 9 L20.5 15 L28 21 L18.5 18.5 L16 28 L13.5 18.5 L4 21 L11.5 15 L4 9 L13.5 11.5 Z"
          fill="white"
          opacity="0.95"
        />
      </g>
    </svg>
  )
}
