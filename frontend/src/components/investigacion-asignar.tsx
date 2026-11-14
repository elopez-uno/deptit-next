"use client";

// Pestañas 👥 Asignar docentes (_render_asignacion_docentes_proyecto_v217 l. 48390 + selector único v270) y 📋 Asignaciones
// (entry l. 65104-65130). El padrón es el del Consolidado institucional (v276/v240, decisión D4); la capacidad v184 es
// solo una advertencia (v187): nunca bloquea ni reduce horas. Cada docente = alta + movimiento (operaciones independientes).
import { useMemo, useState } from "react";
import { Card, Check, Field, PrimaryButton, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  Aviso,
  Caption,
  Cargando,
  SeleccionTabla,
  SoloLectura,
  Tabla,
  TablaLibre,
  type TabProps,
  filtrar,
  useAccion,
  useConsulta,
} from "@/components/investigacion-shared";
import { type AsignarDetalle, type Capacidad, type Fila, type FilaHuella, type Periodo, type WriteResult, g, post } from "@/lib/investigacion";

type Config = { rol: string; horas: string; observaciones: string };

export function AsignarTab(props: TabProps) {
  const { data, version, onError } = props;
  const r = useConsulta<{ periodo: Periodo | null; proyectos: FilaHuella[] }>("asignar/proyectos", {}, onError, version);
  const [elegido, setSel] = useState<number | null>(null);
  const proyectos = r.data?.proyectos;
  const sel = elegido ?? proyectos?.[0]?.id ?? null;
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Asignar docentes a un proyecto</h3>
        <Caption>El catálogo de proyectos es institucional. La asignación que realices quedará asociada únicamente al departamento actual.</Caption>
      </div>
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : !r.data.periodo ? (
        <Aviso feedback={{ tone: "warning", text: "No hay período abierto. Primero creá o abrí un período." }} />
      ) : r.data.proyectos.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: "No hay proyectos activos cuyas fechas cubran el período abierto. Revisá las fechas de inicio y finalización del proyecto." }} />
      ) : (
        <>
          {!data.permisos.puede_escribir && <SoloLectura />}
          <SeleccionTabla
            filas={r.data.proyectos}
            busquedaCols={["codigo_proyecto", "nombre_proyecto", "instituto_proyecto", "anio_llamado", "situacion", "estado"]}
            etiquetaBuscar="Buscar proyecto"
            placeholder="Código, nombre, instituto, año o situación..."
            titulo="Proyectos encontrados"
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
            ]}
            vacio="No hay proyectos que coincidan con la búsqueda."
          />
          {sel !== null && r.data.proyectos.some((p) => p.id === sel) && (
            <DetalleProyecto key={sel} {...props} proyecto={r.data.proyectos.find((p) => p.id === sel)!} />
          )}
        </>
      )}
    </section>
  );
}

