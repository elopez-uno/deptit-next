"use client";

// Pestaña "👥 Inscriptos" (v248, entry l. 70839-71026): una cantidad por asignatura/código y período, editable en
// cualquier período (también cerrados). Solo se editan "Inscriptos al inicio" y "Regulares al final".
import { useMemo, useState } from "react";
import { periodoPorDefecto, SelectorPeriodo } from "@/components/comisiones-periodo";
import { Aviso, Caption, Cargando, Metric, SoloLectura, TablaLibre, type TabProps, useConsulta } from "@/components/comisiones-shared";
import { useAccion } from "@/components/designaciones-shared";
import { Details, EmptyState, FeedbackBox, PrimaryButton } from "@/components/module-ui";
import { type FilaInscriptos, type InscriptosData, type WriteResult, post } from "@/lib/comisiones";

const LABELS: Record<string, string> = {
  codigo_materia: "Código",
  asignatura: "Asignatura / materia dictada",
  asignatura_base: "Asignatura base",
  materia_especifica: "Materia específica",
  cantidad: "Inscriptos al inicio",
  cantidad_final: "Regulares al final",
  cantidad_comisiones: "Cant. de comisiones",
  comisiones_relacionadas: "Comisiones relacionadas",
  combinaciones_relacionadas: "Combinaciones detectadas",
  carrera: "Carrera",
  escuela: "Unidad académica",
  fecha_actualizacion: "Actualización inicio",
  fecha_actualizacion_final: "Actualización final",
  observaciones_inscriptos: "Observaciones",
};

const GRUPOS: Record<string, string> = {
  codigos: "Código/s",
  asignaturas: "Asignatura/s",
  inscriptos_totales: "Alumnos totales",
  regulares_finales: "Regulares finales",
  cantidad_comisiones: "Comisiones",
  comisiones: "Detalle de comisiones",
  docentes_unicos: "Docentes únicos",
  docentes: "Docentes",
  alumnos_por_docente: "Alumnos por docente",
};

const HISTORIAL: Record<string, string> = {
  periodo: "Período",
  codigo_materia: "Código",
  asignatura: "Asignatura / materia dictada",
  asignatura_base: "Asignatura base",
  materia_especifica: "Materia específica",
  comisiones: "Comisiones",
  comisiones_relacionadas: "Comisiones relacionadas",
  inscriptos_inicio: "Inscriptos al inicio",
  regulares_final: "Regulares al final",
  variacion: "Variación",
  retencion_pct: "Retención %",
  carrera: "Carrera",
  escuela: "Unidad académica",
};

type Edicion = Record<string, { cantidad: string; cantidad_final: string }>;

const texto = (v: unknown) => (v === null || v === undefined ? "" : String(v));

