"use client";

// Módulo Análisis — incluye Productividad (B13-FIX02, elif modulo == "📊 Análisis", entry l. 66604-67763): selector
// "Período a analizar", expander "⚙️ Parámetro de horas no lectivas" y las 5 pestañas certificadas (la 5.ª con sus 3
// subpestañas). Todos los valores, rótulos y especificaciones de gráficos llegan ya calculados por el motor
// certificado del backend: acá solo se presentan. Productividad NO es un módulo aparte (D-AM1). No hay llamada a
// ninguna IA (D-AM9). La UI oculta "Guardar" sin permiso (D-AM4); FastAPI vuelve a autorizar todo.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/brand";
import { Field, FeedbackBox, PrimaryButton, Select, type Feedback } from "@/components/module-ui";
import { VegaChart } from "@/components/vega-chart";
import { ApiError } from "@/lib/auth";
import {
  type Celda,
  type Comparacion,
  type Metrica,
  type Overview,
  type Periodo,
  type Seccion,
  type Tabla,
  type Torta,
  AnalisisError,
  analisisApi,
  descargar,
  guardarArchivo,
  type Archivo,
} from "@/lib/analisis";

type OnError = (e: unknown) => ApiError;

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Texto con **negritas** de st.caption / st.markdown (sin HTML del servidor; "&nbsp;" de la leyenda certificada).
function Md({ text }: { text: string }) {
  const partes = text.replace(/&nbsp;/g, " ").split(/(\*\*[^*]+\*\*)/g);
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
  return <h3 className="pt-2 text-lg font-semibold text-slate-800">{children}</h3>;
}

function H4({ children }: { children: React.ReactNode }) {
  return <h4 className="pt-1 text-base font-semibold text-slate-800">{children}</h4>;
}

// st.metric: delta en verde si es positivo (rojo si negativo); "inverse" invierte; "off" gris.
function Tarjeta({ m }: { m: Metrica }) {
  const negativo = (m.delta ?? "").trim().startsWith("-");
  const color =
    m.delta_color === "off"
      ? "text-slate-500"
      : (m.delta_color === "inverse" ? !negativo : negativo)
        ? "text-red-600"
        : "text-emerald-600";
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm" data-testid="metrica">
      <p className="text-xs text-slate-500">{m.label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{m.valor}</p>
      {m.delta && (
        <p className={`text-xs font-medium ${color}`}>
          {m.delta_color === "off" ? "" : negativo ? "↓ " : "↑ "}
          {m.delta}
        </p>
      )}
      {m.caption && <Caption>{m.caption}</Caption>}
    </div>
  );
}

function Tarjetas({ items, cols }: { items: Metrica[]; cols?: number }) {
  const grid = { 2: "md:grid-cols-2", 3: "md:grid-cols-3", 4: "md:grid-cols-4", 5: "md:grid-cols-5" }[cols ?? items.length] ?? "md:grid-cols-4";
  return <div className={`grid gap-3 ${grid}`}>{items.map((m, i) => <Tarjeta key={`${m.label}-${i}`} m={m} />)}</div>;
}

function texto(v: Celda) {
  return v === null || v === undefined ? "" : String(v);
}

