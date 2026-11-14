"use client";

// Pestañas ✏️ Editar (entry l. 65993-66181) y ⏸️ Bajas, suspensión, archivo y eliminación (l. 66183-66410).
// Editar/suspender/archivar/eliminar un proyecto solo desde el departamento creador (o superadmin); la eliminación
// definitiva, solo superadmin. La edición de una asignación registra además su movimiento (operación propia); la baja,
// la suspensión y el archivo no registran movimientos (comportamiento certificado).
import { useState } from "react";
import { Card, Check, Field, PrimaryButton, Radio, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  Aviso,
  Caption,
  Cargando,
  DateInput,
  SeleccionTabla,
  SoloLectura,
  type Col,
  type TabProps,
  hoyIso,
  useAccion,
  useConsulta,
} from "@/components/extension-shared";
import { type Capacidad, type FilaHuella, type Periodo, type WriteResult, g, guardarAlerta, post } from "@/lib/extension";

const COLS_PROYECTO: Col<FilaHuella>[] = [
  { key: "codigo_proyecto", label: "Código" },
  { key: "nombre_proyecto", label: "Proyecto" },
  { key: "instituto_proyecto", label: "Instituto" },
  { key: "anio_llamado", label: "Año" },
  { key: "fecha_inicio", label: "Inicio" },
  { key: "fecha_fin", label: "Fin" },
  { key: "situacion", label: "Situación" },
  { key: "estado", label: "Estado" },
];
const BUSCAR_PROYECTO = ["codigo_proyecto", "nombre_proyecto", "instituto_proyecto", "anio_llamado", "situacion", "estado"];
const COLS_ASIG: Col<FilaHuella>[] = [
  { key: "docente", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "nombre_proyecto", label: "Proyecto" },
  { key: "codigo_proyecto", label: "Código" },
  { key: "rol", label: "Rol" },
  { key: "horas_asignadas", label: "Horas semanales" },
  { key: "departamento_origen_docente", label: "Departamento de origen" },
  { key: "periodo", label: "Período" },
];
const BUSCAR_ASIG = ["docente", "cuil", "nombre_proyecto", "codigo_proyecto", "rol", "departamento_origen_docente", "periodo"];

// --- ✏️ Editar ------------------------------------------------------------------------------------------------------
export function EditarTab(props: TabProps) {
  const [tipo, setTipo] = useState("Proyecto");
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Editar proyectos o asignaciones activas</h3>
      <Field label="Qué querés editar">
        <Radio name="ext_tipo_edicion" value={tipo} options={["Proyecto", "Asignación de un docente"]} onChange={setTipo} />
      </Field>
      {!props.data.permisos.puede_escribir && <SoloLectura />}
      {tipo === "Proyecto" ? <EditarProyecto {...props} /> : <EditarAsignacion {...props} />}
    </section>
  );
}

function EditarProyecto(props: TabProps) {
  const { data, version, onDone, onError } = props;
  const r = useConsulta<{ filas: FilaHuella[] }>("editar/proyectos", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data) return <Cargando />;
  if (!r.data.filas.length) {
    return (
      <Aviso
        feedback={{
          tone: "info",
          text: "No hay proyectos administrables desde este departamento. Podés asignar docentes a proyectos creados por otros departamentos, pero su edición corresponde al departamento creador o a la coordinación institucional.",
        }}
      />
    );
  }
  const fila = r.data.filas.find((f) => f.id === sel);
  return (
    <>
      <SeleccionTabla
        filas={r.data.filas}
        cols={COLS_PROYECTO}
        busquedaCols={BUSCAR_PROYECTO}
        etiquetaBuscar="Buscar proyecto a editar"
        placeholder="Código, nombre, instituto, año, situación..."
        titulo="Proyectos encontrados"
        value={sel}
        onChange={setSel}
      />
      {fila && <FormProyecto key={`${fila.id}-${fila.huella}`} fila={fila} data={data} version={version} onDone={onDone} onError={onError} />}
    </>
  );
}

