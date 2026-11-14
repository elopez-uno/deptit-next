"use client";

// Pestaña "➕ Abrir comisión" (entry l. 70154-70643): comisión + 1 a 7 horarios + docentes con su horario efectivo, en un
// solo clic. El backend repite todas las validaciones certificadas y ejecuta los writers en el orden del certificado.
import { useMemo, useState } from "react";
import {
  Aviso,
  Caption,
  Cargando,
  FranjasForm,
  Metric,
  SoloLectura,
  Tabla,
  TablaLibre,
  type TabProps,
  TimeInput,
  useConsulta,
} from "@/components/comisiones-shared";
import { DateInput, hoyIso, useAccion } from "@/components/designaciones-shared";
import { Card, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea } from "@/components/module-ui";
import {
  type DocenteDisponible,
  type Franja,
  type MateriaAlta,
  type MateriasAlta,
  type Roles,
  type Seleccion,
  type WriteResult,
  g,
  horasHorario,
  post,
} from "@/lib/comisiones";

type Horario = { dia: string; hora_inicio: string; hora_fin: string };
type DocenteCfg = { cuil: string; rol: string; seleccion: Seleccion[] };

const HORARIO_INICIAL: Horario = { dia: "Lunes", hora_inicio: "08:00", hora_fin: "12:00" };

// Casillas iniciales del formulario de horario efectivo para los horarios todavía no guardados (default_full=True).
function franjasNuevas(horarios: Horario[]): Franja[] {
  return horarios.map((h, i) => ({
    indice: i,
    dia: h.dia,
    hora_inicio: h.hora_inicio,
    hora_fin: h.hora_fin,
    etiqueta: `${h.dia} ${h.hora_inicio}–${h.hora_fin}`,
    horario_comision_id: null,
    usar: true,
    desde: h.hora_inicio,
    hasta: h.hora_fin,
  }));
}

export function AbrirTab({ data, version, onDone, onError }: TabProps) {
  if (!data.puede_operar) return <Aviso feedback={{ tone: "warning", text: "Solo podés abrir comisiones en el período actual abierto." }} />;
  if (!data.actual) return <Aviso feedback={{ tone: "warning", text: "No hay un período actual abierto para registrar la comisión." }} />;
  return <AbrirForm data={data} version={version} onDone={onDone} onError={onError} />;
}

