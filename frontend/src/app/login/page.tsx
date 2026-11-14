import { Suspense } from "react";
import { BrandMark } from "@/components/brand";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-900 text-white lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px circle at 10% 10%, rgba(47,111,214,0.45), transparent 55%), radial-gradient(700px circle at 90% 90%, rgba(20,184,166,0.25), transparent 50%)",
          }}
        />
        <div className="relative flex items-center gap-3">
          <BrandMark className="h-11 w-11 text-xl" />
          <div>
            <p className="text-lg font-semibold tracking-tight">DEPTIT</p>
            <p className="text-xs text-brand-100/70">Gestión académica departamental</p>
          </div>
        </div>

        <div className="relative max-w-md">
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.3em] text-brand-100/70">
            DEPTIT — Gestión académica
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Docentes, designaciones y períodos en un solo lugar.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-brand-100/75">
            La nueva plataforma de gestión departamental. Ingresá con tu cuenta institucional para
            continuar.
          </p>
        </div>

        <p className="relative text-xs text-brand-100/50">
          Acceso restringido a personal autorizado.
        </p>
      </section>

      <section className="flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <BrandMark />
            <div>
              <p className="font-semibold tracking-tight">DEPTIT</p>
              <p className="text-xs text-slate-500">Gestión académica</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-brand-950">Ingresar</h2>
          <p className="mt-2 text-sm text-slate-500">Sistema de gestión académica</p>

          <Suspense fallback={<div className="mt-8 h-64" />}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
