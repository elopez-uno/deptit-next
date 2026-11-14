"use client";

// Pestaña "📊 Resumen docente" (E4-05; certificado entry l. 60845-61197). El backend transcribe la pestaña certificada
// sección por sección (textos, avisos, métricas, tablas, torta, tarjeta y cronograma); acá solo se dibuja. El selector
// de docentes usa la base maestra ya cargada (get_docentes) y filtrar_dataframe_por_texto. La sección "Mensaje para
// consultar la designación" (E4-06; l. 61200-61275): radio del estado, guardado (writer de Designaciones) y mensaje
// generado por el backend; el semáforo de cada opción también viene del backend.
import { useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/brand";
import { Metric } from "@/components/comisiones-shared";
import {
  DataTable,
  Details,
  type Feedback,
  FeedbackBox,
  Field,
  PrimaryButton,
  Radio,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import { VegaChart } from "@/components/vega-chart";
import { ApiError } from "@/lib/auth";
import {
  type Aviso,
  type Consulta,
  type MensajeConsulta,
  type DocentesOverview,
  type Resumen,
  type ResumenSecciones,
  type SeccionTabla,
  type TablaUI,
  docentesApi,
  filtrarPorTexto,
} from "@/lib/docentes";
import { etiquetaColumna } from "@/lib/unidades-academicas";

type OnError = (e: unknown) => ApiError;

const COLUMNAS_SELECCION = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "legajo", label: "Legajo" },
  { key: "titulo", label: "Título" },
  { key: "tipo_docente", label: "Tipo" },
] as const;

