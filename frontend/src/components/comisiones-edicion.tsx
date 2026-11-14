"use client";

// Pestaña "✏️ Editar / eliminar" (entry l. 71273-72224): corrección de errores de carga en el período abierto habilitado
// para corrección. Subpestañas: Estado actual, Datos generales (+ número/letra en lote), Horarios (editar / agregar /
// eliminar), Docentes (asignar / horario efectivo / quitar) y Eliminar. Sin movimiento académico salvo horarios y
// quitar asignación, como el certificado.
import { useMemo, useState } from "react";
import { COLS_COMISIONES, EstadoActual, SelectorDocente } from "@/components/comisiones-modificacion";
import { MultiSelect } from "@/components/comisiones-abrir";
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
  TimeInput,
  seleccionInicial,
  useConsulta,
} from "@/components/comisiones-shared";
import { useAccion } from "@/components/designaciones-shared";
import { Check, Details, Field, FeedbackBox, PrimaryButton, Radio, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  type DatosEdicion,
  type Detalle,
  type DocenteDisponible,
  type Franja,
  type Lista,
  type WriteResult,
  g,
  horasHorario,
  post,
} from "@/lib/comisiones";

const SUBTABS = [
  { key: "actual", label: "📌 Estado actual" },
  { key: "datos", label: "📝 Datos generales" },
  { key: "horarios", label: "🕒 Horarios" },
  { key: "docentes", label: "👥 Docentes" },
  { key: "eliminar", label: "🗑️ Eliminar" },
] as const;

const SUBTABS_HORARIOS = [
  { key: "editar", label: "✏️ Editar horario" },
  { key: "agregar", label: "➕ Agregar horario" },
  { key: "eliminar", label: "🗑️ Eliminar horario" },
] as const;

const ACCIONES_DOCENTES = ["➕ Asignar docente", "🕒 Horario efectivo", "🗑️ Quitar asignación"];

type Props = { data: TabProps["data"]; det: Detalle; cid: number; version: number; onDone: TabProps["onDone"]; onError: TabProps["onError"] };