function DetalleProyecto({ proyecto, ...props }: TabProps & { proyecto: FilaHuella }) {
  const { data, version, onDone, onError } = props;
  const r = useConsulta<AsignarDetalle>("asignar/detalle", { proyecto_id: proyecto.id }, onError, version);
  const [buscar, setBuscar] = useState("");
  const [todos, setTodos] = useState(false);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [cfg, setCfg] = useState<Record<string, Config>>({});
  const accion = useAccion(onDone, onError);
  const docentes = useMemo(
    () => filtrar(r.data?.docentes ?? [], buscar, ["nombre_completo", "cuil", "legajo", "cargo_final", "cargo", "tipo_docente", "departamento_origen"]),
    [r.data, buscar]
  );
  const elegidos = docentes.filter((d) => todos || marcados.has(d.cuil));
  const cuiles = elegidos.map((d) => d.cuil);
  const cap = useConsulta<{ capacidades: Record<string, Capacidad> }>("capacidad", { cuiles }, onError, version, cuiles.length > 0);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data) return <Cargando />;
  const d = r.data;
  const conf = (cuil: string): Config => cfg[cuil] ?? { rol: "Integrante", horas: "0", observaciones: "" };
  const setConf = (cuil: string, patch: Partial<Config>) => setCfg({ ...cfg, [cuil]: { ...conf(cuil), ...patch } });
  const horasTot = d.integrantes.reduce((s, i) => s + Number(i.horas_asignadas ?? 0), 0);
  return (
    <div className="space-y-4">
      <Card>
        <p className="text-sm font-semibold">Datos del proyecto seleccionado</p>
        <div className="grid gap-2 text-sm md:grid-cols-3">
          {(["nombre_proyecto", "codigo_proyecto", "instituto_proyecto", "anio_llamado", "fecha_inicio", "fecha_fin"] as const).map((k) => (
            <p key={k}>
              <span className="text-xs text-slate-500">{k}: </span>
              {String(proyecto[k] ?? "")}
            </p>
          ))}
        </div>
      </Card>
      <h4 className="text-base font-semibold text-brand-950">Docentes asignados hasta el momento</h4>
      {d.integrantes.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Todavía no hay docentes asignados a este proyecto para el cuatrimestre abierto." }} />
      ) : (
        <>
          <Tabla
            rows={d.integrantes}
            rowKey={(f) => String(f.id)}
            cols={[
              { key: "docente", label: "Docente" },
              { key: "cuil", label: "CUIL" },
              { key: "rol", label: "Rol" },
              { key: "horas_asignadas", label: "Horas semanales" },
              { key: "departamento_origen_docente", label: "Departamento de origen" },
              { key: "periodo", label: "Período" },
              { key: "observaciones", label: "Observaciones" },
              { key: "fecha_carga", label: "Fecha de carga" },
            ]}
          />
          <Caption>
            Docentes: {new Set(d.integrantes.map((i) => String(i.cuil))).size} | Asignaciones activas: {d.integrantes.length} | Horas
            semanales: {g(horasTot)}
          </Caption>
          {d.duplicados_legacy && (
            <Aviso feedback={{ tone: "warning", text: "Se detectaron docentes duplicados que fueron cargados en versiones anteriores. Las nuevas asignaciones duplicadas quedan bloqueadas; podés eliminar las incorrectas debajo." }} />
          )}
        </>
      )}
      <h4 className="text-base font-semibold text-brand-950">Nueva asignación</h4>
      {d.padron.consolidado !== null && (
        <Caption>
          Control con Consolidado institucional: <b>{d.padron.consolidado} docentes únicos por CUIL</b> · Padrón del selector antes
          de excluir ya asignados: <b>{d.padron.selector ?? 0}</b>.
        </Caption>
      )}
      {d.padron.diagnosticos.length > 0 && (
        <>
          <Aviso feedback={{ tone: "warning", text: "Se detectaron datos legacy/inconsistentes en designaciones usadas para mostrar Cargo/Dedicación/Horas. Eso ya no elimina al docente del padrón: la habilitación sale directamente del Consolidado institucional." }} />
          <details className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm">
            <summary className="cursor-pointer">🔎 Ver diagnóstico de la fuente de docentes</summary>
            {d.padron.diagnosticos.map((m, i) => (
              <p key={i}>• {m}</p>
            ))}
          </details>
        </>
      )}
      {d.docentes.length === 0 && !buscar ? (
        <Aviso feedback={{ tone: "warning", text: "No hay docentes con designación docente Activa en el período académico seleccionado en la institución." }} />
      ) : (
        <Card>
          <Caption>
            La lista usa exactamente el padrón de docentes activos del Consolidado institucional, deduplicado por CUIL. Las
            designaciones solo enriquecen Cargo/Dedicación/Horas y nunca eliminan a una persona del selector. Seleccioná uno o
            varios; para cada docente marcado se habilitan debajo sus propios campos de rol y horas semanales.
          </Caption>
          <Field label="Buscar docentes">
            <TextInput value={buscar} onChange={setBuscar} placeholder="Nombre, CUIL, legajo, cargo o tipo..." />
          </Field>
          {docentes.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay docentes disponibles con ese filtro que no estén ya asignados a este proyecto." }} />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-6">
                <Check checked={todos} onChange={setTodos} label="Seleccionar todos los docentes filtrados" />
                <Caption>Docentes disponibles con el filtro actual: <b>{docentes.length}</b>. Podés marcar uno o varios.</Caption>
              </div>
              <Tabla
                rows={docentes.map((x) => ({ ...x, cargo_txt: x.cargo_final || x.cargo }))}
                rowKey={(x) => x.cuil}
                checked={todos ? new Set(docentes.map((x) => x.cuil)) : marcados}
                onCheck={(k, v) => {
                  const s = new Set(marcados);
                  if (v) s.add(k);
                  else s.delete(k);
                  setMarcados(s);
                }}
                maxHeight="max-h-72"
                cols={[
                  { key: "nombre_completo", label: "Docente" },
                  { key: "cuil", label: "CUIL" },
                  { key: "legajo", label: "Legajo" },
                  { key: "cargo_txt", label: "Cargo" },
                  { key: "horas_designadas", label: "Horas designadas" },
                  { key: "tipo_docente", label: "Tipo" },
                  { key: "departamento_origen", label: "Departamento de origen" },
                ]}
              />
              <Caption>Docentes seleccionados: <b>{elegidos.length}</b></Caption>
            </>
          )}
          {elegidos.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-semibold">Rol y horas de los docentes seleccionados</p>
              <Caption>Los valores son independientes para cada docente. Investigación permite 0 hs; en Extensión las horas deben ser mayores a 0.</Caption>
              {elegidos.map((x) => {
                const c = conf(x.cuil);
                const capacidad = cap.data?.capacidades?.[x.cuil];
                const horas = Number(c.horas || 0);
                return (
                  <div key={x.cuil} className="space-y-2 rounded-xl border border-slate-200 px-4 py-3">
                    <p className="text-sm font-semibold">
                      {x.nombre_completo || x.cuil} · <code>{x.cuil}</code>
                    </p>
                    <div className="grid gap-3 md:grid-cols-2">
                      <Field label="Rol del docente en el proyecto">
                        <TextInput value={c.rol} onChange={(v) => setConf(x.cuil, { rol: v })} placeholder="Ej.: Director, Codirector, Integrante, Becario, Colaborador" />
                      </Field>
                      <Field label="Horas semanales asignadas al docente" hint="Se permiten 0 hs para dejar al docente formalmente vinculado al proyecto sin consumir horas de dedicación.">
                        <TextInput type="number" value={c.horas} onChange={(v) => setConf(x.cuil, { horas: v })} />
                      </Field>
                    </div>
                    {horas === 0 && <Caption>0 hs: quedará vinculado al proyecto sin consumir dedicación.</Caption>}
                    {capacidad && <Caption>{capacidad.mensaje}</Caption>}
                    {capacidad && horas > capacidad.horas_disponibles_proyectos + 1e-9 && (
                      <Aviso
                        feedback={{
                          tone: "warning",
                          text: `⚠️ Se están asignando ${g(horas)} hs y a este docente le quedan ${g(capacidad.horas_disponibles_proyectos)} hs disponibles para Investigación/Extensión. Se puede guardar igualmente; el exceso quedará señalado por el sistema.`,
                        }}
                      />
                    )}
                    <Field label="Observaciones de esta asignación (opcional)">
                      <Textarea value={c.observaciones} onChange={(v) => setConf(x.cuil, { observaciones: v })} />
                    </Field>
                  </div>
                );
              })}
              {accion.feedback && <Aviso feedback={accion.feedback} />}
              <PrimaryButton
                busy={accion.busy}
                disabled={!data.permisos.puede_escribir}
                onClick={() =>
                  accion.run(
                    () =>
                      post<WriteResult>("asignar", {
                        proyecto_id: proyecto.id,
                        huella_proyecto: proyecto.huella,
                        huella_periodo: data.huella_periodo,
                        huella_integrantes: d.huella_integrantes,
                        docentes: elegidos.map((x) => ({
                          cuil: x.cuil,
                          rol: conf(x.cuil).rol,
                          horas: Number(conf(x.cuil).horas || 0),
                          observaciones: conf(x.cuil).observaciones,
                        })),
                      }),
                    () => {
                      setMarcados(new Set());
                      setTodos(false);
                      setCfg({});
                    }
                  )
                }
              >
                💾 Asignar {elegidos.length} docente/s al proyecto
              </PrimaryButton>
            </div>
          )}
        </Card>
      )}
      <EliminarPorError {...props} proyectoId={proyecto.id} eliminables={d.eliminables} />
    </div>
  );
}