function AbrirForm({ data, version, onDone, onError }: TabProps) {
  const puede = data.permisos.puede_escribir;
  const [filtros, setFiltros] = useState({ codigo: "", nombre: "", cuatrimestre: "Todos", escuela: "Todas", carrera: "Todas" });
  const mats = useConsulta<MateriasAlta>("abrir/materias", filtros, onError, version);
  const [materiaSel, setMateriaSel] = useState<number | null>(null);
  const materiaId = useMemo(() => {
    const filas = mats.data?.materias ?? [];
    if (!filas.length) return null;
    return filas.some((f) => f.materia_id === materiaSel) ? materiaSel : filas[0].materia_id;
  }, [mats.data, materiaSel]);
  const [adicionales, setAdicionales] = useState<number[]>([]);
  const [buscarOpcion, setBuscarOpcion] = useState("");
  const [opcionId, setOpcionId] = useState<number | null>(null);
  const info = useConsulta<MateriaAlta>(
    "abrir/materia",
    { materia_id: materiaId, adicionales, buscar_opcion: buscarOpcion, opcion_curricular_id: opcionId },
    onError,
    version,
    materiaId !== null
  );

  const [nombre, setNombre] = useState("");
  const [turno, setTurno] = useState(data.catalogos.turnos[0]);
  const [sede, setSede] = useState(data.catalogos.sedes[0]);
  const [modalidad, setModalidad] = useState(data.catalogos.modalidades[0]);
  const [fecha, setFecha] = useState(hoyIso());
  const [obs, setObs] = useState("");
  const [horarios, setHorarios] = useState<Horario[]>([HORARIO_INICIAL]);
  const [obsAsig, setObsAsig] = useState("");
  const docs = useConsulta<{ docentes: DocenteDisponible[] }>("docentes", { contexto: "actual" }, onError, version);
  const [docentes, setDocentes] = useState<DocenteCfg[]>([]);
  const [roles, setRoles] = useState<Record<string, Roles>>({});
  const accion = useAccion(onDone, onError);

  const franjas = useMemo(() => franjasNuevas(horarios), [horarios]);
  // Cambiar los horarios recrea el formulario de cada docente (como las claves de widget certificadas).
  function cambiarHorarios(fn: (hs: Horario[]) => Horario[]) {
    const nuevos = fn(horarios);
    const fr = franjasNuevas(nuevos);
    setHorarios(nuevos);
    setDocentes((ds) => ds.map((d) => ({ ...d, seleccion: fr.map((f) => ({ usar: f.usar, desde: f.desde, hasta: f.hasta })) })));
  }

  function cambiarMateria(id: number) {
    setMateriaSel(id);
    setAdicionales([]);
    setOpcionId(null);
    setBuscarOpcion("");
  }

  async function alternarDocente(cuil: string, activo: boolean) {
    if (!activo) {
      setDocentes((ds) => ds.filter((d) => d.cuil !== cuil));
      return;
    }
    let r = roles[cuil];
    if (!r) {
      try {
        r = await post<Roles>("docentes/roles", { contexto: "actual", cuil });
        setRoles((m) => ({ ...m, [cuil]: r }));
      } catch (e) {
        accion.setFeedback({ tone: "error", text: onError(e).message });
        return;
      }
    }
    const rol = r.roles.length ? r.roles[0] : data.catalogos.roles[0];
    setDocentes((ds) => [...ds, { cuil, rol, seleccion: franjas.map((f) => ({ usar: f.usar, desde: f.desde, hasta: f.hasta })) }]);
  }

  const horasTotales = horarios.reduce((acc, h) => acc + horasHorario(h.hora_inicio, h.hora_fin), 0);
  const listaDocentes = docs.data?.docentes ?? [];
  const m = info.data;

  async function abrir() {
    if (materiaId === null) return;
    await accion.run(
      () =>
        post<WriteResult>("abrir", {
          materia_id: materiaId,
          adicionales,
          opcion_curricular_id: m?.es_oe ? opcionId : null,
          nombre,
          turno,
          sede,
          modalidad,
          fecha_apertura: fecha,
          observaciones: obs,
          observaciones_asignaciones: obsAsig,
          horarios,
          docentes: docentes.map((d) => ({ cuil: d.cuil, rol: d.rol, franjas: d.seleccion })),
          huella_periodos: data.huella_periodos,
        }),
      () => {
        setNombre("");
        setObs("");
        setObsAsig("");
        setDocentes([]);
      }
    );
  }

  return (
    <section className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Abrir comisión completa</h3>
        <Caption>
          La comisión se registra en una sola operación: datos generales, días y horarios, y docentes asignados. No hace falta
          volver a seleccionar la comisión en pasos separados.
        </Caption>
      </div>
      {!puede && <SoloLectura />}
      {mats.error && <FeedbackBox feedback={mats.error} />}

      <Card>
        <h4 className="text-base font-semibold text-brand-950">1. Materia y datos generales</h4>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Código o parte del código">
            <TextInput value={filtros.codigo} placeholder="Ej.: 07-03" onChange={(v) => setFiltros({ ...filtros, codigo: v })} />
          </Field>
          <Field label="Nombre o parte del nombre">
            <TextInput value={filtros.nombre} placeholder="Ej.: algoritmos" onChange={(v) => setFiltros({ ...filtros, nombre: v })} />
          </Field>
          <Field label="Cuatrimestre">
            <Select value={filtros.cuatrimestre} options={mats.data?.cuatrimestres ?? ["Todos"]} onChange={(v) => setFiltros({ ...filtros, cuatrimestre: v })} />
          </Field>
          <Field label="Unidad académica">
            <Select value={filtros.escuela} options={mats.data?.escuelas ?? ["Todas"]} onChange={(v) => setFiltros({ ...filtros, escuela: v, carrera: "Todas" })} />
          </Field>
          <Field label="Carrera">
            <Select value={filtros.carrera} options={mats.data?.carreras ?? ["Todas"]} onChange={(v) => setFiltros({ ...filtros, carrera: v })} />
          </Field>
        </div>
        {mats.loading && !mats.data && <Cargando />}
        {mats.data && (
          <>
            <Caption>{mats.data.caption}</Caption>
            {mats.data.materias.length === 0 ? (
              <Aviso feedback={{ tone: "warning", text: "No hay materias que coincidan con esos filtros." }} />
            ) : (
              <>
                <p className="text-sm font-medium text-slate-700">Materias encontradas</p>
                <Tabla
                  rows={mats.data.materias}
                  cols={[
                    { key: "codigo", label: "Código" },
                    { key: "asignatura", label: "Asignatura" },
                    { key: "carrera", label: "Carrera/s" },
                    { key: "escuela", label: "Unidad académica" },
                    { key: "plan_version", label: "Plan/es" },
                    { key: "anio", label: "Año" },
                    { key: "cuatrimestre", label: "Cuatrimestre" },
                    { key: "carga_semanal", label: "Hs. sem." },
                  ]}
                  rowKey={(r) => String(r.materia_id)}
                  selected={materiaId === null ? null : String(materiaId)}
                  onSelect={(k) => cambiarMateria(Number(k))}
                  maxHeight="max-h-72"
                />
              </>
            )}
          </>
        )}
        {info.error && <FeedbackBox feedback={info.error} />}
        {m && !m.es_oe && (
          <>
            <Field label="Otros códigos/materias que compartirán esta misma comisión (opcional)">
              <MultiSelect
                opciones={m.adicionales.map((a) => ({ value: a.materia_id, label: a.etiqueta }))}
                value={adicionales}
                onChange={setAdicionales}
                disabled={!puede}
              />
            </Field>
            {m.info_multicodigo && (
              <>
                <Aviso feedback={{ tone: "info", text: m.info_multicodigo }} />
                <TablaLibre rows={m.resumen} />
              </>
            )}
            {m.info_compartida && <Aviso feedback={{ tone: "info", text: m.info_compartida }} />}
          </>
        )}
        {m && m.es_oe && (
          <>
            <Caption>
              Las Optativas/Electivas mantienen una única opción curricular concreta por comisión; la función multicódigo se usa
              para materias comunes.
            </Caption>
            <Aviso
              feedback={{
                tone: "info",
                text: `Este es un espacio formal ${m.tipo_espacio} del plan. Seleccioná la materia concreta que realmente se dictará. Aunque esa opción esté habilitada también para otras Optativas/Electivas, esta comisión quedará vinculada únicamente al código/espacio formal que seleccionaste. Los demás espacios se abren como comisiones separadas.`,
              }}
            />
            <Field label="Buscar opción curricular concreta">
              <TextInput value={buscarOpcion} placeholder="Nombre, código, unidad académica oferente o carrera habilitada" onChange={setBuscarOpcion} />
            </Field>
            {(m.opciones ?? []).length === 0 ? (
              <Aviso
                feedback={{
                  tone: "warning",
                  text: "No hay opciones curriculares activas habilitadas para este espacio. Registralas y vinculalas desde Materias → Optativas / Electivas antes de abrir la comisión.",
                }}
              />
            ) : (
              <>
                <p className="text-sm font-medium text-slate-700">Opciones habilitadas</p>
                <Tabla
                  rows={m.opciones ?? []}
                  cols={[
                    { key: "codigo", label: "Código opción" },
                    { key: "nombre", label: "Materia concreta" },
                    { key: "tipo", label: "Tipo" },
                    { key: "escuela_oferente", label: "Unidad académica oferente" },
                    { key: "carreras_habilitadas", label: "Carreras habilitadas" },
                    { key: "espacios_plan", label: "Espacios que satisface" },
                  ]}
                  rowKey={(r) => String(r.id)}
                  selected={opcionId === null ? null : String(opcionId)}
                  onSelect={(k) => setOpcionId(Number(k))}
                  maxHeight="max-h-64"
                />
                {opcionId !== null && (m.vinculos_opcion ?? []).length > 0 && (
                  <>
                    <p className="text-sm font-semibold text-slate-700">Código/espacio que integrará esta comisión:</p>
                    <TablaLibre rows={m.vinculos_opcion ?? []} />
                  </>
                )}
              </>
            )}
          </>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Comisión">
            <TextInput value={nombre} placeholder="Ej.: 1, 2, A, B" onChange={setNombre} disabled={!puede} />
          </Field>
          <Field label="Sede">
            <Select value={sede} options={data.catalogos.sedes} onChange={setSede} disabled={!puede} />
          </Field>
          <Field label="Fecha de apertura">
            <DateInput value={fecha} onChange={setFecha} disabled={!puede} label="Fecha de apertura" />
          </Field>
          <Field label="Turno">
            <Select value={turno} options={data.catalogos.turnos} onChange={setTurno} disabled={!puede} />
          </Field>
          <Field label="Modalidad">
            <Select value={modalidad} options={data.catalogos.modalidades} onChange={setModalidad} disabled={!puede} />
          </Field>
          <div className="self-end">
            <Aviso feedback={{ tone: "info", text: "La comisión se registra operativamente como activa." }} />
          </div>
        </div>
        <Field label="Observaciones generales de la comisión">
          <Textarea value={obs} onChange={setObs} disabled={!puede} />
        </Field>
      </Card>

      <Card>
        <h4 className="text-base font-semibold text-brand-950">2. Días y horarios</h4>
        <Caption>Indicá todos los encuentros semanales antes de abrir la comisión.</Caption>
        <div className="max-w-xs">
          <Field label="Cantidad de días/horarios semanales">
            <input
              type="number"
              min={1}
              max={7}
              step={1}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={horarios.length}
              disabled={!puede}
              onChange={(e) => {
                const n = Math.min(7, Math.max(1, Math.trunc(Number(e.target.value) || 1)));
                cambiarHorarios((hs) => (n > hs.length ? [...hs, ...Array.from({ length: n - hs.length }, () => HORARIO_INICIAL)] : hs.slice(0, n)));
              }}
            />
          </Field>
        </div>
        {horarios.map((h, i) => (
          <div key={i} className="space-y-1">
            <p className="text-sm font-semibold text-slate-700">Horario {i + 1}</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Día">
                <Select value={h.dia} options={data.catalogos.dias} onChange={(v) => cambiarHorarios((hs) => hs.map((x, j) => (j === i ? { ...x, dia: v } : x)))} disabled={!puede} />
              </Field>
              <Field label="Hora de inicio">
                <TimeInput label={`Hora de inicio ${i + 1}`} value={h.hora_inicio} onChange={(v) => cambiarHorarios((hs) => hs.map((x, j) => (j === i ? { ...x, hora_inicio: v } : x)))} disabled={!puede} />
              </Field>
              <Field label="Hora de finalización">
                <TimeInput label={`Hora de finalización ${i + 1}`} value={h.hora_fin} onChange={(v) => cambiarHorarios((hs) => hs.map((x, j) => (j === i ? { ...x, hora_fin: v } : x)))} disabled={!puede} />
              </Field>
            </div>
            <Caption>Duración: {g(horasHorario(h.hora_inicio, h.hora_fin))} hs</Caption>
          </div>
        ))}
        <div className="max-w-xs">
          <Metric label="Carga horaria semanal total" value={`${g(horasTotales)} hs`} />
        </div>
      </Card>

      <Card>
        <h4 className="text-base font-semibold text-brand-950">3. Docentes asignados</h4>
        {docs.error && <FeedbackBox feedback={docs.error} />}
        {docs.data && listaDocentes.length === 0 ? (
          <Aviso
            feedback={{
              tone: "warning",
              text: "No hay docentes activos disponibles en el período actual. Primero registrá sus designaciones o incorporalos como prestados.",
            }}
          />
        ) : (
          <Field label="Seleccioná uno o más docentes">
            <MultiSelect
              opciones={listaDocentes.map((d) => ({ value: d.cuil, label: d.etiqueta_alta }))}
              value={docentes.map((d) => d.cuil)}
              onChange={(nuevos) => {
                const actuales = docentes.map((d) => d.cuil);
                nuevos.filter((c) => !actuales.includes(c)).forEach((c) => alternarDocente(c, true));
                actuales.filter((c) => !nuevos.includes(c)).forEach((c) => alternarDocente(c, false));
              }}
              disabled={!puede}
            />
          </Field>
        )}
        {docentes.map((d) => {
          const fila = listaDocentes.find((x) => x.cuil === d.cuil);
          const etiqueta = fila?.etiqueta_alta ?? d.cuil;
          const r = roles[d.cuil];
          const opcionesRol = r && r.roles.length > 1 ? r.roles : data.catalogos.roles;
          return (
            <div key={d.cuil} className="space-y-2 rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-800">{etiqueta}</p>
              {(r?.prestado_local || etiqueta.includes("Prestado")) && (
                <Caption>Docente prestado: el cargo se toma de su departamento de origen cuando está disponible.</Caption>
              )}
              {r && r.roles.length === 1 ? (
                <Aviso feedback={{ tone: "info", text: `Cargo tomado automáticamente: ${r.roles[0]}` }} />
              ) : (
                <div className="max-w-xs">
                  <Field label="Cargo para esta comisión">
                    <Select
                      value={d.rol}
                      options={opcionesRol}
                      onChange={(v) => setDocentes((ds) => ds.map((x) => (x.cuil === d.cuil ? { ...x, rol: v } : x)))}
                      disabled={!puede}
                    />
                  </Field>
                </div>
              )}
              {r && r.roles.length === 0 && (
                <Aviso feedback={{ tone: "warning", text: "No se detectó un cargo activo para este docente en el período. Revisá su designación." }} />
              )}
              <p className="text-sm font-semibold text-slate-700">Horario efectivo que cubrirá este docente</p>
              <FranjasForm
                franjas={franjas}
                value={d.seleccion}
                onChange={(sel) => setDocentes((ds) => ds.map((x) => (x.cuil === d.cuil ? { ...x, seleccion: sel } : x)))}
                disabled={!puede}
                metrica="Horas semanales de este docente"
              />
            </div>
          );
        })}
        <Field label="Observaciones de las asignaciones docentes">
          <Textarea value={obsAsig} onChange={setObsAsig} disabled={!puede} />
        </Field>
      </Card>

      <Caption>Al guardar se crearán conjuntamente la comisión, todos sus horarios y todas sus asignaciones docentes.</Caption>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton onClick={abrir} busy={accion.busy} disabled={materiaId === null}>
          ➕ Abrir comisión con horarios y docentes
        </PrimaryButton>
      )}
    </section>
  );
}

export function MultiSelect<V extends string | number>({
  opciones,
  value,
  onChange,
  disabled,
}: {
  opciones: { value: V; label: string }[];
  value: V[];
  onChange: (v: V[]) => void;
  disabled?: boolean;
}) {
  const [q, setQ] = useState("");
  const visibles = q ? opciones.filter((o) => o.label.toLocaleLowerCase().includes(q.toLocaleLowerCase())) : opciones;
  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((v) => (
            <span key={String(v)} className="flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-800">
              {opciones.find((o) => o.value === v)?.label ?? String(v)}
              {!disabled && (
                <button type="button" aria-label="Quitar" className="text-brand-700" onClick={() => onChange(value.filter((x) => x !== v))}>
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <input
        className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        placeholder="Buscar…"
        value={q}
        disabled={disabled}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="max-h-48 overflow-auto rounded-lg border border-slate-200">
        {visibles.map((o) => (
          <label key={String(o.value)} className="flex items-start gap-2 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-brand-600"
              checked={value.includes(o.value)}
              disabled={disabled}
              onChange={(e) => onChange(e.target.checked ? [...value, o.value] : value.filter((x) => x !== o.value))}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
