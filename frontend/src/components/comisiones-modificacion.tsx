"use client";

// Pestaña "🔁 Modificación de asignaciones" (entry l. 71028-71239): altas y bajas REALES de docentes durante el
// dictado, con movimiento. Solo en el período actual abierto. Subpestañas: Estado actual, Alta, Baja, Historial.
import { useMemo, useState } from "react";
import {
  Aviso,
  Caption,
  Cargando,
  FranjasForm,
  Metric,
  SoloLectura,
  Subtabs,
  Tabla,
  TablaLibre,
  type TabProps,
  seleccionInicial,
  useConsulta,
} from "@/components/comisiones-shared";
import { DateInput, hoyIso, useAccion } from "@/components/designaciones-shared";
import { Check, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  type Detalle,
  type DocenteDisponible,
  type Fila,
  type Lista,
  type Roles,
  type WriteResult,
  claveTexto,
  horasSeleccion,
  post,
} from "@/lib/comisiones";

export const COLS_COMISIONES = [
  { key: "codigo_materia", label: "Código" },
  { key: "asignatura", label: "Asignatura" },
  { key: "materia_especifica", label: "Materia específica" },
  { key: "nombre_comision", label: "Comisión" },
  { key: "turno", label: "Turno" },
  { key: "sede", label: "Sede" },
  { key: "modalidad", label: "Modalidad" },
  { key: "periodo", label: "Período" },
  { key: "carrera", label: "Carrera/s" },
  { key: "horarios", label: "Horarios" },
  { key: "docentes_asignados_detalle", label: "Docentes" },
] as const;

const COLS_DOCENTES = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "tipo_docente", label: "Tipo" },
  { key: "cargo", label: "Cargo" },
  { key: "dedicacion", label: "Dedicación" },
  { key: "horas_designadas", label: "Hs. designadas" },
  { key: "departamento_origen", label: "Departamento de origen" },
] as const;

const SUBTABS = [
  { key: "actual", label: "📌 Estado actual" },
  { key: "alta", label: "➕ Alta docente" },
  { key: "baja", label: "➖ Baja docente" },
  { key: "hist", label: "🕘 Historial" },
] as const;

// mostrar_datos_actuales_seleccion: título y una fila con las columnas pedidas que existan en el registro.
export function Resumen({ titulo, fila, columnas }: { titulo: string; fila: Fila; columnas: string[] }) {
  const datos: Fila = {};
  columnas.filter((c) => c in fila).forEach((c) => (datos[c] = fila[c]));
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      <TablaLibre rows={[datos]} />
    </div>
  );
}

export function EstadoActual({ det, titulo, columnas, vacioHorarios, vacioDocentes, tituloDocentes }: {
  det: Detalle;
  titulo: string;
  columnas: string[];
  vacioHorarios: string;
  vacioDocentes: string;
  tituloDocentes: string;
}) {
  return (
    <div className="space-y-4">
      <Resumen titulo={titulo} fila={det.fila} columnas={columnas} />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric label="Horarios" value={det.metricas.horarios} />
        <Metric label="Horas semanales" value={det.metricas.horas} />
        <Metric label="Docentes activos" value={det.metricas.docentes_activos} />
      </div>
      <h5 className="text-sm font-semibold text-brand-950">Horarios actuales</h5>
      {det.horarios.length ? (
        <TablaLibre rows={det.horarios} ocultar={["id", "comision_id", "etiqueta", "etiqueta_eliminar"]} />
      ) : (
        <Aviso feedback={{ tone: "info", text: vacioHorarios }} />
      )}
      <h5 className="text-sm font-semibold text-brand-950">{tituloDocentes}</h5>
      {det.asignaciones.length ? (
        <TablaLibre rows={det.asignaciones} ocultar={["id", "comision_id", "etiqueta", "etiqueta_baja"]} />
      ) : (
        <Aviso feedback={{ tone: "info", text: vacioDocentes }} />
      )}
    </div>
  );
}

