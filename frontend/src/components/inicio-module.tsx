"use client";

// Módulo Inicio (B13-FIX02, if modulo == "🏠 Inicio", entry l. 59280-59794): tablero operativo del departamento
// operativo de la sesión sobre el período abierto (sin selector de período ni pestañas). Tres estados: coordinador sin
// departamento (acceso a Consolidado), sin período abierto (acceso a Períodos) y tablero completo. Todo valor, rótulo
// y especificación de gráfico llega ya calculado por el motor certificado del backend; acá solo se presenta. Los
// botones de navegación usan el shell (D-AN5). "🔄 Actualizar tablero" vuelve a pedir el tablero y está habilitado para
// todos los roles (D-AN3). Única descarga: Excel de "Próximos vencimientos" (D-AN6). No hay escrituras.
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { FeedbackBox, type Feedback } from "@/components/module-ui";
import { VegaChart } from "@/components/vega-chart";
import { ApiError } from "@/lib/auth";
import { type Celda, type Metrica, type Tabla, guardarArchivo } from "@/lib/analisis";
import { type Ayuda, type Boton, type Casos, type Grafico, type Inicio, type Lista, type Tablero, InicioError, inicioApi } from "@/lib/inicio";

type Navegar = (clave: string) => void;

// Texto con **negritas** de st.markdown / st.caption ("&nbsp;" de la línea del período).
function Md({ text }: { text: string }) {
  const partes = text.replace(/&nbsp;/g, " ").split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}
    </>
  );
}

// Bloque markdown de la ayuda: una línea por renglón (los vacíos separan párrafos).
function Bloque({ text }: { text: string }) {
  return (
    <div className="space-y-1 text-sm text-slate-700">
      {text.split("\n").map((l, i) => (l.trim() ? <p key={i}><Md text={l} /></p> : <div key={i} className="h-2" />))}
    </div>
  );
}