// **texto** del certificado -> <strong>
function Negritas({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return <>{partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}</>;
}

function Caption({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <p className="text-xs text-slate-500">
      <Negritas text={text} />
    </p>
  );
}


function Tabla({ tabla }: { tabla: TablaUI }) {
  const filas = useMemo(
    () => tabla.filas.map((f) => Object.fromEntries(tabla.columnas.map((c, i) => [c, f[i]]))) as Record<string, unknown>[],
    [tabla]
  );
  const columnas = tabla.columnas.map((c) => ({ key: c, label: etiquetaColumna(c) }));
  return <DataTable rows={filas} columns={columnas} rowKey={(_, i) => String(i)} />;
}

function AvisoBox({ aviso }: { aviso: Aviso }) {
  return <FeedbackBox feedback={{ tone: aviso.tono, text: aviso.texto }} />;
}

function Titulo({ text }: { text: string }) {
  return <h4 className="text-base font-semibold text-brand-950">{text}</h4>;
}

function Seccion({ s }: { s: SeccionTabla }) {
  return (
    <section className="space-y-2">
      <Titulo text={s.titulo} />
      <Caption text={s.caption} />
      {s.aviso && <FeedbackBox feedback={{ tone: "warning", text: s.aviso }} />}
      {s.tabla ? <Tabla tabla={s.tabla} /> : s.vacio && <AvisoBox aviso={s.vacio} />}
    </section>
  );
}

const COLOR = { positivo: "text-emerald-700", negativo: "text-red-700", neutro: "text-slate-700" } as const;

function Dato({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <div className="mt-1 font-bold text-slate-900">{children}</div>
    </div>
  );
}

function Lineas({ lineas }: { lineas: string[] }) {
  return <>{lineas.map((l, i) => <span key={i} className="block">{l}</span>)}</>;
}

function Separador() {
  return <hr className="border-slate-200" />;
}

function DatosGenerales({ d }: { d: ResumenSecciones["datos_generales"] }) {
  return (
    <section className="space-y-3">
      <Titulo text="Datos generales" />
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div>
          <p className="text-lg font-semibold text-brand-950">👤 {d.nombre}</p>
          <p className="text-xs text-slate-500">CUIL {d.cuil}  •  Legajo {d.legajo}</p>
        </div>
        <div className="min-w-[16rem]">
          <p className="mb-1 text-sm font-semibold">Situación en el período</p>
          <FeedbackBox feedback={{ tone: d.situacion.tono, text: `${d.situacion.tono === "success" ? "✅" : "ℹ️"} ${d.situacion.texto}` }} />
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="space-y-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
          <p className="font-semibold">📅 Trayectoria</p>
          <p><Negritas text={`**Inicio histórico:** ${d.trayectoria.inicio_historico}`} /></p>
          <p><Negritas text={`**Última alta:** ${d.trayectoria.ultima_alta}`} /></p>
          <p><Negritas text={`**Finalización / vencimiento:** ${d.trayectoria.finalizacion}`} /></p>
        </div>
        <div className="space-y-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
          <p className="font-semibold">✉️ Contacto</p>
          <p><Negritas text={`**Mail:** ${d.contacto.mail}`} /></p>
          <p><Negritas text={`**Teléfono:** ${d.contacto.telefono}`} /></p>
        </div>
        <div className="space-y-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
          <p className="font-semibold">🎓 Formación</p>
          <p><Negritas text={`**Título de grado:** ${d.formacion.grado}`} /></p>
          <p><Negritas text={`**Título de posgrado:** ${d.formacion.posgrado}`} /></p>
          <p><Negritas text={`**Nivel adicional salarial:** ${d.formacion.nivel}`} /></p>
          <p><Negritas text={d.formacion.antiguedad} /></p>
        </div>
      </div>
      {d.observaciones && (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
          <p className="font-semibold">📝 Observaciones</p>
          <p className="whitespace-pre-line">{d.observaciones}</p>
        </div>
      )}
    </section>
  );
}

function Tarjeta({ t }: { t: ResumenSecciones["tarjeta"] }) {
  return (
    <section className="space-y-3">
      {t.aviso_prestado && <FeedbackBox feedback={{ tone: "info", text: t.aviso_prestado }} />}
      <Titulo text={t.titulo} />
      {t.estado_designacion && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <Negritas text={t.estado_designacion} />
        </p>
      )}
      {t.funciones_no_docentes && (
        <div className="space-y-2">
          <p className="font-semibold">{t.funciones_no_docentes.titulo}</p>
          <Caption text={t.funciones_no_docentes.caption} />
          <Tabla tabla={t.funciones_no_docentes.tabla} />
        </div>
      )}
      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-[1.4fr_0.9fr_0.9fr]">
          <Dato label={t.cargos.label}>
            <span className="text-xl"><Lineas lineas={t.cargos.lineas} /></span>
          </Dato>
          <Dato label={t.horas.label}>
            <span className="text-2xl">{t.horas.valor}</span>
          </Dato>
          <Dato label={t.variacion.label}>
            <span className={`text-2xl ${COLOR[t.variacion.tono ?? "neutro"]}`}>{t.variacion.valor}</span>
            <p className="text-xs font-normal text-slate-500">{t.variacion.caption}</p>
          </Dato>
        </div>
        <Dato label={t.cambios.label}>
          <Lineas lineas={t.cambios.lineas} />
        </Dato>
      </div>
      {t.evolucion && (
        <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
          <p className="font-bold">{t.evolucion.titulo}</p>
          <div className="grid gap-3 md:grid-cols-3">
            <Dato label={t.evolucion.base.label}><span className="text-xl">{t.evolucion.base.valor}</span></Dato>
            <Dato label={t.evolucion.movimiento.label}>
              <span className={`text-xl ${COLOR[t.evolucion.movimiento.tono ?? "neutro"]}`}>{t.evolucion.movimiento.valor}</span>
            </Dato>
            <Dato label={t.evolucion.resultado.label}><span className="text-xl">{t.evolucion.resultado.valor}</span></Dato>
          </div>
        </div>
      )}
      {t.compartido && <FeedbackBox feedback={{ tone: "warning", text: t.compartido }} />}
      <Caption text={t.caption_origen} />
      {t.departamentos && <Tabla tabla={t.departamentos} />}
    </section>
  );
}

