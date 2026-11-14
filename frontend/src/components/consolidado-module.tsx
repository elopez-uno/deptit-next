"use client";

// Módulo Consolidado institucional (B13-FIX02 render_consolidado_institucional v242, entry l. 53184). Misma página:
// título, 4 métricas, caption de fuente, "🔎 Control de consistencia" abierto, "Resumen por departamento", "Ver datos
// consolidados" con el selector "Tabla" (9 claves certificadas), buscador por tabla, tabla, "Descargar CSV consolidado"
// (tabla COMPLETA) y el Excel global bajo cada tabla mostrada (vista filtrada). Sin gráficos, sin navegación propia y
// sin escrituras. La institución la decide la sesión; cada tabla se pide al elegirla (D-AO3).
import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { FeedbackBox } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type Celda, type Metrica, type Tabla, guardarArchivo } from "@/lib/analisis";
import { type Archivo, type Consolidado, type TablaVisor, consolidadoApi } from "@/lib/consolidado";

type Tablero = Extract<Consolidado, { estado: "tablero" }>;
type OnError = (err: unknown) => ApiError;

function Md({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}
    </>
  );
}

function Caption({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500">{children}</p>;
}

function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="pt-4 text-xl font-semibold text-slate-900">{children}</h3>;
}

function Tarjetas({ items }: { items: Metrica[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {items.map((m, i) => (
        <div key={i} className="rounded-xl bg-white px-4 py-3" data-testid="metrica">
          <p className="text-xs text-slate-500">{m.label}</p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">{m.valor}</p>
        </div>
      ))}
    </div>
  );
}

function texto(v: Celda) {
  return v === null || v === undefined ? "" : String(v);
}

function Grilla({ tabla, label }: { tabla: Tabla; label: string }) {
  return (
    <div className="max-h-[28rem] overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table aria-label={label} className="min-w-full text-left text-sm">
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

function BotonDescarga({ label, onClick }: { label: string; onClick: () => Promise<void> }) {
  const [ocupado, setOcupado] = useState(false);
  async function click() {
    setOcupado(true);
    try {
      await onClick();
    } finally {
      setOcupado(false);
    }
  }
  return (
    <button type="button" onClick={click} disabled={ocupado} className="flex w-fit items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60">
      {ocupado && <Spinner />}
      {label}
    </button>
  );
}

// Excel global certificado (wrapper v191/v200 bajo cada st.dataframe): misma convención que Inicio y Designaciones.
const EXCEL = "📥 Descargar tabla en Excel";

function Visor({ v, onError, descargar }: { v: Tablero["visor"]; onError: OnError; descargar: (f: () => Promise<Archivo>) => Promise<void> }) {
  const [clave, setClave] = useState(v.default);
  const [textos, setTextos] = useState<Record<string, string>>({}); // texto por tabla (key consol_buscar_{tabla})
  const [aplicados, setAplicados] = useState<Record<string, string>>({});
  const [datos, setDatos] = useState<TablaVisor | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const aplicado = aplicados[clave] ?? "";

  useEffect(() => {
    let cancel = false;
    consolidadoApi
      .tabla(clave, aplicado)
      .then((d) => {
        if (cancel) return;
        setDatos(d);
        setError(null);
      })
      .catch((e) => {
        if (cancel) return;
        setDatos(null);
        setError(onError(e).message);
      })
      .finally(() => !cancel && setCargando(false));
    return () => {
      cancel = true;
    };
  }, [clave, aplicado, onError]);

  function elegir(nueva: string) {
    setCargando(true);
    setClave(nueva);
  }

  // como st.text_input: el texto se aplica al confirmar (Enter) o al salir del campo
  function aplicar() {
    const t = textos[clave] ?? "";
    if (t === aplicado) return;
    setCargando(true);
    setAplicados((a) => ({ ...a, [clave]: t }));
  }

  // la tabla en pantalla se conserva mientras se recarga la MISMA tabla (el buscador no se desmonta ni pierde el foco)
  const actual = datos && datos.tabla === clave ? datos : null;

  return (
    <div className="space-y-3">
      <H3>{v.titulo}</H3>
      <label className="block max-w-md text-sm text-slate-700">
        <span className="mb-1 block">{v.label}</span>
        <select value={clave} onChange={(e) => elegir(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          {v.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </label>
      {cargando && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4 text-brand-600" />
          Cargando la tabla…
        </div>
      )}
      {error && !cargando && <FeedbackBox feedback={{ tone: "error", text: error }} />}
      {actual && actual.vacio && <FeedbackBox feedback={{ tone: "info", text: actual.mensaje }} />}
      {actual && !actual.vacio && (
        <div className="space-y-3">
          <label className="block text-sm text-slate-700" title={v.buscador.help}>
            <span className="mb-1 block">{v.buscador.label}</span>
            <input
              type="text"
              value={textos[clave] ?? ""}
              placeholder={v.buscador.placeholder}
              onChange={(e) => setTextos((t) => ({ ...t, [clave]: e.target.value }))}
              onKeyDown={(e) => e.key === "Enter" && aplicar()}
              onBlur={aplicar}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            />
          </label>
          {actual.caption && <Caption>{actual.caption}</Caption>}
          {actual.sin_coincidencias ? (
            <FeedbackBox feedback={{ tone: "info", text: actual.sin_coincidencias }} />
          ) : (
            actual.datos && (
              <>
                <Grilla tabla={actual.datos} label={`Tabla ${clave}`} />
                {actual.excel && <BotonDescarga label={EXCEL} onClick={() => descargar(() => consolidadoApi.excel(clave, actual.busqueda))} />}
              </>
            )
          )}
          <BotonDescarga label={v.csv} onClick={() => descargar(() => consolidadoApi.csv(clave))} />
        </div>
      )}
    </div>
  );
}

export function ConsolidadoModule({ onAuthError }: { onAuthError: (e: ApiError) => void }) {
  const [data, setData] = useState<Consolidado | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

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
    consolidadoApi
      .overview()
      .then((d) => !cancel && setData(d))
      .catch((e) => !cancel && setError(handle(e)))
      .finally(() => !cancel && setCargando(false));
    return () => {
      cancel = true;
    };
  }, [handle]);

  const descargar = useCallback(
    async (fn: () => Promise<Archivo>) => {
      setAviso(null);
      try {
        guardarArchivo(await fn());
      } catch (e) {
        setAviso(handle(e).message);
      }
    },
    [handle]
  );

  if (cargando) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando el Consolidado institucional…
      </div>
    );
  }
  if (error || !data) {
    const scope = error?.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{error?.message ?? "No se pudo completar la operación."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        {data.contexto.institucion && <p className="text-sm text-slate-500">{data.contexto.institucion.nombre}</p>}
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">{data.titulo}</h2>
      </div>
      {aviso && <FeedbackBox feedback={{ tone: "error", text: aviso }} />}
      {data.estado === "sin_datos" ? (
        <FeedbackBox feedback={{ tone: "info", text: data.mensaje }} />
      ) : (
        <>
          <Tarjetas items={data.metricas} />
          <Caption><Md text={data.caption} /></Caption>
          <details open={data.control.abierto} className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">{data.control.titulo}</summary>
            <div className="space-y-3 border-t border-slate-100 px-5 py-4">
              <Tarjetas items={data.control.metricas} />
              <Caption>{data.control.caption}</Caption>
            </div>
          </details>
          <H3>{data.resumen.titulo}</H3>
          <Grilla tabla={data.resumen.tabla} label={data.resumen.titulo} />
          {data.resumen.excel && <BotonDescarga label={EXCEL} onClick={() => descargar(() => consolidadoApi.excel("resumen", null))} />}
          <Visor v={data.visor} onError={handle} descargar={descargar} />
        </>
      )}
    </div>
  );
}
