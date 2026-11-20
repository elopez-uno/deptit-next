"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ActividadesEspecialesModule } from "@/components/actividades-especiales-module";
import { BrandMark, Spinner } from "@/components/brand";
import { ComisionesModule } from "@/components/comisiones-module";
import { ContextSwitcher } from "@/components/context-switcher";
import { ContextoHistorico } from "@/components/contexto-historico";
import { DesignacionesModule } from "@/components/designaciones-module";
import { DocentesModule } from "@/components/docentes-module";
import { ExtensionModule } from "@/components/extension-module";
import { InvestigacionModule } from "@/components/investigacion-module";
import { MateriasModule } from "@/components/materias-module";
import { PeriodosModule } from "@/components/periodos-module";
import { SueldosModule } from "@/components/sueldos-module";
import { DisposicionesModule } from "@/components/disposiciones-module";
import { AnalisisModule } from "@/components/analisis-module";
import { InicioModule } from "@/components/inicio-module";
import { ConsolidadoModule } from "@/components/consolidado-module";
import { SaasModule } from "@/components/saas-module";
import { MovimientosModule } from "@/components/movimientos-module";
import { ResolucionesRespaldosModule } from "@/components/resoluciones-respaldos-module";
import {
  ApiError,
  type Modulo,
  type Session,
  authApi,
  noticeParam,
  roleLabel,
} from "@/lib/auth";

