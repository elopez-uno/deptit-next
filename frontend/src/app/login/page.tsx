import { Suspense } from "react";
import { UnoLogo } from "@/components/brand";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            background:
              "radial-gradient(900px circle at 12% 0%, rgba(0,156,209,0.35), transparent 55%), radial-gradient(700px circle at 90% 100%, rgba(0,100,138,0.35), transparent 55%)",
          }}
        />
        <div className="relative">
          <div className="inline-flex rounded-xl bg-white px-5 py-4 shadow-lg shadow-black/20">
            <UnoLogo className="h-auto w-[180px]" />
          </div>
          <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.3em] text-brand-200/80">
            DEPTIT NEXT
          </p>
        </div>

        <div className="relative max-w-md">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.3em] text-brand-300/80">
            Universidad Nacional del Oeste
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Gestión académica departamental.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-brand-100/75">
            Docentes, designaciones, comisiones y períodos en un solo lugar. Ingresá con tu cuenta
            institucional para continuar.
          </p>
        </div>

        <p className="relative text-xs text-brand-200/70">
          Acceso restringido a personal autorizado · Universidad Nacional del Oeste
        </p>
      </section>

      <section className="flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <UnoLogo className="h-auto w-[170px]" />
          </div>

          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-brand-700">
            DEPTIT NEXT
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-brand-950">Ingresar</h2>
          <p className="mt-2 text-sm text-slate-500">
            Sistema de Gestión Académica Departamental · UNO
          </p>

          <Suspense fallback={<div className="mt-8 h-64" />}>
            <LoginForm />
          </Suspense>

          <p className="mt-10 border-t border-slate-200 pt-5 text-center text-[11px] text-slate-500">
            Universidad Nacional del Oeste
          </p>
        </div>
      </section>
    </main>
  );
}