function Grilla({ tabla, maxHeight = "max-h-[28rem]" }: { tabla: Tabla; maxHeight?: string }) {
  return (
    <div className={`overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm ${maxHeight}`}>
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

function TortaView({ t }: { t: Torta }) {
  return (
    <div className="space-y-2">
      {t.titulo && <p className="text-sm font-semibold text-slate-800">{t.titulo}</p>}
      {t.vacio || !t.spec ? <FeedbackBox feedback={{ tone: "info", text: t.mensaje ?? "No hay datos para graficar." }} /> : <VegaChart spec={t.spec} label={t.titulo ?? "Torta"} />}
    </div>
  );
}

function Info({ text, tone = "info" }: { text: string; tone?: "info" | "warning" | "success" | "error" }) {
  return (
    <div className="whitespace-pre-line">
      <FeedbackBox feedback={{ tone, text }} />
    </div>
  );
}

function Expander({ titulo, abierto = false, children }: { titulo: string; abierto?: boolean; children: React.ReactNode }) {
  return (
    <details open={abierto} className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">{titulo}</summary>
      <div className="space-y-3 border-t border-slate-100 px-5 py-4">{children}</div>
    </details>
  );
}

function Multiselect({ label, opciones, valor, onChange }: { label: string; opciones: string[]; valor: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <div role="group" aria-label={label} className="flex flex-wrap gap-2">
        {opciones.map((o) => {
          const activo = valor.includes(o);
          return (
            <button
              key={o}
              type="button"
              aria-pressed={activo}
              onClick={() => onChange(activo ? valor.filter((x) => x !== o) : opciones.filter((x) => x === o || valor.includes(x)))}
              className={`rounded-full px-3 py-1 text-xs font-medium ${activo ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
            >
              {o}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function useDescarga(onError: OnError) {
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function bajar(clave: string, ruta: "word" | "indicador" | "alertas" | "prompt", body: unknown, guardar = true): Promise<Archivo | null> {
    setBusy(clave);
    setFeedback(null);
    try {
      const archivo = await descargar(ruta, body);
      if (guardar) guardarArchivo(archivo);
      return archivo;
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
      return null;
    } finally {
      setBusy(null);
    }
  }
  return { busy, feedback, bajar };
}

// ------------------------------------------------------------------ 📌 Dashboard de dotación
function Dashboard({ d }: { d: Periodo["dashboard"] }) {
  return (
    <div className="space-y-4">
      <H3>{d.subtitulo}</H3>
      <H4>Dotación por función</H4>
      <Tarjetas items={d.dotacion.slice(0, 3)} cols={3} />
      <Caption>{d.caption_dotacion}</Caption>
      <Tarjetas items={d.dotacion.slice(3, 6)} cols={3} />
      <Tarjetas items={d.dotacion.slice(6, 9)} cols={3} />
      <H4>Operación académica</H4>
      <Tarjetas items={d.operacion} cols={4} />
      <p className="text-sm font-semibold text-slate-800">Alumnos por docente según combinación real de asignaturas</p>
      <Caption>
        Las combinaciones se toman directamente de las comisiones cargadas. Si una misma combinación tiene varias comisiones, los alumnos de sus
        códigos se cuentan una sola vez y se comparan con todos los docentes únicos que participan en cualquiera de esas comisiones.
      </Caption>
      {d.grupos ? <Grilla tabla={d.grupos} /> : <Info text="No hay combinaciones de comisiones con asignaturas disponibles para este período." />}
      <hr className="border-slate-200" />
      <H4>Horas contratadas y horas asignadas · consolidado</H4>
      <Tarjetas items={d.horas.slice(0, 4)} cols={4} />
      <Tarjetas items={d.horas.slice(4)} cols={5} />
      <Caption>{d.caption_horas}</Caption>
      <div className="grid gap-4 md:grid-cols-2">
        <TortaView t={d.torta_horas} />
        <TortaView t={d.torta_comisiones} />
      </div>
      <H4>Resumen tabular</H4>
      <Grilla tabla={d.resumen} />
    </div>
  );
}

// ------------------------------------------------------------------ 👥 Plantel / dotación
function Conteos({ s, titulos }: { s: Seccion; titulos: [string, string, string] }) {
  if (!s.cargos || !s.dedicaciones || !s.tipos) return null;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {[s.cargos, s.dedicaciones, s.tipos].map((c, i) => (
        <div key={titulos[i]} className="space-y-2">
          <p className="text-sm font-semibold text-slate-800">{titulos[i]}</p>
          <Grilla tabla={c.tabla} maxHeight="max-h-64" />
          <TortaView t={c.torta} />
        </div>
      ))}
    </div>
  );
}

function Plantel({ d }: { d: Periodo["plantel"] }) {
  return (
    <div className="space-y-4">
      <H3>{d.subtitulo}</H3>
      <Caption>{d.caption}</Caption>
      <H4>A. Funciones docentes</H4>
      <Tarjetas items={d.a.metricas} cols={4} />
      {d.a.horas && <Tarjetas items={[d.a.horas]} cols={4} />}
      {d.a.vacio ? (
        <Info text={d.a.vacio} />
      ) : (
        <>
          <Conteos s={d.a} titulos={["Cargos docentes", "Dedicaciones docentes", "Tipos de designación docente"]} />
          <p className="text-sm font-semibold text-slate-800">{d.a.titulo_tabla}</p>
          {d.a.tabla && <Grilla tabla={d.a.tabla} />}
        </>
      )}
      <hr className="border-slate-200" />
      <H4>B. Funciones no docentes</H4>
      <Tarjetas items={d.b.metricas} cols={5} />
      {d.b.vacio ? <Info text={d.b.vacio} /> : d.b.tabla && <Grilla tabla={d.b.tabla} />}
      <hr className="border-slate-200" />
      <H4>C. Consolidado total · docencia + funciones no docentes</H4>
      <Tarjetas items={d.c.metricas} cols={5} />
      {d.c.caption && <Caption>{d.c.caption}</Caption>}
      {d.c.tabla && (
        <>
          <Conteos s={d.c} titulos={["Cargos · total", "Dedicaciones · total", "Tipos de designación · total"]} />
          <p className="text-sm font-semibold text-slate-800">Todas las designaciones activas</p>
          <Grilla tabla={d.c.tabla} />
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 🔄 Movimiento docente
function Movimiento({ d, periodo, onError }: { d: Periodo["movimiento"]; periodo: string; onError: OnError }) {
  const [indicador, setIndicador] = useState(d.indicador_default ?? "Altas designaciones");
  const [word, setWord] = useState<{ archivo: Archivo; segundos: number } | null>(null);
  const desc = useDescarga(onError);
  const ind = d.indicadores?.[indicador];
  async function preparar() {
    const t = performance.now();
    const archivo = await desc.bajar("word", "word", { periodo }, false);
    if (archivo) setWord({ archivo, segundos: (performance.now() - t) / 1000 });
  }
  return (
    <div className="space-y-4">
      <H3>{d.subtitulo}</H3>
      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton tone="secondary" busy={desc.busy === "word"} onClick={() => void preparar()}>
          📄 Preparar informe Word del movimiento docente
        </PrimaryButton>
        {word && (
          <PrimaryButton onClick={() => guardarArchivo(word.archivo)}>⬇️ Descargar informe Word preparado</PrimaryButton>
        )}
      </div>
      {word && <Caption>{`Informe preparado en ${word.segundos.toFixed(2)} s. Se reutiliza hasta que cambien datos del sistema.`}</Caption>}
      {desc.feedback && <FeedbackBox feedback={desc.feedback} />}
      {d.vacio ? (
        <Info text={d.vacio} />
      ) : (
        <>
          <H4>Resumen unitario</H4>
          <Tarjetas items={(d.unitario ?? []).slice(0, 4)} cols={4} />
          <Tarjetas items={(d.unitario ?? []).slice(4)} cols={3} />
          <H4>Balance de horas</H4>
          <Tarjetas items={d.balance ?? []} cols={5} />
          {d.caption_balance && <Caption>{d.caption_balance}</Caption>}
          <H4>Ver el detalle de un indicador</H4>
          <div role="radiogroup" aria-label="Indicador" className="flex flex-wrap gap-2">
            {Object.keys(d.indicadores ?? {}).map((k) => (
              <button
                key={k}
                type="button"
                role="radio"
                aria-checked={indicador === k}
                onClick={() => setIndicador(k)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${indicador === k ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
              >
                {k}
              </button>
            ))}
          </div>
          {ind && (
            <>
              <Caption>
                <Md text={ind.caption} />
              </Caption>
              {ind.vacio || !ind.tabla ? (
                <Info text={ind.vacio ?? ""} />
              ) : (
                <>
                  <Grilla tabla={ind.tabla} />
                  <PrimaryButton
                    tone="secondary"
                    busy={desc.busy === "indicador"}
                    onClick={() => void desc.bajar("indicador", "indicador", { periodo, indicador })}
                  >
                    ⬇️ Descargar detalle del indicador seleccionado
                  </PrimaryButton>
                </>
              )}
            </>
          )}
        </>
      )}
      <hr className="border-slate-200" />
      <h3 className="text-xl font-semibold text-slate-800">Balance contra el mismo semestre del año anterior</h3>
      {d.anterior ? (
        <>
          <Caption>{d.anterior.caption}</Caption>
          <Grilla tabla={d.anterior.tabla} />
        </>
      ) : (
        <Info text={d.vacio_anterior} />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 🤖 Análisis automático / IA
const SEMAFORO: Record<string, string> = {
  rojo: "bg-[#b91c1c] text-white font-bold",
  amarillo: "bg-[#facc15] text-[#111827] font-bold",
  verde: "bg-[#15803d] text-white font-bold",
  azul: "bg-[#2563eb] text-white font-bold",
};
const GRAVEDADES = ["Alta", "Media", "Baja"];

function Automatico({ d, periodo, leyenda, onError }: { d: Periodo["automatico"]; periodo: string; leyenda: string; onError: OnError }) {
  const [gravedades, setGravedades] = useState(GRAVEDADES);
  const [diag, setDiag] = useState<string[]>(d.productividad?.diagnosticos ?? []);
  const desc = useDescarga(onError);
  const al = d.alertas;
  const idxGrav = al ? al.tabla.columnas.indexOf("gravedad") : -1;
  const idxCat = al ? al.tabla.columnas.indexOf("categoria") : -1;
  const filtradas = useMemo(() => (al ? al.tabla.filas.filter((f) => gravedades.includes(String(f[idxGrav]))) : []), [al, gravedades, idxGrav]);
  const categorias = useMemo(() => [...new Set(filtradas.map((f) => String(f[idxCat] ?? "")).filter(Boolean))].sort(), [filtradas, idxCat]);
  const prod = d.productividad;
  const filasProd = prod ? prod.tabla.filas.filter((f) => diag.includes(String(f.diagnostico))) : [];
  const idxProd = prod ? prod.tabla.columnas.indexOf("Productividad %") : -1;
  const descargarPrompt = () => void desc.bajar("prompt", "prompt", { periodo });
  return (
    <div className="space-y-4">
      <H3>{d.subtitulo}</H3>
      <Caption>
        Primero se ejecutan reglas duras sobre la base del sistema. La IA, si luego se integra por API, debe redactar y priorizar sobre esta
        información, no modificar datos.
      </Caption>
      <H4>Resumen ejecutivo automático</H4>
      <Info text={d.resumen} />
      <H4>Alertas detectadas</H4>
      {desc.feedback && <FeedbackBox feedback={desc.feedback} />}
      {!al ? (
        <Info tone="success" text="No se detectaron alertas automáticas con las reglas actuales." />
      ) : (
        <>
          <Tarjetas
            cols={4}
            items={[
              { label: "Alertas totales", valor: String(al.totales), delta: null, delta_color: "normal", caption: null },
              ...GRAVEDADES.map((g) => ({ label: `Gravedad ${g.toLowerCase()}`, valor: String(al.por_gravedad[g] ?? 0), delta: null, delta_color: "normal" as const, caption: null })),
            ]}
          />
          <Multiselect label="Filtrar por gravedad" opciones={GRAVEDADES} valor={gravedades} onChange={setGravedades} />
          <H4>Detalle separado por categoría</H4>
          {categorias.length === 0 ? (
            <Info text="No hay alertas para las gravedades seleccionadas." />
          ) : (
            categorias.map((cat) => {
              const filas = filtradas.filter((f) => String(f[idxCat]) === cat);
              return (
                <Expander key={cat} titulo={`${cat} — ${filas.length} caso/s`} abierto={categorias.length <= 3}>
                  <Grilla tabla={{ columnas: al.tabla.columnas, filas }} maxHeight="max-h-72" />
                  <PrimaryButton
                    tone="secondary"
                    busy={desc.busy === `alertas-${cat}`}
                    onClick={() => void desc.bajar(`alertas-${cat}`, "alertas", { periodo, categoria: cat, gravedades })}
                  >
                    {`⬇️ Descargar ${cat}`}
                  </PrimaryButton>
                </Expander>
              );
            })
          )}
        </>
      )}
      <hr className="border-slate-200" />
      <H4>Productividad docente calculada</H4>
      <Caption>
        La tabla analiza únicamente docentes propios con al menos una designación activa en el departamento operativo; las designaciones
        finalizadas/dadas de baja no se incluyen. Para cada docente activo se consolida por CUIL su carga del mismo período en toda la institución:
        comisiones, horas no lectivas, investigación y extensión. Las horas no lectivas usan el porcentaje completo si está solo en la comisión y la
        mitad del parámetro si la comisión tiene 2 o más docentes. Las alertas operativas de comisiones siguen siendo específicas del departamento
        actual y las franjas superpuestas no se cuentan dos veces.
      </Caption>
      <p className="text-sm">
        <Md text={leyenda} />
      </p>
      {!prod ? (
        <Info text="No hay docentes activos para analizar productividad en este período." />
      ) : (
        <>
          <Multiselect label="Filtrar por diagnóstico" opciones={prod.diagnosticos} valor={diag} onChange={setDiag} />
          {diag.length < prod.diagnosticos.length && (
            <Caption>{`Filtro de diagnóstico activo: se muestran ${filasProd.length} de ${prod.total} docentes.`}</Caption>
          )}
          <div className="max-h-[32rem] overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-left text-sm" aria-label="Productividad docente calculada">
              <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
                <tr>{prod.tabla.columnas.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filasProd.map((f, i) => (
                  <tr key={i}>
                    {f.celdas.map((v, j) => (
                      <td key={j} data-semaforo={j === idxProd ? f.color : undefined} className={`whitespace-nowrap px-3 py-1.5 ${j === idxProd ? SEMAFORO[f.color] ?? "" : "text-slate-700"}`}>
                        {texto(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <hr className="border-slate-200" />
      <H4>Prompt base para informe IA</H4>
      <Caption>
        Esto deja preparada la integración. Podés copiar este prompt en una IA externa o, más adelante, conectarlo por API. No incluye modificación
        automática de datos.
      </Caption>
      <Field label="Prompt estructurado">
        <textarea readOnly value={d.prompt} rows={18} aria-label="Prompt estructurado" className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs text-slate-700" />
      </Field>
      <PrimaryButton tone="secondary" busy={desc.busy === "prompt"} onClick={descargarPrompt}>
        ⬇️ Descargar prompt IA
      </PrimaryButton>
    </div>
  );
}

// ------------------------------------------------------------------ 📈 Comparación de períodos
function ComparacionTab({ data, subtabs, onError }: { data: Overview; subtabs: string[]; onError: OnError }) {
  const cmp = data.comparacion;
  const opciones = useMemo(() => cmp?.opciones ?? [], [cmp]);
  const [sel, setSel] = useState<string[]>(cmp?.default ?? []);
  const [ref, setRef] = useState<string>("");
  const [res, setRes] = useState<Comparacion | null>(null);
  const [cargando, setCargando] = useState((cmp?.default ?? []).length > 0);
  const [error, setError] = useState<string | null>(null);
  const [sub, setSub] = useState(0);
  useEffect(() => {
    if (!cmp?.actual || sel.length === 0) return;
    let cancel = false;
    analisisApi
      .comparacion(sel)
      .then((r) => {
        if (cancel) return;
        setRes(r);
        setError(null);
      })
      .catch((e) => !cancel && setError(onError(e).message))
      .finally(() => !cancel && setCargando(false));
    return () => {
      cancel = true;
    };
  }, [cmp, sel, onError]);
  const referencia = sel.includes(ref) ? ref : sel[0];
  if (!cmp?.actual) return <Info text="No se pudo determinar el período actual para comparar." />;
  const r = res && "referencias" in res && sel.length > 0 ? res : null;
  const refData = r && referencia ? r.referencias[referencia] : null;
  return (
    <div className="space-y-4">
      <H3>📈 Evolución del departamento</H3>
      <Caption>
        Elegí uno o varios períodos anteriores. El período actual se mantiene como referencia principal y los históricos se reconstruyen como foto al
        cierre. La vista prioriza indicadores, variaciones y tendencias; el detalle tabular queda disponible solo como respaldo.
      </Caption>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <p className="text-xs text-slate-500">PERÍODO ACTUAL</p>
          <p className="text-xl font-semibold text-slate-900">{cmp.actual.nombre}</p>
          <p className="text-xs text-slate-500">Base de comparación</p>
        </div>
        <div className="space-y-2 md:col-span-2">
          {opciones.length === 0 ? (
            <Info text="No hay períodos anteriores disponibles para comparar." />
          ) : (
            <>
              <Multiselect
                label="Períodos anteriores a incorporar"
                opciones={opciones}
                valor={sel}
                onChange={(v) => {
                  setCargando(v.length > 0);
                  setSel(v);
                }}
              />
              <Caption>
                La comparación múltiple no está limitada a dos períodos: cuando existan más períodos cargados, podés seleccionar 2, 3, 4 o más y todos se
                incorporan a Evolución visual y Detalle.
              </Caption>
            </>
          )}
        </div>
      </div>
      {error && <FeedbackBox feedback={{ tone: "error", text: error }} />}
      {opciones.length > 0 && sel.length === 0 && <Info text="Seleccioná al menos un período anterior para construir la comparación." />}
      {cargando && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4 text-brand-600" /> Calculando la comparación…
        </div>
      )}
      {r && refData && (
        <>
          <Info text={r.info.replace(/\*\*/g, "")} />
          <div className="max-w-sm">
            <Field label="Período de referencia para las variaciones de las tarjetas">
              <Select value={referencia} options={sel} onChange={setRef} />
            </Field>
          </div>
          <div role="tablist" aria-label="Comparación de períodos" className="flex gap-1 border-b border-slate-200">
            {subtabs.map((t, i) => (
              <button key={t} role="tab" aria-selected={sub === i} onClick={() => setSub(i)} className={`-mb-px border-b-2 px-3 py-2 text-sm ${sub === i ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500"}`}>
                {t}
              </button>
            ))}
          </div>
          {sub === 0 && (
            <div className="space-y-4" role="tabpanel">
              <H4>{refData.titulo}</H4>
              <Caption>
                Las variaciones son descriptivas: un valor mayor o menor no se interpreta automáticamente como mejor o peor, porque depende del
                indicador.
              </Caption>
              {refData.grupos.map((g, i) => (
                <div key={i} className="space-y-2">
                  {g.titulo && <p className="text-sm font-semibold text-slate-800">{g.titulo}</p>}
                  <Tarjetas items={g.tarjetas} cols={g.tarjetas.length > 4 ? 5 : g.tarjetas.length} />
                </div>
              ))}
              <p className="text-sm font-semibold text-slate-800">📍 Lectura rápida</p>
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  ["Cobertura de comisiones", refData.cobertura],
                  ["Productividad promedio", refData.productividad],
                ].map(([titulo, barras]) => (
                  <div key={titulo as string} className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-sm font-semibold">{titulo as string}</p>
                    {(barras as { texto: string; valor: number }[]).map((b) => (
                      <div key={b.texto}>
                        <Caption>{b.texto}</Caption>
                        <div className="h-2 rounded bg-slate-200" role="progressbar" aria-valuenow={Math.round(b.valor * 100)} aria-valuemin={0} aria-valuemax={100}>
                          <div className="h-2 rounded bg-brand-600" style={{ width: `${b.valor * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                <p className="font-semibold">Síntesis del cambio</p>
                <p><Md text={refData.sintesis} /></p>
              </div>
            </div>
          )}
          {sub === 1 && (
            <div className="space-y-4" role="tabpanel">
              <H4>Tendencia entre los períodos seleccionados</H4>
              <Caption>
                Los gráficos incluyen el período actual y todos los períodos anteriores seleccionados, ordenados cronológicamente. En los gráficos de
                barras comparables, las barras se superponen con transparencia para que la diferencia entre períodos se vea directamente sobre la
                misma escala.
              </Caption>
              <p className="text-sm font-semibold">Distribución de horas · períodos superpuestos</p>
              <Caption>
                Cada concepto tiene una única base. Los colores representan períodos y las barras se superponen con transparencia; así se ve cuánto
                crece o disminuye cada componente.
              </Caption>
              <VegaChart spec={r.graficos.horas} label="Distribución de horas" />
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-sm font-semibold">Cobertura y productividad</p>
                  <VegaChart spec={r.graficos.porcentajes} label="Cobertura y productividad" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Alumnos por docente</p>
                  <VegaChart spec={r.graficos.alumnos} label="Alumnos por docente" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Comisiones cubiertas sobre el total</p>
                  <Caption>Total y cubiertas comparten exactamente la misma base de cada período: la superposición hace visible de inmediato la parte cubierta.</Caption>
                  <VegaChart spec={r.graficos.comisiones} label="Comisiones cubiertas sobre el total" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Docentes activos</p>
                  <VegaChart spec={r.graficos.docentes} label="Docentes activos" />
                </div>
              </div>
            </div>
          )}
          {sub === 2 && (
            <div className="space-y-4" role="tabpanel">
              <H4>Matriz completa de indicadores</H4>
              <Caption>
                Esta vista queda como respaldo numérico e incluye TODOS los períodos seleccionados. Los períodos se muestran como columnas y los
                indicadores como filas para poder comparar 2, 3, 4 o más períodos sin desplazamiento horizontal excesivo.
              </Caption>
              <Grilla tabla={r.matriz} />
              <Expander titulo="ℹ️ Cómo se calcula Alumnos por docente">
                <p className="text-sm">
                  <strong>
                    Alumnos por docente = alumnos cargados una sola vez por asignatura/código del período / docentes únicos (CUIL) efectivamente
                    asignados a las comisiones.
                  </strong>
                </p>
                <Caption>
                  Para el detalle por conjunto, la app detecta la combinación exacta de asignaturas de cada comisión, reúne todas las comisiones con esa
                  misma combinación, suma una sola vez los alumnos de esos códigos y deduplica por CUIL a todos los docentes de esas comisiones. Una
                  materia con 12 comisiones no multiplica por 12 su cantidad de alumnos.
                </Caption>
              </Expander>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ expander del parámetro de horas no lectivas
function Parametro({ data, onSaved, onError }: { data: Overview; onSaved: (f: Feedback) => Promise<void>; onError: OnError }) {
  const p = data.parametro;
  const [valor, setValor] = useState(p.valor.toFixed(1));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function guardar() {
    setBusy(true);
    setFeedback(null);
    try {
      const r = await analisisApi.guardarPorcentaje(Number(valor), p.huella);
      await onSaved({ tone: r.tono ?? "success", text: r.mensaje });
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Expander titulo="⚙️ Parámetro de horas no lectivas">
      <Caption>{p.caption}</Caption>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="md:col-span-2">
          <Field label="Horas no lectivas estimadas sobre horas de comisión (%)" hint={p.ayuda}>
            <input
              type="number"
              min={0}
              max={200}
              step={5}
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              aria-label="Horas no lectivas estimadas sobre horas de comisión (%)"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </Field>
        </div>
        <Tarjeta m={{ label: "Valor vigente", valor: p.texto, delta: null, delta_color: "normal", caption: null }} />
      </div>
      {feedback && <FeedbackBox feedback={feedback} />}
      {data.permisos.puede_guardar && (
        <PrimaryButton busy={busy} onClick={() => void guardar()} disabled={valor === "" || Number(valor) < 0 || Number(valor) > 200}>
          💾 Guardar porcentaje de horas no lectivas
        </PrimaryButton>
      )}
    </Expander>
  );
}

export function AnalisisModule({ onAuthError }: { onAuthError: (e: ApiError) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodo, setPeriodo] = useState<string | null>(null);
  const [vista, setVista] = useState<Periodo | null>(null);
  const [cargandoPeriodo, setCargandoPeriodo] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [tab, setTab] = useState(0);
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
    analisisApi
      .overview()
      .then((d) => {
        if (cancel) return;
        setData(d);
        setPeriodo((p) => (p && d.periodos.includes(p) ? p : d.periodo));
        setLoadError(null);
      })
      .catch((e) => !cancel && setLoadError(handle(e)))
      .finally(() => !cancel && setLoading(false));
    return () => {
      cancel = true;
    };
  }, [handle, version]);

  useEffect(() => {
    if (!periodo || !data || data.vacio) return;
    let cancel = false;
    analisisApi
      .periodo(periodo)
      .then((v) => !cancel && setVista(v))
      .catch((e) => !cancel && setLoadError(handle(e)))
      .finally(() => !cancel && setCargandoPeriodo(false));
    return () => {
      cancel = true;
    };
  }, [periodo, data, handle]);

  // st.rerun() tras guardar: se relee todo (el nuevo porcentaje recalcula la productividad).
  async function afterSave(f: Feedback) {
    setFeedback(f);
    setCargandoPeriodo(true);
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando análisis…
      </div>
    );
  }
  if (loadError && !data) {
    const scope = loadError.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{loadError.message}</p>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">{data.titulo}</h2>
      </div>
      <Info text={data.info} />
      {feedback && <FeedbackBox feedback={feedback} />}
      {loadError && <FeedbackBox feedback={{ tone: (loadError as AnalisisError).tone === "warning" ? "warning" : "error", text: loadError.message }} />}
      {data.vacio ? (
        <Info tone="warning" text={data.mensaje_sin_periodos} />
      ) : (
        <>
          <div className="max-w-sm">
            <Field label="Período a analizar">
              <Select
                value={periodo ?? ""}
                options={data.periodos}
                disabled={cargandoPeriodo}
                onChange={(p) => {
                  setFeedback(null);
                  setCargandoPeriodo(true);
                  setPeriodo(p);
                }}
              />
            </Field>
          </div>
          <Parametro key={`${data.parametro.huella}-${version}`} data={data} onSaved={afterSave} onError={handle} />
          {cargandoPeriodo || !vista || vista.periodo !== periodo ? (
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <Spinner className="h-4 w-4 text-brand-600" />
              Calculando el análisis del período…
            </div>
          ) : (
            <>
              {vista.info_historico && <Info text={vista.info_historico} />}
              <div role="tablist" aria-label="Pestañas de Análisis" className="flex gap-1 overflow-x-auto border-b border-slate-200">
                {data.tabs.map((label, i) => (
                  <button
                    key={label}
                    role="tab"
                    aria-selected={tab === i}
                    onClick={() => setTab(i)}
                    className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm transition ${tab === i ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div role="tabpanel">
                {tab === 0 && <Dashboard d={vista.dashboard} />}
                {tab === 1 && <Plantel d={vista.plantel} />}
                {tab === 2 && <Movimiento key={vista.periodo} d={vista.movimiento} periodo={vista.periodo} onError={handle} />}
                {tab === 3 && <Automatico key={vista.periodo} d={vista.automatico} periodo={vista.periodo} leyenda={data.leyenda_semaforo} onError={handle} />}
                {tab === 4 && <ComparacionTab key={version} data={data} subtabs={data.subtabs_comparacion} onError={handle} />}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