export function EdicionTab({ data, version, onDone, onError }: TabProps) {
  const [busqueda, setBusqueda] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [sub, setSub] = useState<string>("actual");
  const lista = useConsulta<Lista>("lista", { contexto: "edicion", busqueda }, onError, version);
  const filas = useMemo(() => lista.data?.filas ?? [], [lista.data]);
  const cid = filas.some((f) => f.id === sel) ? sel : filas[0]?.id ?? null;
  const det = useConsulta<Detalle>("detalle", { contexto: "edicion", comision_id: cid }, onError, version, cid !== null);

  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar comisión</h3>
      <Aviso
        feedback={{
          tone: "warning",
          text: "Esta pestaña es solo para corregir errores de carga. Los cambios hechos acá NO quedan como historial académico/operativo de la comisión. Para registrar altas o bajas reales de docentes durante el dictado, usá la pestaña Modificación de asignaciones.",
        }}
      />
      {!data.puede_corregir ? (
        <Aviso feedback={{ tone: "warning", text: "No hay un período abierto habilitado para corregir comisiones." }} />
      ) : (
        data.historico_abierto &&
        data.periodo_correccion && (
          <Aviso
            feedback={{
              tone: "info",
              text: `Modo corrección histórica: estás editando el período ${data.periodo_correccion.nombre}. Usá esta pestaña únicamente para corregir errores de carga; no representa un cambio académico real.`,
            }}
          />
        )
      )}
      {lista.error && <FeedbackBox feedback={lista.error} />}
      <Field label="Buscar comisión por código, materia o nombre">
        <TextInput value={busqueda} onChange={setBusqueda} />
      </Field>
      {lista.loading && !lista.data && <Cargando />}
      {lista.data?.aviso && (
        <Aviso feedback={{ tone: lista.data.aviso.startsWith("No hay comisiones") ? "info" : "warning", text: lista.data.aviso }} />
      )}
      {filas.length > 0 && (
        <>
          <p className="text-sm font-medium text-slate-700">Comisiones encontradas</p>
          <Tabla rows={filas} cols={[...COLS_COMISIONES]} rowKey={(r) => String(r.id)} selected={cid === null ? null : String(cid)} onSelect={(k) => setSel(Number(k))} maxHeight="max-h-72" />
          <Caption>{`${filas.length} fila/s`}</Caption>
        </>
      )}
      {det.error && <FeedbackBox feedback={det.error} />}
      {det.data && cid !== null && (
        <div className="space-y-3">
          <h4 className="text-base font-semibold text-brand-950">Comisión seleccionada · {det.data.etiqueta}</h4>
          <Caption>
            Revisá primero el estado actual de la comisión. Después entrá solamente en la sección que necesitás corregir. Esta
            pestaña continúa siendo exclusivamente para errores de carga, no para cambios académicos reales.
          </Caption>
          <Subtabs tabs={SUBTABS} value={sub} onChange={setSub} label="Secciones de corrección" />
          {sub === "actual" && (
            <EstadoActual
              det={det.data}
              titulo="Resumen actual"
              columnas={["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "nombre_comision", "turno", "sede", "modalidad", "estado", "horas_horario", "docentes_asignados", "observaciones"]}
              vacioHorarios="Esta comisión todavía no tiene horarios cargados."
              vacioDocentes="La comisión no tiene docentes asignados."
              tituloDocentes="Docentes y asignaciones actuales"
            />
          )}
          {sub === "datos" && (
            <>
              <NombresLote key={`lote-${version}-${busqueda}`} data={data} lista={lista.data} busqueda={busqueda} onDone={onDone} onError={onError} />
              <DatosGenerales key={`${cid}-${version}`} data={data} det={det.data} cid={cid} version={version} onDone={onDone} onError={onError} />
            </>
          )}
          {sub === "horarios" && <Horarios key={`${cid}-${version}`} data={data} det={det.data} cid={cid} version={version} onDone={onDone} onError={onError} />}
          {sub === "docentes" && <Docentes key={`${cid}-${version}`} data={data} det={det.data} cid={cid} version={version} onDone={onDone} onError={onError} />}
          {sub === "eliminar" && <EliminarComision key={`${cid}-${version}`} data={data} det={det.data} cid={cid} version={version} onDone={onDone} onError={onError} />}
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------------------------------ número/letra en lote (v180/v195)
function NombresLote({ data, lista, busqueda, onDone, onError }: { data: TabProps["data"]; lista: Lista | null; busqueda: string; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const puede = data.permisos.puede_escribir;
  const filas = lista?.filas ?? [];
  const [valores, setValores] = useState<Record<number, string>>(() => Object.fromEntries(filas.map((f) => [f.id, String(f.nombre_comision ?? "")])));
  const accion = useAccion(onDone, onError);
  return (
    <Details summary="✏️ Corregir número/letra de Comisión en lote">
      <Caption>
        Usá esta tabla únicamente para corregir el número/letra de una o varias comisiones. La comisión cuyo detalle se edita
        se selecciona en la tabla superior.
      </Caption>
      <Tabla
        rows={filas}
        cols={[...COLS_COMISIONES]}
        rowKey={(r) => String(r.id)}
        maxHeight="max-h-80"
        render={(r, key) =>
          key === "nombre_comision" ? (
            <input
              aria-label={`Comisión ${r.id}`}
              className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-50"
              value={valores[r.id] ?? ""}
              disabled={!puede}
              onChange={(e) => setValores((m) => ({ ...m, [r.id]: e.target.value }))}
            />
          ) : undefined
        }
      />
      <Caption>
        Podés modificar todas las filas que necesites. Los cambios quedan pendientes en este formulario y la app procesa la tabla
        una sola vez al guardar.
      </Caption>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() =>
            accion.run(() =>
              post<WriteResult>("edicion/nombres", {
                busqueda,
                filas: filas.map((f) => ({ id: f.id, comision: valores[f.id] ?? "" })),
                huella_lote: lista?.huella_lote ?? null,
              })
            )
          }
        >
          💾 Guardar todos los cambios de Comisión
        </PrimaryButton>
      )}
    </Details>
  );
}

// ------------------------------------------------------------------------------------------ datos generales
function DatosGenerales({ data, det, cid, version, onDone, onError }: Props) {
  const puede = data.permisos.puede_escribir;
  const [materiaId, setMateriaId] = useState<number | null>(null);
  const q = useConsulta<DatosEdicion>("edicion/datos", { comision_id: cid, materia_id: materiaId }, onError, version);
  return (
    <div className="space-y-3">
      <Caption>Corregí acá materia, comisión, turno, sede, modalidad, opción curricular y observaciones.</Caption>
      <h5 className="text-sm font-semibold text-brand-950">Datos generales de la comisión</h5>
      {!puede && <SoloLectura />}
      {q.error && <FeedbackBox feedback={q.error} />}
      {q.loading && !q.data && <Cargando />}
      {q.data && (
        <>
          <Field label="Materia" hint="Cambiar la materia puede recargar esta sección porque redefine las opciones disponibles. El resto se guarda en bloque.">
            <Select
              value={String(q.data.materia_id)}
              options={q.data.materias.map((m) => String(m.materia_id))}
              label={(v) => q.data?.materias.find((m) => String(m.materia_id) === v)?.etiqueta ?? v}
              onChange={(v) => setMateriaId(Number(v))}
              disabled={!puede}
            />
          </Field>
          <FormularioDatos key={q.data.materia_id} d={q.data} det={det} cid={cid} puede={puede} onDone={onDone} onError={onError} />
        </>
      )}
    </div>
  );
}

function FormularioDatos({ d, det, cid, puede, onDone, onError }: { d: DatosEdicion; det: Detalle; cid: number; puede: boolean; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const [nombre, setNombre] = useState(String(d.valores.nombre ?? ""));
  const [turno, setTurno] = useState(d.valores.turno);
  const [sede, setSede] = useState(d.valores.sede);
  const [modalidad, setModalidad] = useState(d.valores.modalidad);
  const [adicionales, setAdicionales] = useState<number[]>(d.adicionales_default);
  const [opcion, setOpcion] = useState(d.opciones_curriculares[d.indice_opcion] ?? d.placeholder);
  const [obs, setObs] = useState(String(d.valores.observaciones ?? ""));
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      {d.avisos.map((a) => (
        <Aviso key={a} feedback={{ tone: "warning", text: a }} />
      ))}
      {d.es_oe && (
        <Caption>Cada comisión Optativa/Electiva mantiene una única opción curricular concreta y un único código/espacio formal.</Caption>
      )}
      {d.es_oe && d.sin_opciones && (
        <Aviso feedback={{ tone: "info", text: "No hay opciones curriculares activas habilitadas para el espacio seleccionado." }} />
      )}
      <Caption>
        Los cambios de este formulario se aplican juntos al presionar Guardar cambios generales. Así, seleccionar una opción
        curricular no recarga toda la app en cada movimiento.
      </Caption>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Comisión">
          <TextInput value={nombre} onChange={setNombre} disabled={!puede} />
        </Field>
        <Field label="Turno">
          <Select value={turno} options={["mañana", "tarde", "noche"]} onChange={setTurno} disabled={!puede} />
        </Field>
        <Field label="Modalidad">
          <Select value={modalidad} options={["Presencial", "Virtual", "Híbrida"]} onChange={setModalidad} disabled={!puede} />
        </Field>
        <Field label="Sede">
          <Select value={sede} options={d.opciones_sede} onChange={setSede} disabled={!puede} />
        </Field>
        <div className="self-end sm:col-span-2">
          <Aviso feedback={{ tone: "info", text: "El estado no se edita desde este apartado." }} />
        </div>
      </div>
      {!d.es_oe ? (
        <Field label="Otros códigos/materias de esta misma comisión" hint="Una comisión puede representar simultáneamente varios códigos de materias comunes.">
          <MultiSelect opciones={d.adicionales.map((a) => ({ value: a.materia_id, label: a.etiqueta }))} value={adicionales} onChange={setAdicionales} disabled={!puede} />
        </Field>
      ) : (
        d.opciones_curriculares.length > 0 && (
          <Field label="Opción curricular concreta" hint="Permite asignar, corregir o completar la opción concreta dictada en esta comisión.">
            <Select value={opcion} options={d.opciones_curriculares} onChange={setOpcion} disabled={!puede} />
          </Field>
        )
      )}
      <Field label="Observaciones">
        <Textarea value={obs} onChange={setObs} disabled={!puede} />
      </Field>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() =>
            accion.run(() =>
              post<WriteResult>("edicion/guardar-datos", {
                comision_id: cid,
                materia_id: d.materia_id,
                nombre,
                turno,
                sede,
                modalidad,
                adicionales: d.es_oe ? [] : adicionales,
                opcion_curricular: d.es_oe ? opcion : null,
                observaciones: obs,
                huella: det.huella,
              })
            )
          }
        >
          ✏️ Guardar cambios generales
        </PrimaryButton>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------ horarios
function Horarios({ data, det, cid, onDone, onError }: Props) {
  const [sub, setSub] = useState<string>("editar");
  const total = det.horarios.reduce((acc, h) => acc + (Number(h.horas) || 0), 0);
  return (
    <div className="space-y-3">
      <Caption>Administrá únicamente los horarios generales de la comisión. Las horas docentes se recalculan automáticamente.</Caption>
      <h5 className="text-sm font-semibold text-brand-950">Horarios de la comisión</h5>
      <Caption>
        La comisión ya está seleccionada. Desde acá podés editar, agregar o eliminar sus horarios. Las horas de las asignaciones
        docentes se recalculan automáticamente.
      </Caption>
      {det.horarios.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Esta comisión todavía no tiene horarios cargados." }} />
      ) : (
        <>
          <TablaLibre rows={det.horarios} ocultar={["id", "comision_id", "etiqueta", "etiqueta_eliminar"]} />
          <div className="max-w-xs">
            <Metric label="Horas semanales actuales" value={`${g(total)} hs`} />
          </div>
        </>
      )}
      <Subtabs tabs={SUBTABS_HORARIOS} value={sub} onChange={setSub} label="Acciones sobre horarios" />
      {sub === "editar" && <EditarHorario data={data} det={det} cid={cid} onDone={onDone} onError={onError} />}
      {sub === "agregar" && <AgregarHorario data={data} det={det} cid={cid} onDone={onDone} onError={onError} />}
      {sub === "eliminar" && <EliminarHorario data={data} det={det} cid={cid} onDone={onDone} onError={onError} />}
    </div>
  );
}

type HProps = Omit<Props, "version">;

const hhmm = (v: unknown, fallback: string) => {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(v ?? "").slice(0, 5));
  return m && Number(m[1]) < 24 && Number(m[2]) < 60 ? `${m[1].padStart(2, "0")}:${m[2]}` : fallback;
};

function EditarHorario({ data, det, cid, onDone, onError }: HProps) {
  const puede = data.permisos.puede_escribir;
  const [hid, setHid] = useState<number | null>(det.horarios[0]?.id ?? null);
  const h = det.horarios.find((x) => x.id === hid) ?? det.horarios[0];
  if (!h) return <Aviso feedback={{ tone: "info", text: "No hay horarios para editar." }} />;
  return <EditarHorarioForm key={h.id} data={data} det={det} cid={cid} h={h} setHid={setHid} puede={puede} onDone={onDone} onError={onError} />;
}

function EditarHorarioForm({ data, det, cid, h, setHid, puede, onDone, onError }: HProps & { h: Detalle["horarios"][number]; setHid: (n: number) => void; puede: boolean }) {
  const dias = data.catalogos.dias;
  const [dia, setDia] = useState(dias.includes(String(h.dia ?? "Lunes")) ? String(h.dia ?? "Lunes") : dias[0]);
  const [ini, setIni] = useState(hhmm(h.hora_inicio || "08:00", "08:00"));
  const [fin, setFin] = useState(hhmm(h.hora_fin || "12:00", "12:00"));
  const [obs, setObs] = useState(String(h.observaciones ?? ""));
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <div className="max-w-sm">
        <Field label="Horario a editar">
          <Select value={String(h.id)} options={det.horarios.map((x) => String(x.id))} label={(v) => det.horarios.find((x) => String(x.id) === v)?.etiqueta ?? v} onChange={(v) => setHid(Number(v))} />
        </Field>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Día">
          <Select value={dia} options={dias} onChange={setDia} disabled={!puede} />
        </Field>
        <Field label="Hora de inicio">
          <TimeInput label="Hora de inicio" value={ini} onChange={setIni} disabled={!puede} />
        </Field>
        <Field label="Hora de finalización">
          <TimeInput label="Hora de finalización" value={fin} onChange={setFin} disabled={!puede} />
        </Field>
      </div>
      <Field label="Observaciones del horario">
        <Textarea value={obs} onChange={setObs} disabled={!puede} />
      </Field>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          tone="secondary"
          busy={accion.busy}
          onClick={() =>
            accion.run(() =>
              post<WriteResult>("edicion/horario/editar", { comision_id: cid, horario_id: h.id, dia, hora_inicio: ini, hora_fin: fin, observaciones: obs, huella: det.huella })
            )
          }
        >
          ✏️ Guardar cambios del horario
        </PrimaryButton>
      )}
    </div>
  );
}

