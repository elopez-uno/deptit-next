import Image from "next/image";

// Logo institucional de la Universidad Nacional del Oeste (PNG oficial 297x102, azul #009cd1, fondo blanco).
// Sobre superficies oscuras debe ir dentro de una tarjeta/claro para conservar el contraste del original.
export function UnoLogo({
  className = "h-auto w-[132px]",
  alt = "Universidad Nacional del Oeste",
}: {
  className?: string;
  alt?: string;
}) {
  return (
    <Image
      src="/uno-logo-web.png"
      alt={alt}
      width={297}
      height={102}
      sizes="(max-width: 768px) 180px, 200px"
      className={className}
    />
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
