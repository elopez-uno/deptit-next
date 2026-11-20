import Image from "next/image";

// Identidad DEPTIT (neutral / multiinstitucional). Los PNG de /public/branding se sirven tal cual (`unoptimized`):
// sin recodificar, recortar ni redimensionar en el servidor. Ambos tienen fondo transparente y trazos navy, por lo
// que sobre superficies oscuras van dentro de una base clara para conservar el contraste del original.
export const DEPTIT_LOGO_SRC = "/branding/deptit-logo-completo.png";
export const DEPTIT_ICONO_SRC = "/branding/deptit-icono.png";

// Logo completo (isotipo + "DEPTIT" + "Gestión académica"): login y superficies amplias.
export function BrandLogo({ className = "h-auto w-[200px]" }: { className?: string }) {
  return (
    <Image
      src={DEPTIT_LOGO_SRC}
      alt="DEPTIT — Gestión académica"
      width={2172}
      height={724}
      unoptimized
      preload
      className={className}
    />
  );
}

// Isotipo DEPTIT sobre base clara: sidebar, encabezados compactos y demás superficies pequeñas.
export function BrandMark({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <div
      className={`${className} grid shrink-0 place-items-center rounded-xl bg-white p-1.5 shadow-lg shadow-brand-900/30`}
    >
      <Image
        src={DEPTIT_ICONO_SRC}
        alt="DEPTIT"
        width={609}
        height={724}
        unoptimized
        className="h-full w-auto object-contain"
      />
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