function AgregarHorario({ data, det, cid, onDone, onError }: HProps) {
  const puede = data.permisos.puede_escribir;
  const [dia, setDia] = useState(data.catalogos.dias[0]);
  const [ini, setIni] = useState("08:00");
  const [fin, setFin] = useState("12:00");
  const [obs, setObs] = useState("");
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Día">
          <Select value={dia} options={data.catalogos.dias} onChange={setDia} disabled={!puede} />
        </Field>
        <Field label="Hora de inicio">
          <TimeInput label="Hora de inicio" value={ini} onChange={setIni} disabled={!puede} />
        </Field>
        <Field label="Hora de finalización">
          <TimeInput label="Hora de finalización" value={fin} onChange={setFin} disabled={!puede} />
        </Field>
      </div>
      <Field label="Observaciones del nuevo horario">
        <Textarea value={obs} onChange={setObs} disabled={!puede} />
      </Field>
      <Aviso feedback={{ tone: "info", text: `Duración calculada: ${g(horasHorario(ini, fin))} hs` }} />
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() =>
            accion.run(() =>
              post<WriteResult>("edicion/horario/agregar", { comision_id: cid, dia, hora_inicio: ini, hora_fin: fin, observaciones: obs, huella: det.huella })
            )
          }
        >
          ➕ Agregar horario
        </PrimaryButton>
      )}
    </div>
  );
}