function FormProyecto({ fila, ...props }: TabProps & { fila: FilaHuella }) {
  const { data, onDone, onError } = props;
  const s = (k: string) => String(fila[k] ?? "");
  const estados = ["Activo", "Finalizado", "Archivado"];
  if (s("estado") === "Suspendido") estados.splice(1, 0, "Suspendido");
  const [f, setF] = useState({
    nombre: s("nombre_proyecto"), codigo: s("codigo_proyecto"), instituto: s("instituto_proyecto"),
    anio_llamado: s("anio_llamado") || String(new Date().getFullYear()), fecha_inicio: s("fecha_inicio") || hoyIso(),
    fecha_fin: s("fecha_fin") || hoyIso(), estado: estados.includes(s("estado")) ? s("estado") : "Activo",
    observaciones: s("observaciones"),
  });
  const accion = useAccion(onDone, onError);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  return (
    <Card>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Nombre del proyecto"><TextInput value={f.nombre} onChange={set("nombre")} /></Field>
          <Field label="Código interno"><TextInput value={f.codigo} onChange={set("codigo")} /></Field>
          <Field label="Área/Secretaría/Instituto/Departamento de radicación (si corresponde)" hint={`ℹ️ ${data.ayuda_radicacion}`}>
            <TextInput value={f.instituto} onChange={set("instituto")} placeholder="Dejar vacío si radica en este departamento" />
          </Field>
          <Field label="Año de llamado"><TextInput type="number" value={f.anio_llamado} onChange={set("anio_llamado")} /></Field>
        </div>
        <div className="space-y-3">
          <Field label="Fecha de inicio"><TextInput type="date" value={f.fecha_inicio} onChange={set("fecha_inicio")} /></Field>
          <Field label="Fecha de finalización"><TextInput type="date" value={f.fecha_fin} onChange={set("fecha_fin")} /></Field>
          <Field label="Estado administrativo"><Select value={f.estado} options={estados} onChange={set("estado")} /></Field>
        </div>
      </div>
      <Field label="Observaciones del proyecto"><Textarea value={f.observaciones} onChange={set("observaciones")} /></Field>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      <PrimaryButton
        busy={accion.busy}
        disabled={!data.permisos.puede_escribir}
        onClick={() =>
          accion.run(() =>
            post<WriteResult>("editar/proyecto", { ...f, anio_llamado: Number(f.anio_llamado), proyecto_id: fila.id, huella: fila.huella })
          )
        }
      >
        💾 Guardar cambios del proyecto
      </PrimaryButton>
    </Card>
  );
}

type Opciones = { proyectos: { id: number; etiqueta: string }[]; docentes: { etiqueta: string; cuil: string; actual: boolean }[] };

function EditarAsignacion(props: TabProps) {
  const { data, version, onDone, onError } = props;
  const r = useConsulta<{ periodo: Periodo | null; filas: FilaHuella[] }>("editar/asignaciones", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data) return <Cargando />;
  if (!r.data.periodo) return <Aviso feedback={{ tone: "warning", text: "No hay período abierto. Solo se editan asignaciones activas del período abierto." }} />;
  if (!r.data.filas.length) return <Aviso feedback={{ tone: "info", text: "No hay asignaciones activas para editar." }} />;
  const fila = r.data.filas.find((f) => f.id === sel);
  return (
    <>
      <SeleccionTabla
        filas={r.data.filas}
        cols={COLS_ASIG}
        busquedaCols={BUSCAR_ASIG}
        etiquetaBuscar="Buscar asignación a editar"
        placeholder="Docente, CUIL, proyecto, código, rol..."
        titulo="Asignaciones encontradas"
        value={sel}
        onChange={setSel}
        vacio="No hay asignaciones que coincidan con la búsqueda."
      />
      {fila && <FormAsignacion key={`${fila.id}-${fila.huella}`} fila={fila} data={data} version={version} onDone={onDone} onError={onError} />}
    </>
  );
}

