"use client";

// Pestaña 1 "📋 Designaciones del período" (entry l. 63403-63615): selector de período, tabla (o grilla de fechas
// v203/v207 si el período es histórico), conteo, vínculo masivo de actos e historial v266/v267/v269 por indicador.
import { useMemo, useState } from "react";
import { Field, FeedbackBox, PrimaryButton, Select } from "@/components/module-ui";
import {
  Aviso,
  Caption,
  type Col,
  DateInput,
  GestionActos,
  type OnDone,
  type OnError,
  type TabProps,
  Tabla,
  safeDate,
  useAccion,
  usePeriodo,
} from "@/components/designaciones-shared";
import {
  type Designacion,
  type Movimiento,
  type Overview,
  type PeriodoData,
  type WriteResult,
  designacionesApi,
  download,
  post,
} from "@/lib/designaciones";

// Columnas visibles de get_designaciones sin id ni columnas técnicas, con los renombres certificados.
const COLUMNAS: Col<Designacion>[] = [
  { key: "periodo", label: "periodo" },
  { key: "nombre_completo", label: "nombre_completo" },
  { key: "cuil", label: "cuil" },
  { key: "cargo", label: "cargo" },
  { key: "dedicacion", label: "dedicacion" },
  { key: "horas", label: "horas" },
  { key: "tipo_designacion", label: "tipo_designacion" },
  { key: "ad_honorem", label: "ad_honorem" },
  { key: "fecha_desde", label: "fecha_desde" },
  { key: "fecha_hasta", label: "fecha_hasta" },
  { key: "fecha_hasta_prevista", label: "fecha_hasta_prevista" },
  { key: "fecha_finalizacion_efectiva", label: "fecha_finalizacion_efectiva" },
  { key: "fecha_registro_finalizacion", label: "fecha_registro_finalizacion" },
  { key: "motivo_finalizacion", label: "motivo_finalizacion" },
  { key: "estado_mostrado", label: "estado" },
  { key: "observaciones", label: "observaciones" },
  { key: "funcion", label: "Función" },
  { key: "texto_funcion_no_docente", label: "Funciones no docentes" },
  { key: "acto_administrativo", label: "Acto administrativo" },
];

const COLS_GESTION_DES: Col<Designacion>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "cargo", label: "Cargo" },
  { key: "dedicacion", label: "Dedicación" },
  { key: "horas", label: "Hs." },
  { key: "tipo_designacion", label: "Tipo" },
  { key: "acto_administrativo", label: "Acto administrativo" },
  { key: "estado", label: "Estado" },
];

const COLS_GESTION_MOV: Col<Movimiento>[] = [
  { key: "fecha", label: "Fecha" },
  { key: "tipo_movimiento", label: "Movimiento" },
  { key: "nombre", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "detalle", label: "Detalle" },
  { key: "acto_administrativo", label: "Acto administrativo" },
];

export function PeriodoTab({ data, version, onDone, onError }: TabProps) {
  const nombres = data.periodos.map((p) => p.nombre ?? "");
  const defecto = data.abierto?.nombre ?? nombres[0] ?? "";
  const [nombre, setNombre] = useState<string>(defecto);
  const periodo = data.periodos.find((p) => p.nombre === nombre) ?? data.periodos.find((p) => p.nombre === defecto) ?? null;
  const { data: pd, error } = usePeriodo(periodo?.id ?? null, version, onError);

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Designaciones</h3>
      {data.periodos.length === 0 || !periodo ? (
        <FeedbackBox feedback={{ tone: "info", text: "Todavía no hay períodos registrados." }} />
      ) : (
        <>
          <div className="max-w-sm">
            <Field label="Ver período">
              <Select value={periodo.nombre ?? ""} options={nombres} onChange={setNombre} />
            </Field>
          </div>
          {error && <FeedbackBox feedback={{ tone: "error", text: error }} />}
          {!pd ? (
            !error && <Caption>Cargando designaciones del período…</Caption>
          ) : pd.designaciones.length === 0 ? (
            <FeedbackBox feedback={{ tone: "info", text: "No hay designaciones registradas para este período." }} />
          ) : (
            <Contenido key={`${pd.periodo.id}-${version}`} data={data} pd={pd} version={version} onDone={onDone} onError={onError} />
          )}
        </>
      )}
    </section>
  );
}

