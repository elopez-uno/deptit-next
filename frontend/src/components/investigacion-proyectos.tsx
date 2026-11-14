"use client";

// Pestañas 📚 Proyectos vigentes (render_proyectos_vigentes_v101), ➕ Nuevo proyecto y 🕘 Historial (entry
// l. 65005-65210). El costo salarial (E4-04) sale del motor de Sueldos por la capa de composición y se
// muestra como ESTIMACIÓN (D-E4-02); los actos se eligen del repositorio existente (D2): crear un acto
// nuevo pertenece a Resoluciones y respaldos.
import { useMemo, useState } from "react";
import { Card, Check, Field, PrimaryButton, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  Aviso,
  Caption,
  Cargando,
  Metric,
  SeleccionTabla,
  SelectorActo,
  SoloLectura,
  Tabla,
  TablaLibre,
  type OnError,
  type TabProps,
  filtrar,
  useAccion,
  useConsulta,
} from "@/components/investigacion-shared";
import { type Costos, type Ficha, type Fila, type FilaHuella, type WriteResult, post } from "@/lib/investigacion";

// Etiqueta discreta de la estimación salarial (D-E4-02).
function Estimacion({ costos }: { costos: Costos | null }) {
  if (!costos) return null;
  return (
    <p className="text-xs text-slate-500">
      <span className="mr-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-amber-800">
        {costos.estimacion.etiqueta}
      </span>
      {costos.estimacion.advertencia}
    </p>
  );
}

