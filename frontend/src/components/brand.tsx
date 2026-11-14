export function BrandMark({ className = "h-10 w-10 text-lg" }: { className?: string }) {
  return (
    <div
      className={`${className} grid place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-800 text-white shadow-lg shadow-brand-900/30`}
      aria-hidden="true"
    >
      <span className="font-bold tracking-tight">D</span>
    </div>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={`${className} animate-spin`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}