function EliminarHorario({ data, det, cid, onDone, onError }: HProps) {
  const puede = data.permisos.puede_borrar;
  const [hid, setHid] = useState<number | null>(det.horarios[0]?.id ?? null);
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  if (!det.horarios.length) return <Aviso feedback={{ tone: "info", text: "No hay horarios para eliminar." }} />;
  const h = det.horarios.find((x) => x.id === hid) ?? det.horarios[0];
  return (
    <div className="space-y-3">
      <div className="max-w-sm">
        <Field label="Horario a eliminar">
          <Select value={String(h.id)} options={det.horarios.map((x) => String(x.id))} label={(v) => det.horarios.find((x) => String(x.id) === v)?.etiqueta_eliminar ?? v} onChange={(v) => setHid(Number(v))} />
        </Field>
      </div>
      <Check checked={confirmar} onChange={setConfirmar} disabled={!puede} label="Confirmo que quiero eliminar este horario" />
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede ? (
        <PrimaryButton
          tone="danger"
          busy={accion.busy}
          onClick={() => accion.run(() => post<WriteResult>("edicion/horario/eliminar", { comision_id: cid, horario_id: h.id, confirmar, huella: det.huella }))}
        >
          🗑️ Eliminar horario
        </PrimaryButton>
      ) : (
        <Caption>Tu rol no puede eliminar horarios.</Caption>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------ docentes
function Docentes({ data, det, cid, version, onDone, onError }: Props) {
  const [accionDoc, setAccionDoc] = useState(ACCIONES_DOCENTES[0]);
  return (
    <div className="space-y-3">
      <Caption>
        Elegí una sola acción sobre docentes. Estas operaciones son correcciones de carga y no representan altas/bajas reales
        durante el dictado.
      </Caption>
      <Field label="¿Qué querés corregir?">
        <Radio name={`accion-docentes-${cid}`} value={accionDoc} options={ACCIONES_DOCENTES} onChange={setAccionDoc} />
      </Field>
      {accionDoc === ACCIONES_DOCENTES[0] && <AsignarCorreccion data={data} det={det} cid={cid} version={version} onDone={onDone} onError={onError} />}
      {accionDoc === ACCIONES_DOCENTES[1] && <HorarioEfectivo data={data} det={det} cid={cid} version={version} onDone={onDone} onError={onError} />}
      {accionDoc === ACCIONES_DOCENTES[2] && <QuitarAsignacion data={data} det={det} cid={cid} version={version} onDone={onDone} onError={onError} />}
    </div>
  );
}

function AsignarCorreccion({ data, det, cid, version, onDone, onError }: Props) {
  const puede = data.permisos.puede_escribir;
  const docs = useConsulta<{ docentes: DocenteDisponible[] }>("docentes", { contexto: "correccion" }, onError, version);
  const [obs, setObs] = useState("");
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <h5 className="text-sm font-semibold text-brand-950">Asignar docente a la comisión</h5>
      <Caption>
        Esta alta pertenece a la pestaña de corrección por error de carga y no genera un movimiento académico. Si el docente se
        incorpora realmente durante el dictado, usá Modificación de asignaciones.
      </Caption>
      {!puede && <SoloLectura />}
      {docs.error && <FeedbackBox feedback={docs.error} />}
      {docs.loading && !docs.data && <Cargando />}
      {docs.data && docs.data.docentes.length === 0 && <Aviso feedback={{ tone: "info", text: "No hay docentes disponibles para asignar en este período." }} />}
      {docs.data && docs.data.docentes.length > 0 && (
        <SelectorDocente
          docentes={docs.data.docentes}
          contexto="correccion"
          det={det}
          puede={puede}
          onError={onError}
          catalogoRoles={data.catalogos.roles}
          filtroExtendido
          render={(s) => (
            <>
              <Field label="Observaciones de la asignación por corrección">
                <Textarea value={obs} onChange={setObs} disabled={!puede} />
              </Field>
              {accion.feedback && <Aviso feedback={accion.feedback} />}
              {puede && (
                <PrimaryButton
                  busy={accion.busy}
                  onClick={() =>
                    accion.run(() =>
                      post<WriteResult>("edicion/docente/asignar", { comision_id: cid, cuil: s.cuil, rol: s.rol, franjas: s.seleccion, observaciones: obs, huella: det.huella })
                    )
                  }
                >
                  ➕ Asignar docente por corrección de carga
                </PrimaryButton>
              )}
            </>
          )}
        />
      )}
    </div>
  );
}

function HorarioEfectivo({ data, det, cid, version, onDone, onError }: Props) {
  const puede = data.permisos.puede_escribir;
  const activas = det.asignaciones.filter((a) => String(a.estado ?? "Activa").trim() === "Activa");
  const [sel, setSel] = useState<number | null>(null);
  const aid = activas.some((a) => a.id === sel) ? sel : activas[0]?.id ?? null;
  const fr = useConsulta<{ franjas: Franja[] }>("asignacion/franjas", { comision_id: cid, asignacion_id: aid }, onError, version, aid !== null);
  return (
    <div className="space-y-3">
      <h5 className="text-sm font-semibold text-brand-950">Horario efectivo de cada docente</h5>
      <Caption>
        Podés ajustar qué franjas de la comisión cubre cada docente. Las asignaciones históricas anteriores a esta función se
        interpretan como cobertura de todo el horario hasta que las edites.
      </Caption>
      {det.asignaciones.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "La comisión no tiene docentes asignados para editar horarios." }} />
      ) : (
        activas.length > 0 && (
          <>
            <p className="text-sm font-medium text-slate-700">Asignaciones de la comisión</p>
            <Tabla
              rows={activas}
              cols={[
                { key: "docente", label: "Docente" },
                { key: "cuil", label: "CUIL" },
                { key: "rol", label: "Rol" },
                { key: "horas_asignadas", label: "Hs." },
                { key: "estado", label: "Estado" },
              ]}
              rowKey={(r) => String(r.id)}
              selected={aid === null ? null : String(aid)}
              onSelect={(k) => setSel(Number(k))}
              maxHeight="max-h-64"
            />
            {fr.error && <FeedbackBox feedback={fr.error} />}
            {fr.data && aid !== null && (
              <FranjasEfectivas key={`${aid}-${version}`} franjas={fr.data.franjas} puede={puede} cid={cid} aid={aid} huella={det.huella} onDone={onDone} onError={onError} />
            )}
          </>
        )
      )}
    </div>
  );
}