function FormAsignacion({ fila, ...props }: TabProps & { fila: FilaHuella }) {
  const { data, version, onDone, onError } = props;
  const op = useConsulta<Opciones>("editar/asignacion/opciones", { asignacion_id: fila.id }, onError, version);
  const [proyectoElegido, setProyecto] = useState<string | null>(null);
  const [docenteElegido, setDocente] = useState<string | null>(null);
  const [rol, setRol] = useState(String(fila.rol ?? ""));
  const [horas, setHoras] = useState(String(Number(fila.horas_asignadas ?? 0)));
  const [obs, setObs] = useState(String(fila.observaciones ?? ""));
  const accion = useAccion(onDone, onError);
  // Valores por defecto certificados: el proyecto actual (o el primero) y el docente actual de la asignación.
  const proyecto =
    proyectoElegido ??
    (op.data?.proyectos.find((p) => p.id === Number(fila.proyecto_id)) ?? op.data?.proyectos[0])?.etiqueta ??
    null;
  const docente = docenteElegido ?? op.data?.docentes.find((d) => d.actual)?.etiqueta ?? null;
  const cuil = op.data?.docentes.find((d) => d.etiqueta === docente)?.cuil ?? null;
  const cap = useConsulta<{ capacidades: Record<string, Capacidad> }>(
    "capacidad",
    { cuiles: cuil ? [cuil] : [], excluir_id: fila.id },
    onError,
    version,
    !!cuil
  );
  if (op.error) return <Aviso feedback={op.error} />;
  if (!op.data) return <Cargando />;
  if (!op.data.proyectos.length) return <Aviso feedback={{ tone: "warning", text: "No hay proyectos vigentes disponibles para esta asignación." }} />;
  const capacidad = cuil ? cap.data?.capacidades?.[cuil] : undefined;
  const h = Number(horas || 0);
  return (
    <Card>
      <Field label="Proyecto">
        <Select value={proyecto ?? ""} options={op.data.proyectos.map((p) => p.etiqueta)} onChange={setProyecto} />
      </Field>
      <Field label="Docente">
        <Select value={docente ?? ""} options={op.data.docentes.map((d) => d.etiqueta)} onChange={setDocente} />
      </Field>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Rol en el proyecto"><TextInput value={rol} onChange={setRol} /></Field>
        <Field label="Horas semanales asignadas">
          <TextInput type="number" value={horas} onChange={setHoras} />
        </Field>
      </div>
      {capacidad && <Caption>{capacidad.mensaje}</Caption>}
      {capacidad && h > capacidad.horas_disponibles_proyectos + 1e-9 && (
        <Aviso
          feedback={{
            tone: "warning",
            text: `⚠️ Con esta modificación se excedería la dedicación. Disponibles para esta asignación: ${g(capacidad.horas_disponibles_proyectos)} hs. Podés guardar igualmente; el exceso quedará señalado por el sistema.`,
          }}
        />
      )}
      <Field label="Observaciones de la asignación"><Textarea value={obs} onChange={setObs} /></Field>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      <PrimaryButton
        busy={accion.busy}
        disabled={!data.permisos.puede_escribir}
        onClick={() =>
          accion.run(
            () =>
              post<WriteResult>("editar/asignacion", {
                asignacion_id: fila.id,
                huella: fila.huella,
                proyecto_id: op.data!.proyectos.find((p) => p.etiqueta === proyecto)?.id ?? null,
                docente_etiqueta: docente,
                rol,
                horas: h,
                observaciones: obs,
              }),
            (res) => res.alerta_post_accion && guardarAlerta(res.alerta_post_accion)
          )
        }
      >
        💾 Guardar cambios de la asignación
      </PrimaryButton>
    </Card>
  );
}

// --- ⏸️ Bajas, suspensión, archivo y eliminación --------------------------------------------------------------------
const ACCIONES = ["Dar de baja una asignación", "Suspender un proyecto", "Archivar un proyecto", "Eliminar definitivamente un proyecto"];

export function BajasTab(props: TabProps) {
  const [accion, setAccion] = useState(ACCIONES[0]);
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Bajas, suspensión, archivo y eliminación definitiva</h3>
        <Caption>
          Dar de baja, suspender o archivar conserva el historial. La eliminación definitiva se usa únicamente para corregir un
          proyecto cargado por error y borra también todas sus asignaciones.
        </Caption>
      </div>
      <Field label="Acción">
        <Radio name="ext_tipo_baja" value={accion} options={ACCIONES} onChange={setAccion} />
      </Field>
      {!props.data.permisos.puede_escribir && <SoloLectura />}
      {accion === ACCIONES[0] && <BajaAsignacion {...props} />}
      {accion === ACCIONES[1] && <Suspender {...props} />}
      {accion === ACCIONES[2] && <Archivar {...props} />}
      {accion === ACCIONES[3] && <Eliminar {...props} />}
    </section>
  );
}