export function ModificacionTab({ data, version, onDone, onError }: TabProps) {
  const [busqueda, setBusqueda] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [sub, setSub] = useState<string>("actual");
  const habilitado = data.puede_operar && !!data.actual;
  const lista = useConsulta<Lista>("lista", { contexto: "modificacion", busqueda }, onError, version, habilitado);
  const filas = useMemo(() => lista.data?.filas ?? [], [lista.data]);
  const cid = filas.some((f) => f.id === sel) ? sel : filas[0]?.id ?? null;
  const det = useConsulta<Detalle>("detalle", { contexto: "modificacion", comision_id: cid }, onError, version, cid !== null);

  if (!data.puede_operar) return <Aviso feedback={{ tone: "warning", text: "Solo podés registrar modificaciones de asignaciones en el período actual abierto." }} />;
  if (!data.actual) return <Aviso feedback={{ tone: "info", text: "No hay período actual para operar cambios de comisiones." }} />;
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Modificación de asignaciones</h3>
      <Aviso
        feedback={{
          tone: "info",
          text: "Usá esta pestaña para modificar asignaciones reales durante el dictado de una comisión. A diferencia de Editar / eliminar, acá queda registro de altas y bajas de docentes en el historial de la comisión y en el resumen del docente.",
        }}
      />
      {lista.error && <FeedbackBox feedback={lista.error} />}
      <Field label="Buscar comisión por código, materia o nombre">
        <TextInput value={busqueda} onChange={setBusqueda} />
      </Field>
      {lista.loading && !lista.data && <Cargando />}
      {lista.data?.aviso && <Aviso feedback={{ tone: "warning", text: lista.data.aviso }} />}
      {filas.length > 0 && (
        <>
          <p className="text-sm font-medium text-slate-700">Comisiones encontradas</p>
          <Tabla rows={filas} cols={[...COLS_COMISIONES]} rowKey={(r) => String(r.id)} selected={cid === null ? null : String(cid)} onSelect={(k) => setSel(Number(k))} maxHeight="max-h-72" />
        </>
      )}
      {det.error && <FeedbackBox feedback={det.error} />}
      {det.data && cid !== null && (
        <div className="space-y-3">
          <h4 className="text-base font-semibold text-brand-950">Comisión seleccionada · {det.data.etiqueta}</h4>
          <Caption>
            Primero revisá la situación actual. Después elegí una acción concreta: alta, baja o historial. Las altas/bajas de esta
            pestaña son cambios reales y quedan registradas.
          </Caption>
          <Subtabs tabs={SUBTABS} value={sub} onChange={setSub} label="Acciones sobre la comisión" />
          {sub === "actual" && (
            <EstadoActual
              det={det.data}
              titulo="Resumen de la comisión"
              columnas={["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "nombre_comision", "turno", "sede", "modalidad", "horarios", "docentes_asignados_detalle"]}
              vacioHorarios="La comisión no tiene horarios cargados."
              vacioDocentes="No hay docentes registrados en esta comisión."
              tituloDocentes="Docentes actuales"
            />
          )}
          {sub === "alta" && <Alta key={`${cid}-${version}`} data={data} det={det.data} cid={cid} version={version} onDone={onDone} onError={onError} />}
          {sub === "baja" && <Baja key={`${cid}-${version}`} data={data} det={det.data} cid={cid} onDone={onDone} onError={onError} />}
          {sub === "hist" && (
            <div className="space-y-2">
              <Caption>Historial operativo de altas y bajas reales registradas para esta comisión.</Caption>
              <h5 className="text-sm font-semibold text-brand-950">Historial de modificación de asignaciones de esta comisión</h5>
              {(det.data.historial ?? []).length ? (
                <TablaLibre rows={det.data.historial ?? []} />
              ) : (
                <Aviso feedback={{ tone: "info", text: "Esta comisión todavía no tiene altas/bajas registradas desde esta pestaña." }} />
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// Selector de docente + cargo + horario efectivo (Alta real y Asignar por corrección).
export function SelectorDocente({
  docentes,
  contexto,
  det,
  puede,
  onError,
  render,
  filtroExtendido,
  catalogoRoles,
}: {
  docentes: DocenteDisponible[];
  contexto: "actual" | "correccion";
  det: Detalle;
  puede: boolean;
  onError: TabProps["onError"];
  render: (s: { cuil: string; rol: string; seleccion: ReturnType<typeof seleccionInicial>; horas: number; fila: DocenteDisponible }) => React.ReactNode;
  filtroExtendido?: boolean;
  catalogoRoles: string[];
}) {
  const [busq, setBusq] = useState("");
  const [cuilSel, setCuilSel] = useState<string | null>(null);
  const q = claveTexto(busq);
  const filtrados = docentes.filter((d) =>
    !q
      ? true
      : claveTexto(filtroExtendido ? `${d.nombre_completo ?? ""} ${d.cuil} ${d.departamento_origen ?? ""}` : d.etiqueta_cambio).includes(q)
  );
  const cuil = filtrados.some((d) => d.cuil === cuilSel) ? cuilSel : filtrados[0]?.cuil ?? null;
  const fila = filtrados.find((d) => d.cuil === cuil) ?? null;
  const roles = useConsulta<Roles>("docentes/roles", { contexto, cuil }, onError, 0, cuil !== null);
  const [rolSel, setRolSel] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState(() => seleccionInicial(det.franjas_alta));
  const listaRoles = roles.data?.roles ?? [];
  const opcionesRol = listaRoles.length > 1 ? listaRoles : catalogoRoles;
  const rol = listaRoles.length === 1 ? listaRoles[0] : rolSel && opcionesRol.includes(rolSel) ? rolSel : opcionesRol[0];
  const { horas } = horasSeleccion(det.franjas_alta, seleccion);
  return (
    <div className="space-y-3">
      <Field label={filtroExtendido ? "Buscar docente para asignar por nombre o CUIL" : "Buscar docente por nombre o CUIL"}>
        <TextInput value={busq} onChange={setBusq} />
      </Field>
      {filtrados.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: "No encontré docentes con esa búsqueda." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Docentes encontrados</p>
          <Tabla rows={filtrados} cols={[...COLS_DOCENTES]} rowKey={(r) => r.cuil} selected={cuil} onSelect={(k) => { setCuilSel(k); setRolSel(null); }} maxHeight="max-h-64" />
          {roles.data && listaRoles.length === 1 ? (
            <Aviso feedback={{ tone: "info", text: `Rol tomado automáticamente: ${listaRoles[0]}` }} />
          ) : (
            <div className="max-w-xs">
              <Field label="Rol">
                <Select value={rol} options={opcionesRol} onChange={setRolSel} disabled={!puede} />
              </Field>
            </div>
          )}
          <p className="text-sm font-semibold text-slate-700">Horario efectivo que cubrirá el docente</p>
          <FranjasForm franjas={det.franjas_alta} value={seleccion} onChange={setSeleccion} disabled={!puede} metrica="Horas que tomará en la comisión" />
          {fila && cuil && render({ cuil, rol, seleccion, horas, fila })}
        </>
      )}
    </div>
  );
}

function Alta({ data, det, cid, version, onDone, onError }: { data: TabProps["data"]; det: Detalle; cid: number; version: number; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const puede = data.permisos.puede_escribir;
  const docs = useConsulta<{ docentes: DocenteDisponible[] }>("docentes", { contexto: "actual" }, onError, version);
  const [fecha, setFecha] = useState(hoyIso());
  const [obs, setObs] = useState("");
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Caption>Registrá acá una incorporación real durante el dictado. Quedará en Movimientos y en el historial del docente.</Caption>
      <h5 className="text-sm font-semibold text-brand-950">Alta de docente en la comisión</h5>
      {!puede && <SoloLectura />}
      {docs.error && <FeedbackBox feedback={docs.error} />}
      {docs.loading && !docs.data && <Cargando />}
      {docs.data && docs.data.docentes.length === 0 && <Aviso feedback={{ tone: "warning", text: "No hay docentes disponibles para asignar." }} />}
      {docs.data && docs.data.docentes.length > 0 && (
        <SelectorDocente
          docentes={docs.data.docentes}
          contexto="actual"
          det={det}
          puede={puede}
          onError={onError}
          catalogoRoles={data.catalogos.roles}
          render={(s) => (
            <>
              <div className="max-w-xs">
                <Field label="Fecha efectiva del alta">
                  <DateInput value={fecha} onChange={setFecha} disabled={!puede} label="Fecha efectiva del alta" />
                </Field>
              </div>
              <Field label="Observaciones del alta">
                <Textarea value={obs} onChange={setObs} disabled={!puede} />
              </Field>
              {accion.feedback && <Aviso feedback={accion.feedback} />}
              {puede && (
                <PrimaryButton
                  busy={accion.busy}
                  onClick={() =>
                    accion.run(() =>
                      post<WriteResult>("modificacion/alta", {
                        comision_id: cid,
                        cuil: s.cuil,
                        rol: s.rol,
                        franjas: s.seleccion,
                        fecha,
                        observaciones: obs,
                        huella: det.huella,
                      })
                    )
                  }
                >
                  Registrar alta por modificación de asignación
                </PrimaryButton>
              )}
            </>
          )}
        />
      )}
    </div>
  );
}

function Baja({ data, det, cid, onDone, onError }: { data: TabProps["data"]; det: Detalle; cid: number; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const puede = data.permisos.puede_escribir;
  const activas = det.asignaciones.filter((a) => String(a.estado ?? "Activa").trim() === "Activa" || a.estado === null);
  const [sel, setSel] = useState<number | null>(null);
  const aid = activas.some((a) => a.id === sel) ? sel : activas[0]?.id ?? null;
  const [fecha, setFecha] = useState(hoyIso());
  const [obs, setObs] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Caption>Registrá acá una baja real de una asignación activa de esta comisión.</Caption>
      <h5 className="text-sm font-semibold text-brand-950">Baja de docente en la comisión</h5>
      {!puede && <SoloLectura />}
      {det.asignaciones.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "No hay docentes para dar de baja en esta comisión." }} />
      ) : activas.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "No hay asignaciones activas para dar de baja." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Asignaciones activas</p>
          <Tabla
            rows={activas}
            cols={[
              { key: "docente", label: "Docente" },
              { key: "cuil", label: "CUIL" },
              { key: "rol", label: "Rol" },
              { key: "horas_asignadas", label: "Hs." },
              { key: "estado", label: "Estado" },
              { key: "observaciones", label: "Observaciones" },
            ]}
            rowKey={(r) => String(r.id)}
            selected={aid === null ? null : String(aid)}
            onSelect={(k) => setSel(Number(k))}
            maxHeight="max-h-64"
          />
          <div className="max-w-xs">
            <Field label="Fecha efectiva de baja">
              <DateInput value={fecha} onChange={setFecha} disabled={!puede} label="Fecha efectiva de baja" />
            </Field>
          </div>
          <Field label="Observaciones de la baja">
            <Textarea value={obs} onChange={setObs} disabled={!puede} />
          </Field>
          <Check checked={confirmar} onChange={setConfirmar} disabled={!puede} label="Confirmo que es una baja real en la comisión y debe quedar en historial" />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {puede && (
            <PrimaryButton
              tone="secondary"
              busy={accion.busy}
              onClick={() =>
                accion.run(() =>
                  post<WriteResult>("modificacion/baja", {
                    comision_id: cid,
                    asignacion_id: aid,
                    fecha,
                    observaciones: obs,
                    confirmar,
                    huella: det.huella,
                  })
                )
              }
            >
              Registrar baja por modificación de asignación
            </PrimaryButton>
          )}
        </>
      )}
    </div>
  );
}
