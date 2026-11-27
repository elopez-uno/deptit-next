import { Suspense } from "react";
import { BrandLogo } from "@/components/brand";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-brand-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(900px circle at 8% 8%, rgba(47,111,214,0.42), transparent 52%), radial-gradient(800px circle at 95% 88%, rgba(37,99,235,0.28), transparent 52%)",
          }}
        />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -left-24 h-[420px] w-[720px] rotate-[-8deg] rounded-[50%] border-[64px] border-brand-700/20"
        />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-40 left-20 h-[420px] w-[760px] rotate-[-8deg] rounded-[50%] border-[54px] border-brand-500/15"
        />

        <div className="relative">
          <BrandLogo
            variant="light"
            className="h-auto w-[240px]"
          />
        </div>

        <div className="relative max-w-lg">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Gestión departamental en un solo lugar.
          </h1>

          <p className="mt-5 max-w-md text-base leading-relaxed text-brand-100/75">
            Toda la gestión académica de tu departamento, centralizada en una sola plataforma.
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

          <h2 className="text-2xl font-semibold tracking-tight text-brand-950">
            Ingresar
          </h2>

          <p className="mt-2 text-sm text-slate-500">
            Sistema de gestión académica
          </p>

          <Suspense fallback={<div className="mt-8 h-64" />}>
            <LoginForm />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