// --- gestión masiva de actos (_render_gestion_actos_proyectos_masivo_v267) --------------------------------------------
export function GestionActosMasiva({ filas, ...props }: TabProps & { filas: FilaHuella[] }) {
  const { data, version, onDone, onError } = props;
  const [buscar, setBuscar] = useState("");
  const [todos, setTodos] = useState(false);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [acto, setActo] = useState<number | null>(null);
  const accion = useAccion(onDone, onError);
  const vista = useMemo(
    () => filtrar(filas, buscar, ["codigo_proyecto", "nombre_proyecto", "responsable_proyecto_v244", "situacion", "estado", "actos_documentales_v263"]),
    [filas, buscar]
  );
  const elegidas = vista.filter((f) => todos || marcados.has(String(f.id)));
  if (!data.permisos.puede_vincular_acto && !data.permisos.puede_desvincular_acto) return null;
  const cuerpo = {
    documento_id: acto,
    proyecto_ids: elegidas.map((f) => f.id),
    huellas: Object.fromEntries(elegidas.map((f) => [String(f.id), f.huella])),
  };
  return (
    <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">
        🔗 Vincular un acto administrativo a varios proyectos
      </summary>
      <div className="space-y-3 border-t border-slate-100 px-5 py-4">
        <Field label="Buscar proyectos para vincular">
          <TextInput value={buscar} onChange={setBuscar} placeholder="Código, nombre, responsable o estado..." />
        </Field>
        {vista.length === 0 ? (
          <Aviso feedback={{ tone: "warning", text: "No hay proyectos que coincidan con la búsqueda." }} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-6">
              <Check checked={todos} onChange={setTodos} label="Seleccionar todos los proyectos filtrados" />
              <Caption>Proyectos mostrados: {vista.length}</Caption>
            </div>
            <Tabla
              rows={vista}
              rowKey={(r) => String(r.id)}
              checked={todos ? new Set(vista.map((f) => String(f.id))) : marcados}
              onCheck={(k, v) => {
                const s = new Set(marcados);
                if (v) s.add(k);
                else s.delete(k);
                setMarcados(s);
              }}
              maxHeight="max-h-64"
              cols={[
                { key: "codigo_proyecto", label: "Código" },
                { key: "nombre_proyecto", label: "Proyecto" },
                { key: "actos_documentales_v263", label: "Acto administrativo" },
                { key: "responsable_proyecto_v244", label: "Instituto/Área responsable" },
                { key: "situacion", label: "Situación" },
                { key: "estado", label: "Estado" },
                { key: "fecha_inicio", label: "Inicio" },
                { key: "fecha_fin", label: "Fin" },
              ]}
            />
            <Caption>Proyectos seleccionados: {elegidas.length}</Caption>
            {elegidas.length > 0 && (
              <>
                <SelectorActo
                  titulo="Acto administrativo común para los proyectos seleccionados"
                  version={version}
                  value={acto}
                  onChange={setActo}
                  onError={onError}
                />
                {accion.feedback && <Aviso feedback={accion.feedback} />}
                <div className="flex flex-wrap gap-3">
                  {data.permisos.puede_vincular_acto && (
                    <PrimaryButton busy={accion.busy} disabled={acto === null} onClick={() => accion.run(() => post<WriteResult>("actos/vincular", cuerpo))}>
                      🔗 Vincular a los proyectos seleccionados
                    </PrimaryButton>
                  )}
                  {data.permisos.puede_desvincular_acto && (
                    <PrimaryButton tone="secondary" busy={accion.busy} disabled={acto === null} onClick={() => accion.run(() => post<WriteResult>("actos/desvincular", cuerpo))}>
                      Quitar ese acto de los proyectos seleccionados
                    </PrimaryButton>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </details>
  );
}

// --- 📚 Proyectos vigentes --------------------------------------------------------------------------------------------
type Vigentes = { caption: string; filas: FilaHuella[]; lista: Fila[] };

export function VigentesTab(props: TabProps) {
  const { version, onError } = props;
  const r = useConsulta<Vigentes>("vigentes", {}, onError, version);
  const c = useConsulta<Costos>("costos", {}, onError, version);
  const costos = c.data;
  const costoDe = (id: number) => costos?.proyectos.find((p) => p.proyecto_id === id)?.costo_tabla ?? "…";
  // Listado completo: misma vista y mismo orden que la tabla; la columna va después de "Meses de ejecución" (l. 33620).
  const lista = useMemo(() => {
    const filasV = r.data?.filas ?? [];
    const alineado =
      !!costos && costos.proyectos.length === filasV.length && costos.proyectos.every((p, i) => p.proyecto_id === filasV[i].id);
    return (r.data?.lista ?? []).map((fila, i) =>
      Object.fromEntries(
        Object.entries(fila).flatMap(([k, v]) =>
          k === "meses_ejecucion_v258"
            ? [[k, v], ["costo_total_sueldos_txt_v258", alineado ? costos!.proyectos[i].costo_tabla : "…"]]
            : [[k, v]]
        )
      )
    ) as Fila[];
  }, [r.data, costos]);
  const [elegido, setSel] = useState<number | null>(null);
  const filas = r.data?.filas;
  // seleccionar_registro_desde_tabla: por defecto, la primera fila.
  const sel = filas?.some((f) => f.id === elegido) ? elegido : (filas?.[0]?.id ?? null);
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Proyectos vigentes</h3>
      {r.error && <Aviso feedback={r.error} />}
      {c.error && <Aviso feedback={c.error} />}
      {!r.data ? (
        <Cargando />
      ) : (
        <>
          <Caption>{r.data.caption}</Caption>
          {r.data.filas.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay proyectos vigentes para el período actual." }} />
          ) : (
            <>
              <GestionActosMasiva {...props} filas={r.data.filas} />
              <p className="text-sm font-semibold text-slate-800">Proyectos vigentes</p>
              <Tabla
                rows={r.data.filas}
                rowKey={(f) => String(f.id)}
                selected={sel === null ? null : String(sel)}
                onSelect={(k) => setSel(Number(k))}
                render={(f, key) => (key === "costo" ? costoDe(f.id) : undefined)}
                cols={[
                  { key: "codigo_proyecto", label: "Código" },
                  { key: "nombre_proyecto", label: "Proyecto" },
                  { key: "actos_documentales_v263", label: "Acto administrativo" },
                  { key: "responsable_proyecto_v244", label: "Instituto/Área responsable" },
                  { key: "horas_semanales", label: "Horas semanales" },
                  { key: "meses_ejecucion_v258", label: "Meses de ejecución" },
                  { key: "costo" as keyof FilaHuella & string, label: "Costo total sueldos" },
                  { key: "horas_totales_periodo", label: "Horas totales del período" },
                  { key: "situacion", label: "Situación" },
                  { key: "estado", label: "Estado" },
                  { key: "fecha_inicio", label: "Inicio" },
                  { key: "fecha_fin", label: "Fin" },
                  { key: "departamento_creador", label: "Departamento creador" },
                ]}
              />
              <Estimacion costos={costos} />
              {sel !== null && <FichaProyecto {...props} proyectoId={sel} fila={r.data.filas.find((f) => f.id === sel)!} costos={costos} />}
              <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
                <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">
                  📋 Ver listado completo de proyectos vigentes
                </summary>
                <div className="border-t border-slate-100 px-5 py-4">
                  <TablaLibre
                    rows={lista}
                    renombres={{
                      nombre_proyecto: "Proyecto", codigo_proyecto: "Código", actos_documentales_v263: "Acto administrativo",
                      instituto_proyecto: "Instituto / Departamento responsable", anio_llamado: "Año de llamado",
                      fecha_inicio: "Inicio", fecha_fin: "Fin", periodo_ejecucion: "Período de ejecución",
                      situacion: "Situación", estado: "Estado", departamento_creador: "Departamento creador",
                      docentes_periodo_activo: "Docentes activos", asignaciones_periodo_activo: "Asignaciones activas",
                      horas_semanales: "Horas semanales", meses_ejecucion_v258: "Meses de ejecución",
                      costo_total_sueldos_txt_v258: "Costo total sueldos",
                      horas_totales_periodo: "Horas totales del período", docentes_historicos_v102: "Docentes históricos",
                      asignaciones_historicas_v102: "Asignaciones históricas", horas_historicas_v102: "Horas históricas",
                      fecha_carga: "Fecha de carga", fecha_suspension: "Fecha suspensión",
                      motivo_suspension: "Motivo suspensión", observaciones: "Observaciones",
                    }}
                  />
                </div>
              </details>
            </>
          )}
        </>
      )}
    </section>
  );
}

function FichaProyecto({
  proyectoId,
  fila,
  costos,
  ...props
}: TabProps & { proyectoId: number; fila: FilaHuella; costos: Costos | null }) {
  const { data, version, onDone, onError } = props;
  const r = useConsulta<Ficha>("vigentes/ficha", { proyecto_id: proyectoId }, onError, version);
  const [acto, setActo] = useState<number | null>(null);
  const accion = useAccion(onDone, onError);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data || r.data.proyecto_id !== proyectoId) return <Cargando text="Cargando la ficha del proyecto…" />;
  const f = r.data;
  const costo = costos?.proyectos.find((p) => p.proyecto_id === proyectoId);
  const imputado = (id: number | null) => costos?.integrantes.find((x) => x.asignacion_id === id);
  const p = f.participacion;
  const h = f.historico_contexto;
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <p className="text-lg font-semibold leading-snug text-brand-950">{f.encabezado.nombre}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="rounded-full border border-slate-300 px-2 py-0.5">{f.encabezado.codigo}</span>
          <span className="rounded-full border border-slate-300 px-2 py-0.5">{f.encabezado.situacion}</span>
          <span className="rounded-full border border-slate-300 px-2 py-0.5">Estado: {f.encabezado.estado}</span>
        </div>
      </div>
      <h4 className="text-base font-semibold text-brand-950">📌 Datos del proyecto</h4>
      <div className="grid gap-4 md:grid-cols-3">
        <Dato titulo="Instituto / Departamento responsable" valor={f.datos.area} />
        <Dato titulo="Período de ejecución" valor={f.datos.periodo_ejecucion} />
        <Dato titulo="Departamento creador" valor={f.datos.creador} />
        <Dato titulo="Vigencia" valor={`${f.datos.inicio} → ${f.datos.fin}`} />
        <Dato titulo="Año de llamado" valor={f.datos.anio} />
        <Dato titulo="Fecha de carga" valor={f.datos.fecha_carga} />
      </div>
      <h4 className="text-base font-semibold text-brand-950">📄 Actos administrativos vinculados</h4>
      {f.actos.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Este proyecto todavía no tiene un acto administrativo vinculado en Resoluciones y respaldos." }} />
      ) : (
        <Tabla
          rows={f.actos}
          rowKey={(a) => String(a.documento_id)}
          cols={[
            { key: "codigo", label: "Código" },
            { key: "dependencia_emisora", label: "Dependencia emisora" },
            { key: "fecha", label: "Fecha" },
            { key: "categoria", label: "Respalda" },
            { key: "detalle", label: "Detalle" },
          ]}
        />
      )}
      {data.permisos.puede_vincular_acto && (
        <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">🔗 Acto administrativo del proyecto</summary>
          <div className="space-y-3 border-t border-slate-100 px-5 py-4">
            {f.actos.length === 0 && <Caption>Pendiente de vincular: el proyecto todavía no tiene acto administrativo asociado.</Caption>}
            <SelectorActo titulo="Buscar acto administrativo en el repositorio" version={version} value={acto} onChange={setActo} onError={onError} />
            {accion.feedback && <Aviso feedback={accion.feedback} />}
            <PrimaryButton
              busy={accion.busy}
              disabled={acto === null}
              onClick={() =>
                accion.run(() =>
                  post<WriteResult>("actos/vincular", {
                    documento_id: acto,
                    proyecto_ids: [proyectoId],
                    huellas: { [String(proyectoId)]: fila.huella },
                    individual: true,
                  })
                )
              }
            >
              🔗 Vincular acto al proyecto
            </PrimaryButton>
          </div>
        </details>
      )}
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Horas semanales del proyecto" value={f.metricas.horas_semanales} />
        <Metric label="Costo total en sueldos" value={costo?.costo_ficha ?? "…"} />
        <Metric label="Meses de ejecución" value={f.metricas.meses} />
        <Metric label="Horas totales del período" value={f.metricas.horas_totales} />
      </div>
      {costo && <Caption>{costo.leyenda}</Caption>}
      <Estimacion costos={costos} />
      {(f.datos.fecha_suspension || f.datos.motivo_suspension) && (
        <Aviso
          feedback={{
            tone: "warning",
            text: `${f.datos.fecha_suspension || "Sin fecha informada"}${f.datos.motivo_suspension ? ` · ${f.datos.motivo_suspension}` : ""}`,
          }}
        />
      )}
      {f.datos.observaciones && <Caption>Observaciones: {f.datos.observaciones}</Caption>}
      <h4 className="text-base font-semibold text-brand-950">👥 Participación docente</h4>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <p className="text-sm font-semibold">
            {f.periodo_activo ? `${h ? "Período en contexto" : "Período activo"} · ${f.periodo_activo}` : "Período activo · sin período abierto"}
          </p>
          <Caption>
            {!f.periodo_activo
              ? "No hay asignaciones activas hasta que exista un nuevo período abierto."
              : h
                ? "Se muestran únicamente las asignaciones que seguían vigentes al cierre del período."
                : "Solo se cuentan asignaciones vigentes del período actualmente abierto."}
          </Caption>
          <div className="grid grid-cols-2 gap-3">
            <Metric label={h ? "Docentes al cierre" : "Docentes activos"} value={p.docentes_activos} />
            <Metric label={h ? "Asignaciones al cierre" : "Asignaciones activas"} value={p.asignaciones_activas} />
            <Metric label="Horas semanales del proyecto" value={p.horas_activas} />
            <Metric label={h ? "Departamentos al cierre" : "Departamentos activos"} value={p.departamentos_activos} />
          </div>
        </Card>
        <Card>
          <p className="text-sm font-semibold">Histórico del proyecto</p>
          <Caption>Acumula las participaciones que computaron. Las bajas se conservan en el historial, pero no suman asignaciones ni horas históricas.</Caption>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Docentes históricos" value={p.docentes_historicos} />
            <Metric label="Asignaciones históricas" value={p.asignaciones_historicas} />
            <Metric label="Horas históricas" value={p.horas_historicas} />
            <Metric label="Departamentos históricos" value={p.departamentos_historicos} />
          </div>
        </Card>
      </div>
      <h4 className="text-base font-semibold text-brand-950">{h ? "👥 Integrantes vigentes al cierre" : "👥 Integrantes del período activo"}</h4>
      {!f.periodo_activo ? (
        <Aviso feedback={{ tone: "info", text: "No hay un período abierto. Los integrantes de períodos anteriores se consultan en el historial." }} />
      ) : f.integrantes.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: h ? `No hay integrantes registrados en ${f.periodo_activo}.` : `No hay integrantes activos asignados en ${f.periodo_activo}.` }} />
      ) : (
        <div className="space-y-2">
          <Caption>{h ? `Participaciones vigentes al cierre de ${f.periodo_activo}` : `Participaciones activas en ${f.periodo_activo}`}</Caption>
          {f.integrantes.map((i, n) => (
            <div key={n} className="grid gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm md:grid-cols-[2.4fr_1.2fr_1fr_1.35fr]">
              <div>
                <p className="font-semibold">👤 {i.docente}</p>
                <Caption>CUIL {i.cuil} · {i.departamento}</Caption>
                {imputado(i.id) && <Caption>{imputado(i.id)!.detalle_salarial}</Caption>}
                {i.observaciones && <Caption>Observaciones: {i.observaciones}</Caption>}
              </div>
              <Dato titulo="Rol" valor={i.rol} />
              <Dato titulo="Horas semanales asignadas" valor={i.horas} />
              <div>
                <Caption>Costo total imputado</Caption>
                <p className="font-semibold">{costos ? (imputado(i.id)?.costo ?? costos.sin_costo) : "…"}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      {f.historial.length > 0 && (
        <details className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-800">🕘 Ver historial completo de asignaciones e integrantes</summary>
          <div className="border-t border-slate-100 px-5 py-4">
            <TablaLibre
              rows={f.historial}
              renombres={{
                periodo: "Período", departamento_origen_docente: "Departamento de origen", docente: "Docente", cuil: "CUIL",
                rol: "Rol", horas_asignadas: "Horas semanales", estado_asignacion: "Estado", fecha_carga: "Fecha de carga",
                fecha_baja: "Fecha de baja", motivo_baja: "Motivo de baja", observaciones: "Observaciones",
                computa: "Computa en histórico",
              }}
            />
          </div>
        </details>
      )}
    </div>
  );
}

function Dato({ titulo, valor }: { titulo: string; valor: string | number | null | undefined }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className="text-sm font-semibold text-slate-800">{valor ?? ""}</p>
    </div>
  );
}

// --- ➕ Nuevo proyecto -----------------------------------------------------------------------------------------------
export function NuevoTab(props: TabProps) {
  const { data, version, onDone, onError } = props;
  const anio = new Date().getFullYear();
  const [f, setF] = useState({
    nombre: "", codigo: "", instituto: "", anio_llamado: String(anio), fecha_inicio: `${anio}-01-01`,
    fecha_fin: `${anio + 1}-12-31`, estado: "Activo", observaciones: "",
  });
  const [acto, setActo] = useState<number | null>(null);
  const accion = useAccion(onDone, onError);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Registrar nuevo proyecto institucional</h3>
        <Caption>
          El proyecto se verá automáticamente en todos los departamentos. El departamento actual quedará registrado como creador
          y administrador del proyecto.
        </Caption>
      </div>
      {!data.permisos.puede_escribir && <SoloLectura />}
      <Card>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <Field label="Nombre del proyecto"><TextInput value={f.nombre} onChange={set("nombre")} /></Field>
            <Field label="Código interno del proyecto"><TextInput value={f.codigo} onChange={set("codigo")} /></Field>
            <Field label="Instituto/Departamento de radicación (si corresponde)" hint={`ℹ️ ${data.ayuda_radicacion}`}>
              <TextInput value={f.instituto} onChange={set("instituto")} placeholder="Dejar vacío si radica en este departamento" />
            </Field>
            <Field label="Año de llamado"><TextInput type="number" value={f.anio_llamado} onChange={set("anio_llamado")} /></Field>
          </div>
          <div className="space-y-3">
            <Field label="Fecha de inicio"><TextInput type="date" value={f.fecha_inicio} onChange={set("fecha_inicio")} /></Field>
            <Field label="Fecha de finalización"><TextInput type="date" value={f.fecha_fin} onChange={set("fecha_fin")} /></Field>
            <Field
              label="Estado administrativo"
              hint="La situación visible se calcula con las fechas: programado, en ejecución o finalizado. El estado administrativo permite suspender o finalizar manualmente."
            >
              <Select value={f.estado} options={data.estados_alta} onChange={set("estado")} />
            </Field>
          </div>
        </div>
        <Field label="Observaciones del proyecto"><Textarea value={f.observaciones} onChange={set("observaciones")} /></Field>
        <SelectorActo titulo="Acto administrativo que aprueba el proyecto (opcional)" version={version} value={acto} onChange={setActo} onError={onError} />
        {accion.feedback && <Aviso feedback={accion.feedback} />}
        <PrimaryButton
          busy={accion.busy}
          disabled={!data.permisos.puede_escribir}
          onClick={() =>
            accion.run(
              () => post<WriteResult>("proyecto/guardar", { ...f, anio_llamado: Number(f.anio_llamado), documento_id: acto }),
              () => {
                setF({ ...f, nombre: "", codigo: "", instituto: "", observaciones: "" });
                setActo(null);
              }
            )
          }
        >
          💾 Guardar proyecto
        </PrimaryButton>
      </Card>
    </section>
  );
}

// --- 🕘 Historial ---------------------------------------------------------------------------------------------------
export function HistorialTab(props: TabProps) {
  const { version, onError } = props;
  const r = useConsulta<{ filas: FilaHuella[]; situaciones: string[] }>("historial", {}, onError, version);
  const [situacion, setSituacion] = useState("Todos");
  const [sel, setSel] = useState<number | null>(null);
  const filtradas = useMemo(
    () => (r.data?.filas ?? []).filter((f) => situacion === "Todos" || f.situacion === situacion),
    [r.data, situacion]
  );
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Historial completo de proyectos</h3>
        <Caption>Los proyectos finalizados, suspendidos o archivados permanecen registrados. También se conservan las asignaciones dadas de baja.</Caption>
      </div>
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : r.data.filas.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Todavía no hay proyectos registrados." }} />
      ) : (
        <>
          <Field label="Filtrar por situación">
            <Select value={situacion} options={r.data.situaciones} onChange={setSituacion} />
          </Field>
          <Tabla
            rows={filtradas}
            rowKey={(f) => String(f.id)}
            cols={[
              { key: "nombre_proyecto", label: "nombre_proyecto" },
              { key: "codigo_proyecto", label: "codigo_proyecto" },
              { key: "actos_documentales_v263", label: "Acto administrativo" },
              { key: "instituto_proyecto", label: "instituto_proyecto" },
              { key: "anio_llamado", label: "anio_llamado" },
              { key: "fecha_inicio", label: "fecha_inicio" },
              { key: "fecha_fin", label: "fecha_fin" },
              { key: "situacion", label: "situacion" },
              { key: "estado", label: "estado" },
              { key: "fecha_suspension", label: "fecha_suspension" },
              { key: "motivo_suspension", label: "motivo_suspension" },
              { key: "departamento_creador", label: "departamento_creador" },
              { key: "cantidad_departamentos", label: "cantidad_departamentos" },
              { key: "cantidad_docentes_historicos", label: "cantidad_docentes_historicos" },
              { key: "cantidad_asignaciones_historicas", label: "cantidad_asignaciones_historicas" },
              { key: "horas_asignadas_historicas", label: "horas_asignadas_historicas" },
              { key: "observaciones", label: "observaciones" },
            ]}
          />
          <GestionActosMasiva {...props} filas={filtradas} />
          <SeleccionTabla
            filas={filtradas}
            busquedaCols={["codigo_proyecto", "nombre_proyecto", "instituto_proyecto", "anio_llamado", "departamento_creador", "situacion", "estado"]}
            etiquetaBuscar="Buscar proyecto en el historial"
            placeholder="Código, proyecto, instituto, año, departamento..."
            titulo="Seleccioná un proyecto para ver sus asignaciones"
            value={sel}
            onChange={setSel}
            cols={[
              { key: "codigo_proyecto", label: "Código" },
              { key: "nombre_proyecto", label: "Proyecto" },
              { key: "instituto_proyecto", label: "Instituto" },
              { key: "anio_llamado", label: "Año" },
              { key: "fecha_inicio", label: "Inicio" },
              { key: "fecha_fin", label: "Fin" },
              { key: "situacion", label: "Situación" },
              { key: "estado", label: "Estado" },
              { key: "departamento_creador", label: "Departamento creador" },
            ]}
          />
          {sel !== null && <AsignacionesHistorial proyectoId={sel} version={version} onError={onError} />}
        </>
      )}
    </section>
  );
}

function AsignacionesHistorial({ proyectoId, version, onError }: { proyectoId: number; version: number; onError: OnError }) {
  const r = useConsulta<{ filas: Fila[] }>("historial/asignaciones", { proyecto_id: proyectoId }, onError, version);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data) return <Cargando />;
  if (!r.data.filas.length) return <Aviso feedback={{ tone: "info", text: "El proyecto no registra asignaciones." }} />;
  return <TablaLibre rows={r.data.filas} />;
}
