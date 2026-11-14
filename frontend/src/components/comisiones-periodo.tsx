"use client";

// Pestañas de consulta: "📋 Comisiones del período" (tabla integrada de 23 columnas, v248) y "🚨 Alertas".
import { useState } from "react";
import { Caption, Cargando, Metric, TablaLibre, type TabProps, useConsulta } from "@/components/comisiones-shared";
import { Details, EmptyState, Field, FeedbackBox, Select } from "@/components/module-ui";
import type { Alertas, Overview, PeriodoData } from "@/lib/comisiones";

// Período por defecto de las pestañas con selector (abierto o, si no hay, el actual).
export function periodoPorDefecto(data: Overview): string {
  const base = data.abierto ?? data.actual;
  const nombres = data.periodos.map((p) => String(p.nombre));
  return base && nombres.includes(String(base.nombre)) ? String(base.nombre) : nombres[0];
}

export function SelectorPeriodo({
  data,
  value,
  onChange,
  label,
}: {
  data: Overview;
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  return (
    <div className="max-w-sm">
      <Field label={label}>
        <Select value={value} options={data.periodos.map((p) => String(p.nombre))} onChange={onChange} />
      </Field>
    </div>
  );
}

const RENOMBRES_PERIODO: Record<string, string> = { alumnos_conjunto: "Alumnos del conjunto" };

export function PeriodoTab({ data, version, onError }: TabProps) {
  const [nombre, setNombre] = useState(() => periodoPorDefecto(data));
  const periodo = data.periodos.find((p) => String(p.nombre) === nombre);
  const q = useConsulta<PeriodoData>("periodo", { periodo_id: periodo?.id }, onError, version, !!periodo);
  if (!data.periodos.length) return <EmptyState text="Todavía no hay períodos registrados." />;
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Comisiones por período</h3>
      <SelectorPeriodo data={data} value={nombre} onChange={setNombre} label="Seleccioná el período a consultar" />
      {q.error && <FeedbackBox feedback={q.error} />}
      {q.loading && !q.data && <Cargando />}
      {q.data && q.data.vacio && <FeedbackBox feedback={{ tone: "info", text: "No hay comisiones cargadas en el período seleccionado." }} />}
      {q.data && !q.data.vacio && (
        <>
          <TablaLibre rows={q.data.filas} renombres={RENOMBRES_PERIODO} />
          <Caption>{q.data.caption}</Caption>
          <h4 className="pt-2 text-base font-semibold text-brand-950">Listado auxiliar de horarios y docentes asignados</h4>
          <Details summary="Ver horarios por fila">
            {q.data.horarios.length ? (
              <>
                <TablaLibre rows={q.data.horarios} />
                <Caption>{q.data.caption_horarios}</Caption>
              </>
            ) : (
              <FeedbackBox feedback={{ tone: "info", text: "No hay horarios cargados para las comisiones de este período." }} />
            )}
          </Details>
          <Details summary="Ver docentes asignados por fila">
            {q.data.asignaciones.length ? (
              <>
                <TablaLibre rows={q.data.asignaciones} />
                <Caption>{q.data.caption_asignaciones}</Caption>
              </>
            ) : (
              <FeedbackBox feedback={{ tone: "info", text: "No hay docentes asignados a comisiones en este período." }} />
            )}
          </Details>
        </>
      )}
    </section>
  );
}

export function AlertasTab({ version, onError }: TabProps) {
  const q = useConsulta<Alertas>("alertas", {}, onError, version);
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Alertas del período</h3>
      <Caption>Revisión automática de problemas operativos: superposiciones horarias y comisiones sin docentes asignados.</Caption>
      {q.error && <FeedbackBox feedback={q.error} />}
      {q.loading && !q.data && <Cargando />}
      {q.data && !q.data.periodo && <FeedbackBox feedback={{ tone: "info", text: "No hay período en contexto para analizar alertas." }} />}
      {q.data && q.data.periodo && (
        <>
          <Caption>Período analizado: {q.data.periodo.nombre ?? ""}</Caption>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Metric label="Superposiciones detectadas" value={q.data.superposiciones?.length ?? 0} />
            <Metric label="Comisiones sin docentes" value={q.data.sin_docentes?.length ?? 0} />
          </div>
          <h4 className="pt-2 text-base font-semibold text-brand-950">Superposiciones horarias</h4>
          {q.data.superposiciones?.length ? (
            <>
              <FeedbackBox feedback={{ tone: "warning", text: "Hay docentes asignados a dos o más comisiones con horarios superpuestos. Revisá estas filas." }} />
              <TablaLibre rows={q.data.superposiciones} />
            </>
          ) : (
            <FeedbackBox feedback={{ tone: "success", text: "No se detectaron superposiciones horarias entre comisiones asignadas a docentes." }} />
          )}
          <h4 className="pt-2 text-base font-semibold text-brand-950">Comisiones sin docentes asignados</h4>
          {q.data.sin_docentes?.length ? (
            <>
              <FeedbackBox feedback={{ tone: "warning", text: "Estas comisiones están abiertas pero todavía no tienen docentes asignados." }} />
              <TablaLibre rows={q.data.sin_docentes} />
            </>
          ) : (
            <FeedbackBox feedback={{ tone: "success", text: "No hay comisiones activas sin docentes asignados." }} />
          )}
        </>
      )}
    </section>
  );
}