function Caption({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500">{children}</p>;
}

function H2({ children }: { children: React.ReactNode }) {
  return <h3 className="pt-4 text-xl font-semibold text-slate-900">{children}</h3>;
}

function Tarjeta({ m, borde = false }: { m: Metrica; borde?: boolean }) {
  return (
    <div className={`rounded-xl bg-white px-4 py-3 ${borde ? "border border-slate-200 shadow-sm" : ""}`} data-testid="metrica">
      <p className="text-xs text-slate-500">{m.label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{m.valor}</p>
      {m.caption && <Caption>{m.caption}</Caption>}
    </div>
  );
}

function texto(v: Celda) {
  return v === null || v === undefined ? "" : String(v);
}

function Grilla({ tabla }: { tabla: Tabla }) {
  return (
    <div className="max-h-[28rem] overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
          <tr>{tabla.columnas.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tabla.filas.map((f, i) => (
            <tr key={i}>{f.map((v, j) => <td key={j} className="whitespace-nowrap px-3 py-1.5 text-slate-700">{texto(v)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Expander({ titulo, abierto = false, children }: { titulo: string; abierto?: boolean; children: React.ReactNode }) {
  return (
    <details open={abierto} className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800 transition hover:bg-brand-50/50">{titulo}</summary>
      <div className="space-y-3 border-t border-slate-100 px-5 py-4">{children}</div>
    </details>
  );
}

function Progreso({ valor, label }: { valor: number; label: string }) {
  const pct = Math.max(0, Math.min(100, valor * 100));
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
      <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
    </div>
  );
}

function BotonNav({ b, onNavigate, ancho = false }: { b: Boton; onNavigate: Navegar; ancho?: boolean }) {
  const cls = b.primario
    ? "bg-brand-700 text-white shadow-sm hover:bg-brand-800"
    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50";
  return (
    <button type="button" onClick={() => onNavigate(b.destino)} className={`rounded-lg px-4 py-2 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/30 ${cls} ${ancho ? "w-full" : ""}`}>
      {b.label}
    </button>
  );
}

function CasosView({ c }: { c: Casos }) {
  return (
    <>
      {c.tabla && <Grilla tabla={c.tabla} />}
      <Caption>{c.caption}</Caption>
    </>
  );
}

function AyudaView({ a }: { a: Ayuda }) {
  return (
    <Expander titulo={a.titulo} abierto={a.abierto}>
      <Bloque text={a.texto} />
    </Expander>
  );
}

function ListaView({ l }: { l: Lista }) {
  return (
    <Expander titulo={l.titulo}>
      {l.vacio && <Caption>{l.vacio}</Caption>}
      {l.personas.map((p, i) => (
        <div key={i} className="space-y-1 rounded-xl border border-slate-200 px-4 py-3">
          <p className="text-sm text-slate-800"><Md text={p.encabezado} /></p>
          {p.designaciones.map((d, j) => (
            <div key={j} className={`space-y-1 ${j < p.designaciones.length - 1 ? "border-b border-slate-100 pb-2" : ""}`}>
              <p className="text-sm text-slate-700"><Md text={d.linea} /></p>
              {d.funciones && <p className="text-sm text-slate-700"><Md text={d.funciones} /></p>}
              <Caption>{d.caption}</Caption>
            </div>
          ))}
        </div>
      ))}
    </Expander>
  );
}

function GraficoView({ g }: { g: Grafico }) {
  return (
    <div className="space-y-2">
      <h4 className="text-base font-semibold text-slate-800">{g.titulo}</h4>
      {g.vacio || !g.spec ? <FeedbackBox feedback={{ tone: "info", text: g.mensaje ?? "Todavía no hay datos para graficar." }} /> : <VegaChart spec={g.spec} label={g.titulo} />}
      <Caption>{g.caption}</Caption>
    </div>
  );
}

function TableroView({ t, onNavigate, onRefresh, refrescando, onError }: { t: Tablero; onNavigate: Navegar; onRefresh: () => void; refrescando: boolean; onError: (e: unknown) => ApiError }) {
  const [excel, setExcel] = useState(false);
  const [aviso, setAviso] = useState<Feedback>(null);

  async function bajarExcel() {
    setExcel(true);
    setAviso(null);
    try {
      guardarArchivo(await inicioApi.excelVencimientos());
    } catch (e) {
      const err = onError(e);
      const tone = (err as InicioError).tone;
      setAviso({ tone: tone === "info" ? "info" : tone === "warning" ? "warning" : "error", text: err.message });
    } finally {
      setExcel(false);
    }
  }

  const p = t.periodo;
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-700"><Md text={p.linea} /></p>
      {p.progreso !== null && (
        <div className="space-y-1">
          <Progreso valor={p.progreso} label="Avance calendario del período" />
          {p.caption_progreso && <Caption>{p.caption_progreso}</Caption>}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-4">
        <button type="button" onClick={onRefresh} disabled={refrescando} className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60">
          {refrescando && <Spinner />}
          {p.actualizar.label}
        </button>
        <div className="min-w-0 flex-1"><Caption>{p.actualizar.caption}</Caption></div>
      </div>
      {t.error && <FeedbackBox feedback={{ tone: "error", text: t.error }} />}

      {t.situacion && (
        <section className="space-y-3">
          <H2>{t.situacion.titulo}</H2>
          <div className="grid gap-3 md:grid-cols-5">{t.situacion.tarjetas.map((m) => <Tarjeta key={m.label} m={m} borde />)}</div>
          <Caption>{t.situacion.caption_dotacion}</Caption>
          {t.situacion.listas.map((l) => <ListaView key={l.titulo} l={l} />)}
        </section>
      )}

      {t.acciones && (
        <section className="space-y-3">
          <H2>{t.acciones.titulo}</H2>
          {t.acciones.vacio ? (
            <FeedbackBox feedback={{ tone: "success", text: t.acciones.vacio }} />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {t.acciones.items.map((a) => (
                <div key={a.titulo} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h4 className="text-lg font-semibold text-slate-900">{a.icono} {a.titulo}</h4>
                  <p className="text-sm text-slate-700">{a.detalle}</p>
                  <Expander titulo={a.expander}><CasosView c={a.casos} /></Expander>
                  <BotonNav b={a.boton} onNavigate={onNavigate} ancho />
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {t.salud && (
        <section className="space-y-3">
          <H2>{t.salud.titulo}</H2>
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <Caption>{t.salud.caption}</Caption>
            {t.salud.controles.map((c) => <Expander key={c.titulo} titulo={c.titulo}><CasosView c={c.casos} /></Expander>)}
            <hr className="border-slate-200" />
            <p className="text-sm text-slate-800"><Md text={t.salud.estado_general} /></p>
            <Progreso valor={t.salud.porcentaje / 100} label="Estado general del período" />
            <Caption>{t.salud.caption_indice}</Caption>
            <BotonNav b={t.salud.boton} onNavigate={onNavigate} />
          </div>
        </section>
      )}

      {t.indicadores && (
        <section className="space-y-3">
          <H2>{t.indicadores.titulo}</H2>
          {t.indicadores.filas.map((fila, i) => (
            <div key={i} className={`grid gap-3 ${fila.length === 6 ? "md:grid-cols-6" : "md:grid-cols-5"}`}>
              {fila.map((m) => <Tarjeta key={m.label} m={m} />)}
            </div>
          ))}
        </section>
      )}

      {t.graficos && (
        <section className="grid gap-6 md:grid-cols-2">
          {t.graficos.map((g) => <GraficoView key={g.titulo} g={g} />)}
        </section>
      )}

      {t.vencimientos && (
        <section className="space-y-3">
          <H2>{t.vencimientos.titulo}</H2>
          {t.vencimientos.vacio ? (
            <FeedbackBox feedback={{ tone: "success", text: t.vencimientos.vacio }} />
          ) : (
            <>
              {t.vencimientos.tabla && <Grilla tabla={t.vencimientos.tabla} />}
              {t.vencimientos.excel && (
                <button type="button" onClick={bajarExcel} disabled={excel} className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60">
                  {excel && <Spinner />}
                  📥 Descargar tabla en Excel
                </button>
              )}
              {aviso && <FeedbackBox feedback={aviso} />}
              {t.vencimientos.boton && <BotonNav b={t.vencimientos.boton} onNavigate={onNavigate} />}
            </>
          )}
        </section>
      )}

      {t.ayuda && <AyudaView a={t.ayuda} />}
    </div>
  );
}

export function InicioModule({ onAuthError, onNavigate }: { onAuthError: (e: ApiError) => void; onNavigate: Navegar }) {
  const [data, setData] = useState<Inicio | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);

  const handle = useCallback(
    (err: unknown): ApiError => {
      const e = err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
      if (e.status === 401) onAuthError(e);
      return e;
    },
    [onAuthError]
  );

  useEffect(() => {
    let cancel = false;
    inicioApi
      .tablero()
      .then((d) => {
        if (cancel) return;
        setData(d);
        setError(null);
      })
      .catch((e) => !cancel && setError(handle(e)))
      .finally(() => !cancel && setCargando(false));
    return () => {
      cancel = true;
    };
  }, [handle, version]);

  // "🔄 Actualizar tablero" (D-AN3): vuelve a pedir el tablero; no escribe nada.
  function refrescar() {
    setCargando(true);
    setVersion((v) => v + 1);
  }

  if (cargando && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando el tablero de Inicio…
      </div>
    );
  }
  if (error && !data) {
    const scope = error.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{error.message}</p>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div>
        {data.contexto.institucion && (
          <p className="text-sm text-slate-500">
            {data.contexto.institucion.nombre}
            {data.contexto.departamento ? ` · ${data.contexto.departamento.nombre}` : ""}
          </p>
        )}
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">{data.titulo}</h2>
      </div>
      {error && <FeedbackBox feedback={{ tone: "error", text: error.message }} />}
      {data.estado === "institucional" && (
        <div className="space-y-3">
          <FeedbackBox feedback={{ tone: "info", text: data.institucional.mensaje.replace(/\*\*/g, "") }} />
          <BotonNav b={data.institucional.boton} onNavigate={onNavigate} />
        </div>
      )}
      {data.estado === "sin_periodo" && (
        <div className="space-y-3">
          <FeedbackBox feedback={{ tone: "warning", text: data.sin_periodo.mensaje }} />
          <BotonNav b={data.sin_periodo.boton} onNavigate={onNavigate} />
          <AyudaView a={data.sin_periodo.ayuda} />
        </div>
      )}
      {data.estado === "tablero" && <TableroView t={data.tablero} onNavigate={onNavigate} onRefresh={refrescar} refrescando={cargando} onError={handle} />}
    </div>
  );
}