function EliminarPorError({ proyectoId, eliminables, ...props }: TabProps & { proyectoId: number; eliminables: FilaHuella[] }) {
  const { data, onDone, onError } = props;
  const [sel, setSel] = useState<number | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3 border-t border-slate-200 pt-4">
      <h4 className="text-base font-semibold text-brand-950">Eliminar una asignación cargada por error</h4>
      <Caption>Esta acción borra definitivamente la asignación seleccionada y no la deja en el historial. No uses esta opción para una baja real del docente.</Caption>
      {eliminables.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "No hay asignaciones de este proyecto que puedas eliminar definitivamente desde el departamento actual." }} />
      ) : (
        <>
          <p className="text-sm font-semibold">Asignaciones que pueden eliminarse</p>
          <Tabla
            rows={eliminables}
            rowKey={(f) => String(f.id)}
            selected={sel === null ? null : String(sel)}
            onSelect={(k) => setSel(Number(k))}
            cols={[
              { key: "docente", label: "Docente" },
              { key: "cuil", label: "CUIL" },
              { key: "rol", label: "Rol" },
              { key: "horas_asignadas", label: "Horas semanales" },
              { key: "departamento_origen_docente", label: "Departamento de origen" },
              { key: "periodo", label: "Período" },
              { key: "estado_asignacion", label: "Estado" },
            ]}
          />
          {data.permisos.puede_borrar ? (
            <>
              <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que esta asignación fue cargada por error y quiero borrarla sin historial" />
              {accion.feedback && <Aviso feedback={accion.feedback} />}
              <PrimaryButton
                tone="danger"
                busy={accion.busy}
                onClick={() =>
                  accion.run(() =>
                    post<WriteResult>("asignar/eliminar-error", {
                      proyecto_id: proyectoId,
                      asignacion_id: sel,
                      huella: eliminables.find((f) => f.id === sel)?.huella ?? null,
                      confirmar,
                    })
                  )
                }
              >
                🗑️ Eliminar asignación definitivamente
              </PrimaryButton>
            </>
          ) : (
            <Caption>La eliminación definitiva está reservada al rol superadmin.</Caption>
          )}
        </>
      )}
    </div>
  );
}