export function InscriptosTab({ data, version, onDone, onError }: TabProps) {
  const [nombre, setNombre] = useState(() => periodoPorDefecto(data));
  const periodo = data.periodos.find((p) => String(p.nombre) === nombre);
  const q = useConsulta<InscriptosData>("inscriptos", { periodo_id: periodo?.id }, onError, version, !!periodo);
  if (!data.periodos.length) return <EmptyState text="Todavía no hay períodos registrados." />;
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Registro de inscriptos por asignatura / código</h3>
        <Caption>
          La cantidad de alumnos se registra una sola vez por asignatura/código y período dentro del departamento. Las comisiones
          y sus combinaciones se detectan automáticamente desde lo que ya está cargado en Comisiones; no hace falta repetir los
          alumnos comisión por comisión.
        </Caption>
      </div>
      <SelectorPeriodo data={data} value={nombre} onChange={setNombre} label="Período" />
      {q.error && <FeedbackBox feedback={q.error} />}
      {q.loading && !q.data && <Cargando />}
      {q.data && periodo && (
        <Contenido key={`${periodo.id}-${version}`} d={q.data} periodoId={periodo.id} puede={data.permisos.puede_escribir} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

function Contenido({
  d,
  periodoId,
  puede,
  onDone,
  onError,
}: {
  d: InscriptosData;
  periodoId: number;
  puede: boolean;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const filas = useMemo(() => d.filas ?? [], [d.filas]);
  const [edicion, setEdicion] = useState<Edicion>(() =>
    Object.fromEntries(filas.map((f) => [f.clave, { cantidad: texto(f.cantidad), cantidad_final: texto(f.cantidad_final) }]))
  );
  const accion = useAccion(onDone, onError);
  const numero = (v: string) => (v.trim() === "" ? null : Number(v));

  async function guardar() {
    await accion.run(() =>
      post<WriteResult>("inscriptos/guardar", {
        periodo_id: periodoId,
        filas: filas.map((f: FilaInscriptos) => ({
          clave: f.clave,
          huella: f.huella,
          cantidad: numero(edicion[f.clave]?.cantidad ?? ""),
          cantidad_final: numero(edicion[f.clave]?.cantidad_final ?? ""),
        })),
      })
    );
  }

  const columnas = d.columnas ?? [];
  return (
    <>
      {d.legacy.length > 0 && (
        <>
          <Aviso
            feedback={{
              tone: "warning",
              text: "Hay cantidades históricas cargadas antes de la discriminación por código en comisiones multicódigo. Se conservan como referencia y no se reparten automáticamente entre asignaturas para evitar inventar datos.",
            }}
          />
          <Details summary="Ver totales históricos pendientes de discriminar">
            <TablaLibre rows={d.legacy} />
          </Details>
        </>
      )}
      {d.vacio ? (
        <Aviso feedback={{ tone: "info", text: "No hay asignaturas vinculadas a comisiones en este período." }} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric label="Asignaturas / códigos" value={d.metricas?.asignaturas ?? 0} />
            <Metric label="Alumnos inscriptos" value={d.metricas?.alumnos ?? 0} />
            <Metric label="Comisiones relacionadas" value={d.metricas?.comisiones ?? 0} />
            <Metric label="Docentes únicos en comisiones" value={d.metricas?.docentes ?? 0} />
          </div>
          <Caption>
            Los alumnos se suman una sola vez por código. La cantidad de comisiones y docentes se deriva de las relaciones reales
            ya cargadas.
          </Caption>
          <h4 className="pt-2 text-base font-semibold text-brand-950">Carga por asignatura / código</h4>
          <Caption>
            Editá únicamente Inscriptos al inicio y Regulares al final. Las columnas de comisiones son informativas y se
            reconstruyen automáticamente desde las comisiones existentes.
          </Caption>
          {!puede && <SoloLectura />}
          <div className="max-h-[28rem] overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  {columnas.map((c) => (
                    <th key={c} className="whitespace-nowrap px-3 py-3 font-medium">
                      {LABELS[c] ?? c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filas.map((f) => (
                  <tr key={f.clave}>
                    {columnas.map((c) =>
                      c === "cantidad" || c === "cantidad_final" ? (
                        <td key={c} className="px-3 py-1.5">
                          <input
                            type="number"
                            min={0}
                            step={1}
                            aria-label={`${LABELS[c]} ${texto(f.codigo_materia)}`}
                            className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-50"
                            value={edicion[f.clave]?.[c] ?? ""}
                            disabled={!puede}
                            onChange={(e) => setEdicion((m) => ({ ...m, [f.clave]: { ...m[f.clave], [c]: e.target.value } }))}
                          />
                        </td>
                      ) : (
                        <td key={c} className="whitespace-nowrap px-3 py-2 text-slate-700">
                          {texto(f[c])}
                        </td>
                      )
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {puede && (
            <PrimaryButton onClick={guardar} busy={accion.busy}>
              💾 Guardar cantidades de inscriptos por asignatura
            </PrimaryButton>
          )}
          <h4 className="pt-2 text-base font-semibold text-brand-950">Conjuntos de comisiones detectados y alumnos por docente</h4>
          <Caption>
            Cada fila es una combinación exacta de asignaturas/códigos tomada de las comisiones cargadas. Si esa misma combinación
            tiene 1, 6 o 12 comisiones, los alumnos se suman una sola vez por código y se comparan con todos los docentes únicos
            (CUIL) que participan en cualquiera de esas comisiones.
          </Caption>
          {(d.grupos ?? []).length ? (
            <TablaLibre rows={d.grupos ?? []} renombres={GRUPOS} />
          ) : (
            <Aviso feedback={{ tone: "info", text: "No hay conjuntos de comisiones disponibles para analizar." }} />
          )}
          <h4 className="pt-2 text-base font-semibold text-brand-950">Historial de inscriptos y regulares por período</h4>
          <Caption>
            El historial conserva una sola cantidad por asignatura/código y período. Las comisiones relacionadas se reconstruyen
            desde la estructura de cada período.
          </Caption>
          {(d.historial ?? []).length ? (
            <>
              <TablaLibre rows={d.historial ?? []} renombres={HISTORIAL} />
              <Details summary="Ver historial por combinación de asignaturas / comisiones">
                {(d.historial_combinaciones ?? []).length ? (
                  <TablaLibre rows={d.historial_combinaciones ?? []} renombres={{ periodo: "Período", ...GRUPOS }} />
                ) : (
                  <Aviso feedback={{ tone: "info", text: "No hay combinaciones históricas con datos." }} />
                )}
              </Details>
            </>
          ) : (
            <Aviso feedback={{ tone: "info", text: "Todavía no hay datos históricos de inscriptos." }} />
          )}
        </>
      )}
    </>
  );
}