export function AppShell() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [active, setActive] = useState("inicio");
  const [loggingOut, setLoggingOut] = useState(false);

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        const aviso = noticeParam(err.code);
        router.replace(aviso ? `/login?aviso=${aviso}` : "/login");
        return;
      }
      setUnavailable(
        err instanceof ApiError
          ? err.message
          : "No se pudo verificar tu sesión en este momento."
      );
    },
    [router]
  );

  // Revalida la sesión contra el backend (equivale a cada rerun de la app certificada).
  const refresh = useCallback(async () => {
    try {
      const data = await authApi.me();
      setUnavailable(null);
      setSession(data);
      return data;
    } catch (err) {
      handleError(err);
      return null;
    }
  }, [handleError]);

  useEffect(() => {
    let cancelled = false;
    authApi
      .me()
      .then((data) => {
        if (!cancelled) setSession(data);
      })
      .catch((err) => {
        if (!cancelled) handleError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [handleError]);

  async function selectModule(clave: string) {
    setActive(clave);
    const data = await refresh();
    if (data && !data.modulos.some((m) => m.clave === clave)) setActive("inicio");
  }

  async function logout() {
    setLoggingOut(true);
    try {
      await authApi.logout();
    } catch {
      // aunque falle la red, se sale; el backend expira la sesión por tiempo
    }
    router.replace("/login?aviso=cerrada");
  }

  function onContextChanged(data: Session) {
    setSession(data);
    if (!data.modulos.some((m) => m.clave === active)) setActive("inicio");
  }

  if (unavailable && !session) {
    return (
      <CenteredMessage>
        <p className="font-medium text-slate-800">{unavailable}</p>
        <button
          onClick={() => refresh()}
          className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800"
        >
          Reintentar
        </button>
      </CenteredMessage>
    );
  }

  if (!session) {
    return (
      <CenteredMessage>
        <Spinner className="h-6 w-6 text-brand-600" />
        <p className="mt-3 text-sm text-slate-500">Verificando sesión…</p>
      </CenteredMessage>
    );
  }

  const current = session.modulos.find((m) => m.clave === active) ?? session.modulos[0];

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col bg-brand-950 text-brand-100 md:flex">
        <div className="flex items-center gap-3 px-5 py-5">
          <BrandMark className="h-9 w-9" />
          <div className="min-w-0">
            <p className="font-semibold tracking-tight text-white">DEPTIT</p>
            <p className="truncate text-[11px] text-brand-100/60">Gestión académica</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4" aria-label="Módulos">
          {session.modulos.map((m) => (
            <button
              key={m.clave}
              onClick={() => selectModule(m.clave)}
              aria-current={m.clave === current.clave ? "page" : undefined}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition ${
                m.clave === current.clave
                  ? "bg-white/10 font-medium text-white"
                  : "text-brand-100/75 hover:bg-white/5 hover:text-white"
              }`}
            >
              <ModuleBadge nombre={m.nombre} active={m.clave === current.clave} />
              <span className="truncate">{m.nombre}</span>
            </button>
          ))}
        </nav>
        <div className="border-t border-white/10 p-3">
          <button
            onClick={logout}
            disabled={loggingOut}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm text-brand-100/80 transition hover:bg-white/5 hover:text-white disabled:opacity-60"
          >
            {loggingOut && <Spinner />}
            Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-4 border-b border-slate-200 bg-white px-6 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
              {session.contexto.institucion_encabezado}
            </p>
            <h1 className="truncate text-lg font-semibold tracking-tight text-brand-950">
              {current.nombre}
            </h1>
          </div>
          <ContextSwitcher session={session} onChanged={onContextChanged} onError={handleError} />
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-900">
                {session.usuario.nombre || session.usuario.email}
              </p>
              <p className="text-xs text-slate-500">{roleLabel(session.usuario.rol)}</p>
            </div>
            <div className="grid h-9 w-9 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-800">
              {initials(session.usuario.nombre || session.usuario.email)}
            </div>
            <button
              onClick={logout}
              disabled={loggingOut}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
            >
              Cerrar sesión
            </button>
          </div>
        </header>

        {unavailable && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">
            {unavailable}
          </div>
        )}
        {session.usuario.modo_solo_lectura_comercial && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">
            Acceso limitado a solo lectura por estado comercial de la institución.
          </div>
        )}

        <main className="flex-1 px-6 py-8">
          <div className="mx-auto max-w-6xl">
            <ContextoHistorico session={session} />
            {current.clave === "inicio" ? (
              <InicioModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}-${session.contexto.vista}`}
                onAuthError={handleError}
                onNavigate={selectModule}
              />
            ) : current.clave === "consolidado" ? (
              <ConsolidadoModule key={`${session.contexto.institucion?.id}`} onAuthError={handleError} />
            ) : current.clave === "periodos" ? (
              <PeriodosModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "docentes" ? (
              <DocentesModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "designaciones" ? (
              <DesignacionesModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "comisiones" ? (
              <ComisionesModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "investigacion" ? (
              <InvestigacionModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "extension" ? (
              <ExtensionModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "actividades_especiales" ? (
              <ActividadesEspecialesModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "sueldos" ? (
              <SueldosModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "disposiciones" ? (
              <DisposicionesModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "resoluciones_respaldos" ? (
              <ResolucionesRespaldosModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "analisis" ? (
              <AnalisisModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "movimientos" ? (
              <MovimientosModule
                key={`${session.contexto.institucion?.id}-${session.contexto.departamento?.id}`}
                onAuthError={handleError}
              />
            ) : current.clave === "materias" ? (
              <MateriasModule key={`${session.contexto.institucion?.id}`} onAuthError={handleError} />
            ) : current.clave === "administracion_saas" ? (
              <SaasModule onAuthError={handleError} />
            ) : (
              <ModulePlaceholder modulo={current} />
            )}
          </div>
        </main>

        <MobileNav session={session} active={current.clave} onSelect={selectModule} />
      </div>
    </div>
  );
}

function ModulePlaceholder({ modulo }: { modulo: Modulo }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-8 py-16 text-center">
      <div className="mx-auto mb-4 w-fit">
        <ModuleBadge nombre={modulo.nombre} light />
      </div>
      <h2 className="text-xl font-semibold text-brand-950">{modulo.nombre}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
        Este módulo todavía no está disponible en DEPTIT NEXT. Se migrará en un próximo bloque
        conservando el funcionamiento del sistema certificado.
      </p>
      <div className="mt-5 flex justify-center gap-2">
        <Chip tone={modulo.puede_escribir ? "green" : "slate"}>
          {modulo.puede_escribir ? "Tu rol puede editar" : "Tu rol puede consultar"}
        </Chip>
        {modulo.puede_borrar && <Chip tone="amber">Tu rol puede borrar</Chip>}
      </div>
    </div>
  );
}

function MobileNav({
  session,
  active,
  onSelect,
}: {
  session: Session;
  active: string;
  onSelect: (c: string) => void;
}) {
  return (
    <nav className="sticky bottom-0 flex gap-1 overflow-x-auto border-t border-slate-200 bg-white px-2 py-2 md:hidden">
      {session.modulos.map((m) => (
        <button
          key={m.clave}
          onClick={() => onSelect(m.clave)}
          className={`shrink-0 rounded-md px-3 py-1.5 text-xs transition ${
            m.clave === active
              ? "bg-brand-700 font-medium text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {m.nombre}
        </button>
      ))}
    </nav>
  );
}

function Chip({ children, tone }: { children: React.ReactNode; tone: "slate" | "green" | "amber" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function ModuleBadge({ nombre, active, light }: { nombre: string; active?: boolean; light?: boolean }) {
  const cls = light
    ? "bg-brand-50 text-brand-700"
    : active
      ? "bg-brand-500 text-white"
      : "bg-white/10 text-brand-100";
  return (
    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-md text-[11px] font-semibold ${cls}`}>
      {initials(nombre)}
    </span>
  );
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      {children}
    </div>
  );
}

function initials(text: string) {
  return text
    .split(/\s+/)
    .filter((w) => w.length > 2 || /^[A-ZÁÉÍÓÚ]/.test(w))
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}
