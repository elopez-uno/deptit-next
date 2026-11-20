import { Suspense } from "react";
import { BrandLogo } from "@/components/brand";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-900 text-white lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px circle at 10% 10%, rgba(47,111,214,0.45), transparent 55%), radial-gradient(700px circle at 90% 90%, rgba(20,184,166,0.25), transparent 50%)",
          }}
        />
        {/* El logo completo ya contiene "DEPTIT" y "Gestión académica": no se repite en texto. */}
        <div className="relative">
          <div className="inline-flex rounded-2xl bg-white px-6 py-4 shadow-lg shadow-black/20">
            <BrandLogo className="h-auto w-[240px]" />
          </div>
        </div>

        <div className="relative max-w-md">
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
          <div className="mb-10 lg:hidden">
            <BrandLogo className="h-auto w-[220px]" />
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