// --- 📋 Asignaciones ----------------------------------------------------------------------------------------------
export function AsignacionesTab({ data, version, onError }: TabProps) {
  const nombres = data.periodos.map((p) => String(p.nombre));
  const porDefecto = data.abierto && nombres.includes(String(data.abierto.nombre)) ? String(data.abierto.nombre) : nombres[0] ?? "";
  const [nombre, setNombre] = useState(porDefecto);
  const periodo = data.periodos.find((p) => String(p.nombre) === nombre);
  const r = useConsulta<{ filas: Fila[]; caption: string }>("asignaciones", { periodo_id: periodo?.id ?? null }, onError, version, !!periodo);
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Asignaciones por período</h3>
      {data.periodos.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: "Todavía no hay períodos registrados." }} />
      ) : (
        <>
          <Field label="Ver período">
            <Select value={nombre} options={nombres} onChange={setNombre} />
          </Field>
          {r.error && <Aviso feedback={r.error} />}
          {!r.data ? (
            <Cargando />
          ) : r.data.filas.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay docentes asignados a proyectos para ese período." }} />
          ) : (
            <>
              <TablaLibre rows={r.data.filas} />
              <Caption>{r.data.caption}</Caption>
            </>
          )}
        </>
      )}
    </section>
  );
}