function Contenido({
  data,
  pd,
  version,
  onDone,
  onError,
}: {
  data: Overview;
  pd: PeriodoData;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const pid = pd.periodo.id;
  return (
    <div className="space-y-5">
      {pd.historico ? (
        <GrillaHistorica data={data} pd={pd} onDone={onDone} onError={onError} />
      ) : (
        <Tabla rows={pd.designaciones} cols={COLUMNAS} rowKey={(d) => String(d.id)} />
      )}
      <Caption>
        {pd.historico
          ? `Cantidad de designaciones vigentes al cierre del período seleccionado: ${pd.conteo}`
          : `Cantidad de designaciones activas en el período seleccionado: ${pd.conteo}`}
      </Caption>
      <GestionActos
        titulo="🔗 Vincular / cambiar acto administrativo de una o varias designaciones"
        ayuda="Podés seleccionar varias designaciones y aplicarles el mismo acto administrativo. Cada designación conserva un único acto principal; si ya tenía otro, se reemplaza el vínculo."
        filas={pd.designaciones}
        cols={COLS_GESTION_DES}
        buscarCols={["nombre_completo", "cuil", "cargo", "dedicacion", "tipo_designacion", "acto_administrativo", "estado"]}
        placeholder="Docente, CUIL, cargo, dedicación, tipo o acto actual..."
        destino="designaciones"
        periodoId={pid}
        data={data}
        version={version}
        onDone={onDone}
        onError={onError}
      />
      <hr className="border-slate-200" />
      <Historial data={data} pd={pd} version={version} onDone={onDone} onError={onError} />
    </div>
  );
}

// Grilla histórica v203: solo fecha_desde / fecha_hasta editables; al guardar, sincronización de baja v207.
function GrillaHistorica({ data, pd, onDone, onError }: { data: Overview; pd: PeriodoData; onDone: OnDone; onError: OnError }) {
  const [edits, setEdits] = useState<Record<number, { desde: string; hasta: string }>>({});
  const accion = useAccion(onDone, onError);
  const [excelBusy, setExcelBusy] = useState(false);
  const [excelError, setExcelError] = useState<string | null>(null);
  const editable = data.permisos.puede_escribir;
  const valor = (d: Designacion) => edits[d.id] ?? { desde: safeDate(d.fecha_desde, ""), hasta: safeDate(d.fecha_hasta, "") };
  const { cambios, errores } = useMemo(() => {
    const cambios: { id: number; huella: string; desde: string; hasta: string }[] = [];
    const errores: string[] = [];
    for (const d of pd.designaciones) {
      const e = edits[d.id];
      if (!e) continue;
      if (e.desde === safeDate(d.fecha_desde, "") && e.hasta === safeDate(d.fecha_hasta, "")) continue;
      if (!e.desde || !e.hasta) errores.push(`Designación ID ${d.id}: fecha_desde y fecha_hasta son obligatorias.`);
      else if (e.desde > e.hasta) errores.push(`Designación ID ${d.id}: fecha_desde no puede ser posterior a fecha_hasta.`);
      else cambios.push({ id: d.id, huella: d.huella, desde: e.desde, hasta: e.hasta });
    }
    return { cambios, errores };
  }, [edits, pd.designaciones]);

  async function excel() {
    setExcelBusy(true);
    setExcelError(null);
    try {
      download(await designacionesApi.tablaExcel(pd.periodo.id));
    } catch (e) {
      setExcelError(onError(e).message);
    } finally {
      setExcelBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Caption>
        Período histórico: podés corregir directamente <b>fecha_desde</b> y <b>fecha_hasta</b> en la tabla. Si{" "}
        <b>fecha_hasta</b> queda antes del cierre del período, se registra/sincroniza automáticamente la{" "}
        <b>Baja de designación</b> con esa fecha. El resto permanece bloqueado.
      </Caption>
      <Tabla
        rows={pd.designaciones}
        cols={COLUMNAS}
        rowKey={(d) => String(d.id)}
        render={(d, key) => {
          if (!editable || (key !== "fecha_desde" && key !== "fecha_hasta")) return undefined;
          const v = valor(d);
          const campo = key === "fecha_desde" ? "desde" : "hasta";
          return (
            <DateInput
              label={`${key} de la designación ${d.id}`}
              value={v[campo]}
              onChange={(nuevo) => setEdits((prev) => ({ ...prev, [d.id]: { ...valor(d), [campo]: nuevo } }))}
            />
          );
        }}
      />
      {errores.length > 0 && (
        <Aviso feedback={{ tone: "error", text: "No se pueden guardar las correcciones de fechas:\n- " + errores.join("\n- ") }} />
      )}
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {editable && (
        <div className="flex flex-wrap items-center gap-4">
          <PrimaryButton
            busy={accion.busy}
            disabled={cambios.length === 0 || errores.length > 0}
            onClick={() =>
              accion.run(() => post<WriteResult>("fechas-historicas", { periodo_id: pd.periodo.id, cambios }), () => setEdits({}))
            }
          >
            💾 Guardar fechas corregidas
          </PrimaryButton>
          <Caption>
            {cambios.length ? `Filas con cambios pendientes de guardar: ${cambios.length}` : "No hay cambios de fechas pendientes."}
          </Caption>
        </div>
      )}
      {excelError && <FeedbackBox feedback={{ tone: "error", text: excelError }} />}
      <PrimaryButton tone="secondary" busy={excelBusy} onClick={excel}>
        📥 Descargar tabla en Excel
      </PrimaryButton>
    </div>
  );
}

// `{:+g}` de Python para la variación total.
const signo = (v: number) => (Object.is(v, -0) || v < 0 ? "-" : "+") + String(Math.abs(v));

// _render_historial_designaciones_analisis_v267: lectura por indicadores, igual que Análisis.
function Historial({
  data,
  pd,
  version,
  onDone,
  onError,
}: {
  data: Overview;
  pd: PeriodoData;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const [elegido, setElegido] = useState<string | null>(null);
  const indicador = pd.indicadores.find((i) => i.etiqueta === elegido) ?? pd.indicadores[0] ?? null;
  const filtrado = indicador ? pd.historial.filter((m) => m.categoria === indicador.categoria) : [];
  const variacion = filtrado.reduce((s, m) => s + (Number(m.variacion_horas) || 0), 0);
  const conActo = filtrado.filter((m) => data.catalogos.movimientos_con_acto.includes(m.tipo_movimiento));
  const periodoNombre = pd.periodo.nombre ?? "";
  const filas = filtrado.map((m) => ({ ...m, periodo: periodoNombre, movimiento: indicador?.movimiento ?? "" }));

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Altas, modificaciones y bajas del período</h3>
      <Caption>
        Historial administrativo de las designaciones del período. El acto se toma exclusivamente del repositorio; si
        todavía no fue asociado se muestra como pendiente de vincular.
      </Caption>
      {pd.historial.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: "No hay altas, modificaciones o bajas de designación registradas para este período." }} />
      ) : (
        indicador && (
          <>
            <div>
              <p className="mb-1 text-xs font-medium text-slate-500">Indicador</p>
              <div role="radiogroup" aria-label="Indicador" className="flex flex-wrap gap-2">
                {pd.indicadores.map((i) => (
                  <button
                    key={i.etiqueta}
                    type="button"
                    role="radio"
                    aria-checked={i.etiqueta === indicador.etiqueta}
                    onClick={() => setElegido(i.etiqueta)}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      i.etiqueta === indicador.etiqueta ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
                    }`}
                  >
                    {i.etiqueta}
                  </button>
                ))}
              </div>
            </div>
            <Caption>
              {filtrado.length} movimiento/s integran el indicador <b>{indicador.etiqueta}</b>; variación total: {signo(variacion)} hs.
            </Caption>
            {filtrado.length === 0 ? (
              <FeedbackBox feedback={{ tone: "info", text: `El indicador ${indicador.etiqueta} no tiene movimientos en ${periodoNombre}.` }} />
            ) : (
              <Tabla
                rows={filas}
                rowKey={(m) => String(m.id)}
                cols={[
                  { key: "periodo", label: "Período" },
                  { key: "fecha", label: "Fecha" },
                  { key: "cuil", label: "CUIL" },
                  { key: "nombre", label: "Docente" },
                  { key: "tipo_movimiento", label: "Tipo original" },
                  { key: "movimiento", label: "Movimiento" },
                  { key: "detalle", label: "Detalle" },
                  { key: "acto_administrativo", label: "Acto administrativo" },
                  { key: "observaciones", label: "Observaciones" },
                  { key: "variacion_horas", label: "Variación de horas" },
                ]}
              />
            )}
            {conActo.length > 0 && (
              <GestionActos
                key={indicador.etiqueta}
                titulo="🔗 Vincular / cambiar acto administrativo de uno o varios movimientos"
                ayuda="Una misma resolución puede aprobar varias altas, modificaciones o bajas."
                filas={conActo}
                cols={COLS_GESTION_MOV}
                buscarCols={["fecha", "tipo_movimiento", "nombre", "cuil", "detalle", "acto_administrativo"]}
                placeholder="Fecha, movimiento, docente, CUIL o detalle..."
                destino="movimientos"
                periodoId={pd.periodo.id}
                data={data}
                version={version}
                onDone={onDone}
                onError={onError}
              />
            )}
          </>
        )
      )}
    </div>
  );
}