function Cronograma({ c }: { c: ResumenSecciones["cronograma"] }) {
  return (
    <section className="space-y-2">
      <Titulo text={c.titulo} />
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-[10.5px] leading-tight">
          <thead>
            <tr>
              <th className="w-24 border border-slate-300 px-1 py-1">Hora</th>
              {c.dias.map((d) => (
                <th key={d} className="border border-slate-300 px-1 py-1">{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {c.filas.map((f) => (
              <tr key={f.hora}>
                <td className="whitespace-nowrap border border-slate-300 px-1 py-1 text-center font-semibold">{f.hora}</td>
                {f.celdas.map((celda, i) =>
                  celda ? (
                    <td key={i} title={celda.titulo} className="cursor-help border border-emerald-400 bg-emerald-100 px-1 py-1 text-center font-bold">
                      {celda.labels.map((l) => <span key={l} className="block truncate">{l}</span>)}
                    </td>
                  ) : (
                    <td key={i} className="border border-slate-300" />
                  )
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Caption text={c.caption} />
    </section>
  );
}

function Productividad({ p }: { p: ResumenSecciones["productividad"] }) {
  return (
    <section className="space-y-3">
      <Titulo text={p.titulo} />
      <Caption text={p.caption} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {p.metricas.map((m) => <Metric key={m.label} label={m.label} value={m.valor} />)}
      </div>
      {p.detalle_no_lectivas && (
        <Details summary={p.detalle_no_lectivas.titulo}>
          <Tabla tabla={p.detalle_no_lectivas.tabla} />
        </Details>
      )}
      {p.torta ? <VegaChart spec={p.torta.spec} label="Distribución de horas" /> : p.sin_torta && <FeedbackBox feedback={{ tone: "info", text: p.sin_torta }} />}
    </section>
  );
}

// Sección E4-06 ("Mensaje para consultar la designación"): estado actual, radio certificado, semáforo de la opción elegida,
// guardado (el backend autoriza con designaciones.write) y mensaje listo para copiar, generado por el backend.
// Como el certificado (button_con_permisos, l. 2787-2804): "Guardar…" y "Generar…" son acciones "write" por su rótulo
// y se muestran deshabilitadas, con esta ayuda, si el rol no puede escribir en Docentes (visual_can = permisos.puede_escribir).
const AYUDA_SIN_ESCRITURA = "Tu rol permite visualizar, pero no cargar, editar ni generar cambios.";

function ConsultaDocente({ c, cuil, periodoId, puedeEscribir, onError }: { c: Consulta; cuil: string; periodoId: number; puedeEscribir: boolean; onError: OnError }) {
  const [sel, setSel] = useState(c.seleccion);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [mensaje, setMensaje] = useState<MensajeConsulta | null>(null);
  const [busy, setBusy] = useState<"guardar" | "mensaje" | null>(null);
  const opcion = c.opciones.find((o) => o.etiqueta === sel) ?? c.opciones[0];

  async function guardar() {
    setBusy("guardar");
    try {
      const r = await docentesApi.estadoConsulta(cuil, periodoId, opcion.valor);
      // el radio queda en el estado confirmado por el backend (el certificado hace st.rerun y relee)
      setSel(c.opciones.find((o) => o.valor === r.estado)?.etiqueta ?? sel);
      setFeedback({ tone: "success", text: r.mensaje });
    } catch (e) {
      setFeedback({ tone: "error", text: onError(e).message });
    } finally {
      setBusy(null);
    }
  }

  async function generar() {
    setBusy("mensaje");
    try {
      setMensaje(await docentesApi.mensajeConsulta(cuil, periodoId));
    } catch (e) {
      setFeedback({ tone: "error", text: onError(e).message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="space-y-3">
      <Titulo text={c.titulo} />
      <Caption text={c.caption} />
      <Field label={c.radio}>
        <Radio name={`consulta-${cuil}-${periodoId}`} value={sel} options={c.opciones.map((o) => o.etiqueta)} onChange={setSel} />
      </Field>
      <div className={`rounded-xl border px-4 py-3 text-sm ${SEMAFORO[opcion.semaforo.tono]}`}>
        <Negritas text={opcion.semaforo.texto} />
      </div>
      <div className="flex flex-wrap gap-2">
        <span title={puedeEscribir ? undefined : AYUDA_SIN_ESCRITURA}>
          <PrimaryButton tone="secondary" busy={busy === "guardar"} disabled={busy !== null || !puedeEscribir} onClick={guardar}>
            {c.boton_guardar}
          </PrimaryButton>
        </span>
        <span title={puedeEscribir ? undefined : AYUDA_SIN_ESCRITURA}>
          <PrimaryButton busy={busy === "mensaje"} disabled={busy !== null || !puedeEscribir} onClick={generar}>
            {c.boton_mensaje}
          </PrimaryButton>
        </span>
      </div>
      {feedback && <FeedbackBox feedback={feedback} />}
      {mensaje && (
        <div className="space-y-3">
          {mensaje.advertencias.map((a) => (
            <FeedbackBox key={a} feedback={{ tone: "warning", text: a }} />
          ))}
          <Field label={c.asunto_label}>
            <TextInput value={mensaje.asunto} onChange={(v) => setMensaje({ ...mensaje, asunto: v })} />
          </Field>
          <Field label={c.cuerpo_label}>
            <Textarea rows={24} value={mensaje.cuerpo} onChange={(v) => setMensaje({ ...mensaje, cuerpo: v })} />
          </Field>
        </div>
      )}
    </section>
  );
}

const SEMAFORO = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  error: "border-red-200 bg-red-50 text-red-900",
  info: "border-sky-200 bg-sky-50 text-sky-900",
} as const;

function Secciones({ r, cuil, puedeEscribir, onError }: { r: Resumen; cuil: string; puedeEscribir: boolean; onError: OnError }) {
  const s = r.secciones!;
  const su = s.sueldo;
  return (
    <div className="space-y-5">
      <DatosGenerales d={s.datos_generales} />
      <Separador />
      <Tarjeta t={s.tarjeta} />
      <Separador />
      <Seccion s={s.designaciones} />
      <Seccion s={s.actos} />
      <section className="space-y-2">
        <Titulo text={su.titulo} />
        {r.estimacion && (
          <p className="text-xs text-slate-500">
            <span className="mr-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-amber-800">
              {r.estimacion.etiqueta}
            </span>
            {r.estimacion.advertencia}
          </p>
        )}
        {su.vacio ? (
          <AvisoBox aviso={su.vacio} />
        ) : (
          <>
            <Caption text={su.caption} />
            {su.tabla && <Tabla tabla={su.tabla} />}
            {su.total && <Metric label={su.total.label} value={su.total.valor} />}
          </>
        )}
      </section>
      <Separador />
      <Seccion s={s.investigacion} />
      <Separador />
      <Seccion s={s.extension} />
      <Separador />
      <Seccion s={s.actividades} />
      <Separador />
      <Seccion s={s.comisiones} />
      <Cronograma c={s.cronograma} />
      <Seccion s={s.superposiciones} />
      <Productividad p={s.productividad} />
      <Separador />
      <Seccion s={s.materias_historicas} />
      <Separador />
      {r.consulta && r.seleccionado && (
        <ConsultaDocente key={`${cuil}|${r.seleccionado.id}`} c={r.consulta} cuil={cuil} periodoId={r.seleccionado.id} puedeEscribir={puedeEscribir} onError={onError} />
      )}
    </div>
  );
}

export function ResumenDocente({ data, onError }: { data: DocentesOverview | null; onError: OnError }) {
  const [q, setQ] = useState("");
  const [cuil, setCuil] = useState<string | null>(null);
  const [periodoId, setPeriodoId] = useState<number | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  // CUIL para el que se calculó `resumen`. Mientras llega el resumen de otro docente, `sel` ya cambió pero `resumen` sigue
  // siendo el anterior: las secciones (y la clave de ConsultaDocente) deben usar el CUIL de los datos que muestran, o
  // el radio se inicializa con el estado de consulta del docente anterior y no se vuelve a montar (bug E4-06).
  const [resumenCuil, setResumenCuil] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [listo, setListo] = useState<string | null>(null);
  const docentes = useMemo(() => data?.docentes ?? [], [data]);
  const vista = useMemo(() => filtrarPorTexto(docentes, q, ["nombre_completo", "cuil", "legajo", "titulo"]), [docentes, q]);
  // seleccionar_registro_desde_tabla: por defecto, la primera fila de la vista filtrada.
  const sel = vista.some((d) => d.cuil === cuil) ? cuil : (vista[0]?.cuil ?? null);
  const docenteSel = vista.find((d) => d.cuil === sel);
  const clave = `${sel}|${periodoId}`;
  const busy = !!sel && listo !== clave;

  useEffect(() => {
    if (!sel) return;
    let cancel = false;
    docentesApi
      .resumen(sel, periodoId)
      .then((r) => {
        if (!cancel) {
          setResumen(r);
          setResumenCuil(sel);
          setError(null);
        }
      })
      .catch((e) => !cancel && setError(onError(e)))
      .finally(() => !cancel && setListo(`${sel}|${periodoId}`));
    return () => {
      cancel = true;
    };
  }, [sel, periodoId, onError]);

  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Resumen individual del docente</h3>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Seleccioná un docente y un período para analizar designaciones, movimientos, investigación, comisiones, " +
            "productividad y alertas. Las materias históricas se muestran acumuladas para todos los períodos.",
        }}
      />
      {data && docentes.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: "Todavía no hay docentes registrados." }} />
      ) : resumen?.sin_periodos ? (
        <FeedbackBox feedback={{ tone: "warning", text: resumen.sin_periodos }} />
      ) : (
        <>
          <Field label="Buscar docente para consultar">
            <TextInput value={q} onChange={setQ} placeholder="Nombre, CUIL, legajo o título" />
          </Field>
          {vista.length === 0 ? (
            <FeedbackBox feedback={{ tone: "warning", text: "No hay docentes que coincidan con la búsqueda." }} />
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-800">Docentes encontrados</p>
              <DataTable
                rows={vista as unknown as Record<string, unknown>[]}
                columns={COLUMNAS_SELECCION.map((c) => ({ key: c.key, label: c.label }))}
                rowKey={(r) => String(r.cuil)}
                selected={sel}
                onSelect={(k) => setCuil(k)}
                maxHeight="max-h-72"
              />
              <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
                <Caption text={`Docente seleccionado: **${docenteSel?.nombre_completo ?? ""}**`} />
                {resumen?.periodos && resumen.seleccionado && (
                  <Field label="Período a analizar">
                    <Select
                      value={resumen.seleccionado.nombre}
                      options={resumen.periodos.map((p) => p.nombre)}
                      onChange={(n) => setPeriodoId(resumen.periodos!.find((p) => p.nombre === n)?.id ?? null)}
                      disabled={busy}
                    />
                  </Field>
                )}
              </div>
              {error && <FeedbackBox feedback={{ tone: "error", text: error.message }} />}
              {busy && !resumen && (
                <p className="flex items-center gap-2 text-sm text-slate-500">
                  <Spinner className="h-4 w-4 text-brand-600" />
                  Cargando el resumen del docente…
                </p>
              )}
              {resumen?.error && <FeedbackBox feedback={{ tone: "error", text: resumen.error }} />}
              {resumen?.secciones && resumenCuil && <Secciones r={resumen} cuil={resumenCuil} puedeEscribir={data?.permisos.puede_escribir ?? false} onError={onError} />}
            </>
          )}
        </>
      )}
    </section>
  );
}