function BajaAsignacion({ data, version, onDone, onError }: TabProps) {
  const r = useConsulta<{ periodo: Periodo | null; filas: FilaHuella[] }>("editar/asignaciones", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  const [fecha, setFecha] = useState(hoyIso());
  const [motivo, setMotivo] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Aviso feedback={{ tone: "info", text: "La asignación dejará de estar activa, pero permanecerá visible en el historial." }} />
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : !r.data.periodo ? (
        <Aviso feedback={{ tone: "warning", text: "No hay período abierto." }} />
      ) : !r.data.filas.length ? (
        <Aviso feedback={{ tone: "info", text: "No hay asignaciones activas para dar de baja." }} />
      ) : (
        <Card>
          <SeleccionTabla
            filas={r.data.filas}
            cols={COLS_ASIG}
            busquedaCols={BUSCAR_ASIG}
            etiquetaBuscar="Buscar asignación"
            placeholder="Docente, CUIL, proyecto, código, rol..."
            titulo="Asignaciones encontradas"
            value={sel}
            onChange={setSel}
          />
          <Field label="Fecha efectiva de baja" hint="Indicá la fecha real en la que dejó de participar del proyecto, aunque la cargues otro día.">
            <DateInput value={fecha} onChange={setFecha} />
          </Field>
          <Field label="Motivo de la baja"><Textarea value={motivo} onChange={setMotivo} /></Field>
          <Check checked={confirmar} onChange={setConfirmar} label="Confirmo la baja de esta asignación" />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          <PrimaryButton
            busy={accion.busy}
            disabled={!data.permisos.puede_escribir}
            onClick={() =>
              accion.run(() =>
                post<WriteResult>("bajas/asignacion", {
                  asignacion_id: sel,
                  huella: r.data!.filas.find((f) => f.id === sel)?.huella ?? null,
                  fecha_baja: fecha,
                  motivo,
                  confirmar,
                })
              )
            }
          >
            📦 Dar de baja asignación
          </PrimaryButton>
        </Card>
      )}
    </div>
  );
}

function Suspender({ data, version, onDone, onError }: TabProps) {
  const r = useConsulta<{ periodo: Periodo | null; filas: FilaHuella[] }>("bajas/suspender/proyectos", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  const [fecha, setFecha] = useState(hoyIso());
  const [motivo, setMotivo] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Aviso
        feedback={{
          tone: "warning",
          text: "La suspensión afecta al período abierto de toda la institución. Las asignaciones activas de ese período se darán de baja y quedarán en el historial; los períodos anteriores no se modifican.",
        }}
      />
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : !r.data.periodo ? (
        <Aviso feedback={{ tone: "warning", text: "No hay período abierto para aplicar la suspensión." }} />
      ) : !r.data.filas.length ? (
        <Aviso feedback={{ tone: "info", text: "No hay proyectos activos y administrables para suspender en este período." }} />
      ) : (
        <Card>
          <SeleccionTabla
            filas={r.data.filas}
            cols={COLS_PROYECTO.slice(0, 7)}
            busquedaCols={BUSCAR_PROYECTO}
            etiquetaBuscar="Buscar proyecto a suspender"
            placeholder="Código, nombre, instituto, año..."
            titulo="Proyectos encontrados"
            value={sel}
            onChange={setSel}
          />
          <Field label="Fecha efectiva de suspensión" hint="Indicá la fecha real desde la que el proyecto quedó suspendido.">
            <DateInput value={fecha} onChange={setFecha} />
          </Field>
          <Field label="Motivo de la suspensión"><Textarea value={motivo} onChange={setMotivo} /></Field>
          <Check checked={confirmar} onChange={setConfirmar} label={`Confirmo la suspensión para el período ${r.data.periodo.nombre}`} />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          <PrimaryButton
            busy={accion.busy}
            disabled={!data.permisos.puede_escribir}
            onClick={() =>
              accion.run(() =>
                post<WriteResult>("bajas/suspender", {
                  proyecto_id: sel,
                  huella: r.data!.filas.find((f) => f.id === sel)?.huella ?? null,
                  huella_periodo: data.huella_periodo,
                  fecha_suspension: fecha,
                  motivo,
                  confirmar,
                })
              )
            }
          >
            ⏸️ Suspender proyecto
          </PrimaryButton>
        </Card>
      )}
    </div>
  );
}