function FranjasEfectivas({ franjas, puede, cid, aid, huella, onDone, onError }: { franjas: Franja[]; puede: boolean; cid: number; aid: number; huella: string; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const [seleccion, setSeleccion] = useState(() => seleccionInicial(franjas));
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <FranjasForm franjas={franjas} value={seleccion} onChange={setSeleccion} disabled={!puede} metrica="Horas semanales efectivas" />
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() => accion.run(() => post<WriteResult>("edicion/docente/franjas", { comision_id: cid, asignacion_id: aid, franjas: seleccion, huella }))}
        >
          💾 Guardar horario efectivo del docente
        </PrimaryButton>
      )}
    </div>
  );
}

function QuitarAsignacion({ data, det, cid, onDone, onError }: Props) {
  const puede = data.permisos.puede_borrar;
  const [sel, setSel] = useState<number | null>(null);
  const aid = det.asignaciones.some((a) => a.id === sel) ? sel : det.asignaciones[0]?.id ?? null;
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <h5 className="text-sm font-semibold text-brand-950">Quitar asignación docente cargada por error</h5>
      <Caption>
        Usá esta sección solamente para corregir una asignación cargada por error. Para una baja real durante el período, usá
        Modificación de asignaciones.
      </Caption>
      {det.asignaciones.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "La comisión no tiene docentes asignados." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Asignaciones de la comisión</p>
          <Tabla
            rows={det.asignaciones}
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
          <Check checked={confirmar} onChange={setConfirmar} disabled={!puede} label="Confirmo que quiero eliminar esta asignación" />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {puede ? (
            <PrimaryButton
              tone="danger"
              busy={accion.busy}
              onClick={() => accion.run(() => post<WriteResult>("edicion/docente/quitar", { comision_id: cid, asignacion_id: aid, confirmar, huella: det.huella }))}
            >
              🗑️ Eliminar asignación
            </PrimaryButton>
          ) : (
            <Caption>Tu rol no puede eliminar asignaciones.</Caption>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------ eliminar comisión
function EliminarComision({ data, det, cid, onDone, onError }: Props) {
  const puede = data.permisos.puede_borrar;
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <Caption>Zona de eliminación. Usala solamente cuando la comisión completa fue cargada por error.</Caption>
      <h5 className="text-sm font-semibold text-brand-950">Eliminar comisión completa</h5>
      <Aviso feedback={{ tone: "error", text: "Esta acción elimina la comisión junto con todos sus horarios y asignaciones docentes." }} />
      <Check checked={confirmar} onChange={setConfirmar} disabled={!puede} label="Confirmo que quiero eliminar esta comisión y sus horarios/asignaciones" />
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede ? (
        <PrimaryButton tone="danger" busy={accion.busy} onClick={() => accion.run(() => post<WriteResult>("edicion/eliminar", { comision_id: cid, confirmar, huella: det.huella }))}>
          🗑️ Eliminar comisión completa
        </PrimaryButton>
      ) : (
        <Caption>Tu rol no puede eliminar comisiones.</Caption>
      )}
    </div>
  );
}