function Archivar({ data, version, onDone, onError }: TabProps) {
  const r = useConsulta<{ filas: FilaHuella[] }>("bajas/archivar/proyectos", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Aviso feedback={{ tone: "info", text: "El proyecto dejará de estar vigente para toda la institución, pero conservará todas sus asignaciones e historial." }} />
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : !r.data.filas.length ? (
        <Aviso feedback={{ tone: "info", text: "No hay proyectos disponibles para archivar." }} />
      ) : (
        <Card>
          <SeleccionTabla
            filas={r.data.filas}
            cols={COLS_PROYECTO}
            busquedaCols={BUSCAR_PROYECTO}
            etiquetaBuscar="Buscar proyecto a archivar"
            placeholder="Código, nombre, instituto, año, estado..."
            titulo="Proyectos encontrados"
            value={sel}
            onChange={setSel}
          />
          <Field label="Motivo/observación del archivo"><Textarea value={motivo} onChange={setMotivo} /></Field>
          <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que quiero archivar el proyecto" />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          <PrimaryButton
            busy={accion.busy}
            disabled={!data.permisos.puede_escribir}
            onClick={() =>
              accion.run(() =>
                post<WriteResult>("bajas/archivar", {
                  proyecto_id: sel,
                  huella: r.data!.filas.find((f) => f.id === sel)?.huella ?? null,
                  motivo,
                  confirmar,
                })
              )
            }
          >
            📦 Archivar proyecto
          </PrimaryButton>
        </Card>
      )}
    </div>
  );
}

function Eliminar({ data, version, onDone, onError }: TabProps) {
  const r = useConsulta<{ filas: FilaHuella[] }>("editar/proyectos", {}, onError, version);
  const [sel, setSel] = useState<number | null>(null);
  const [texto, setTexto] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  const fila = r.data?.filas.find((f) => f.id === sel);
  const esperado = fila ? String(fila.codigo_proyecto || "").trim() || String(fila.nombre_proyecto || "").trim() : "";
  return (
    <div className="space-y-3">
      <Aviso
        feedback={{
          tone: "error",
          text: "Esta acción es irreversible. El proyecto desaparecerá de todos los departamentos, del catálogo y del historial, y se eliminarán todas sus asignaciones activas, dadas de baja y de períodos cerrados.",
        }}
      />
      {r.error && <Aviso feedback={r.error} />}
      {!r.data ? (
        <Cargando />
      ) : !r.data.filas.length ? (
        <Aviso feedback={{ tone: "info", text: "No hay proyectos que puedas eliminar desde este departamento. La eliminación corresponde al departamento creador o a la coordinación institucional." }} />
      ) : (
        <Card>
          <SeleccionTabla
            filas={r.data.filas}
            cols={[
              ...COLS_PROYECTO.filter((c) => !["fecha_inicio", "fecha_fin"].includes(c.key)),
              { key: "departamento_creador", label: "Departamento creador" },
              { key: "cantidad_asignaciones_registradas", label: "Asignaciones" },
              { key: "cantidad_docentes_historicos", label: "Docentes" },
            ]}
            busquedaCols={[...BUSCAR_PROYECTO, "departamento_creador"]}
            etiquetaBuscar="Buscar proyecto a eliminar definitivamente"
            placeholder="Código, nombre, instituto, año, estado..."
            titulo="Proyectos encontrados"
            value={sel}
            onChange={(v) => {
              setSel(v);
              setTexto("");
              setConfirmar(false);
            }}
            vacio="No hay proyectos que coincidan con la búsqueda."
          />
          {fila && (
            <>
              <p className="text-sm">
                Registros que también se borrarán: <b>{Math.trunc(Number(fila.cantidad_asignaciones_registradas ?? 0))} asignación/es</b>{" "}
                correspondiente/s a <b>{Math.trunc(Number(fila.cantidad_docentes_historicos ?? 0))} docente/s</b>.
              </p>
              <Caption>
                Para confirmar, escribí exactamente: <b>{esperado}</b>
              </Caption>
              <Field label="Código o nombre de confirmación"><TextInput value={texto} onChange={setTexto} /></Field>
              <Check checked={confirmar} onChange={setConfirmar} label="Entiendo que esta eliminación es definitiva y que no quedará en el historial" />
              {accion.feedback && <Aviso feedback={accion.feedback} />}
              {data.permisos.puede_borrar ? (
                <PrimaryButton
                  tone="danger"
                  busy={accion.busy}
                  onClick={() =>
                    accion.run(() =>
                      post<WriteResult>("bajas/eliminar", { proyecto_id: fila.id, huella: fila.huella, confirmacion: texto, confirmar })
                    )
                  }
                >
                  🗑️ Eliminar definitivamente
                </PrimaryButton>
              ) : (
                <Caption>La eliminación definitiva está reservada al rol superadmin.</Caption>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
