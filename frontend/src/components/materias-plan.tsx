"use client";

// Submódulo 2 · Plan de estudio / Materias — pestañas "📋 Plan de estudio", "➕ Agregar materia" y
// "📥 Carga rápida de plan" (entry l. 68791-69305).
import { useState } from "react";
import {
  Card,
  Check,
  DataTable,
  Details,
  FeedbackBox,
  Field,
  PrimaryButton,
  Radio,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import {
  EscuelaFiltro,
  MateriaFields,
  Metric,
  ReadOnlyNote,
  type TabProps,
  materiaDefaults,
  useAccion,
  useConsulta,
} from "@/components/materias-shared";
import { type MateriaForm, type Opcion, type Row, type WriteResult, post } from "@/lib/materias";
import { etiquetaColumna } from "@/lib/unidades-academicas";

type PlanResp = {
  hay_carreras_activas: boolean;
  opciones: Opcion[];
  carrera: Row | null;
  plan: Row[];
  metricas?: { materias: number; horas_totales: number; activas: number; duracion: string };
};

const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v).trim());

// ---------------------------------------------------------------------------------------------- Plan de estudio
export function PlanTab({ data, onDone, onError }: TabProps) {
  const [escuela, setEscuela] = useState("Todas");
  const [carreraId, setCarreraId] = useState<number | null>(null);
  const [version, setVersion] = useState(0);
  const consulta = useConsulta<PlanResp>("plan", { escuela, carrera_id: carreraId }, onError, version);
  const resp = consulta.data;
  const opciones = resp?.opciones ?? [];
  const elegido = opciones.find((o) => o.id === carreraId) ?? opciones[0] ?? null;
  if (resp && elegido && elegido.id !== carreraId) setCarreraId(elegido.id);

  const after = async (f: Parameters<TabProps["onDone"]>[0]) => {
    setVersion((v) => v + 1);
    await onDone(f);
  };

  if (resp && !resp.hay_carreras_activas) {
    return (
      <FeedbackBox
        feedback={{ tone: "warning", text: "Primero registrá una carrera en la pestaña 'Unidades académicas y carreras'." }}
      />
    );
  }
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Plan de estudio por carrera</h3>
      <div className="grid gap-4 md:grid-cols-2">
        <EscuelaFiltro
          label="Unidad académica"
          escuelas={data.escuelas}
          value={escuela}
          onChange={(v) => {
            setEscuela(v);
            setCarreraId(null);
          }}
        />
        {opciones.length > 0 && (
          <Field label="Carrera / plan">
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={elegido?.id ?? ""}
              onChange={(e) => setCarreraId(Number(e.target.value))}
            >
              {opciones.map((o) => (
                <option key={o.id ?? o.etiqueta} value={o.id ?? ""}>
                  {o.etiqueta}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {resp && opciones.length === 0 && (
        <FeedbackBox feedback={{ tone: "info", text: "No hay carreras activas para la unidad académica seleccionada." }} />
      )}
      {resp?.carrera && (
        <div className="space-y-4">
          <div>
            <h4 className="text-xl font-semibold text-brand-950">{txt(resp.carrera.nombre)}</h4>
            <p className="text-xs text-slate-500">
              Unidad académica: {txt(resp.carrera.escuela)} · Plan: {txt(resp.carrera.plan_version) || "-"} · Título:{" "}
              {txt(resp.carrera.titulo_otorga) || "-"}
            </p>
          </div>
          {resp.plan.length === 0 ? (
            <FeedbackBox feedback={{ tone: "info", text: "Esta carrera todavía no tiene materias cargadas." }} />
          ) : (
            <>
              {resp.metricas && (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric label="Materias del plan" value={resp.metricas.materias} />
                  <Metric label="Horas totales del plan" value={resp.metricas.horas_totales} />
                  <Metric label="Materias activas" value={resp.metricas.activas} />
                  <Metric label="Duración de la carrera" value={resp.metricas.duracion} />
                </div>
              )}
              <p className="text-xs text-slate-500">
                Podés editar directamente las columnas Código y Asignatura en cada cuadro. El resto de los datos del
                plan queda bloqueado para evitar cambios accidentales.
              </p>
              {data.catalogos.anios.map((anio) => {
                const filas = resp.plan.filter((r) => r.anio === anio);
                if (filas.length === 0) return null;
                return (
                  <GrillaAnio
                    key={`${anio}|${filas.map((f) => f.huella).join()}`}
                    anio={anio}
                    filas={filas}
                    carreraId={Number(resp.carrera?.id)}
                    puedeEscribir={data.permisos.puede_escribir}
                    onDone={after}
                    onError={onError}
                  />
                );
              })}
              {data.permisos.puede_borrar && (
                <QuitarDelPlan
                  key={resp.plan.map((f) => f.huella).join()}
                  filas={resp.plan}
                  carreraId={Number(resp.carrera.id)}
                  onDone={after}
                  onError={onError}
                />
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

const GRILLA_COLS: [string, string][] = [
  ["orden", "Orden"],
  ["codigo", "Código"],
  ["asignatura", "Asignatura"],
  ["cuatrimestre", "Cuatrimestre"],
  ["dictado", "Dictado"],
  ["carga_semanal", "Hs. sem."],
  ["carga_total", "Hs. total"],
  ["duracion", "Duración"],
  ["estado", "Estado"],
  ["observaciones", "Observaciones"],
  ["comparticion_modo", "comparticion_modo"],
  ["comparticion_grupo", "comparticion_grupo"],
];

function GrillaAnio({
  anio,
  filas,
  carreraId,
  puedeEscribir,
  onDone,
  onError,
}: {
  anio: string;
  filas: Row[];
  carreraId: number;
  puedeEscribir: boolean;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const [edit, setEdit] = useState<Record<number, { codigo: string; asignatura: string }>>({});
  const accion = useAccion(onDone, onError);
  const cambios = filas
    .map((f) => {
      const id = Number(f.id);
      const e = edit[id];
      if (!e) return null;
      return e.codigo.trim() !== txt(f.codigo) || e.asignatura.trim() !== txt(f.asignatura)
        ? { id, codigo: e.codigo.trim(), asignatura: e.asignatura.trim(), huella: f.huella }
        : null;
    })
    .filter(Boolean);

  return (
    <div className="space-y-2">
      <h5 className="font-semibold text-slate-800">{anio}</h5>
      <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              {GRILLA_COLS.map(([, l]) => (
                <th key={l} className="whitespace-nowrap px-3 py-2 font-medium">
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filas.map((f) => {
              const id = Number(f.id);
              const e = edit[id] ?? { codigo: txt(f.codigo), asignatura: txt(f.asignatura) };
              return (
                <tr key={id}>
                  {GRILLA_COLS.map(([k]) =>
                    (k === "codigo" || k === "asignatura") && puedeEscribir ? (
                      <td key={k} className="px-2 py-1">
                        <input
                          className="w-full min-w-24 rounded border border-slate-300 px-2 py-1 text-sm"
                          value={e[k]}
                          disabled={accion.busy}
                          onChange={(ev) => setEdit((s) => ({ ...s, [id]: { ...e, [k]: ev.target.value } }))}
                        />
                      </td>
                    ) : (
                      <td key={k} className="whitespace-nowrap px-3 py-2 text-slate-700">
                        {f[k] === null ? "" : String(f[k])}
                      </td>
                    )
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {puedeEscribir && (
        <div className="flex items-center gap-4">
          <PrimaryButton
            onClick={() => accion.run(() => post<WriteResult>("plan/guardar", { carrera_id: carreraId, cambios }))}
            busy={accion.busy}
            disabled={cambios.length === 0}
          >
            Guardar cambios
          </PrimaryButton>
          {cambios.length > 0 && (
            <span className="text-xs text-slate-500">Cambios pendientes en este cuadro: {cambios.length} materia(s).</span>
          )}
        </div>
      )}
      {accion.error && <p className="text-sm text-red-600">{accion.error}</p>}
    </div>
  );
}

function QuitarDelPlan({
  filas,
  carreraId,
  onDone,
  onError,
}: {
  filas: Row[];
  carreraId: number;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const [sel, setSel] = useState<number[]>([]);
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const etiqueta = (r: Row) =>
    `${txt(r.codigo) || "(sin código)"} - ${txt(r.asignatura) || "(sin asignatura)"} — ${txt(r.anio)} — C${txt(r.cuatrimestre)}`;

  async function quitar() {
    setError(null);
    if (sel.length === 0) return setError("Seleccioná al menos una materia.");
    if (!confirmar) return setError("Primero confirmá que querés quitar las materias seleccionadas de este plan.");
    setBusy(true);
    try {
      const r = await post<{ errores: string[]; quitadas: number; error?: string; mensaje?: string }>("plan/quitar", {
        carrera_id: carreraId,
        confirmar,
        materias: filas.filter((f) => sel.includes(Number(f.id))).map((f) => ({ id: f.id, huella: f.huella })),
      });
      if (r.error) setError(r.error);
      if (r.mensaje) await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="Quitar materias de este plan">
      <p className="text-xs text-slate-500">
        Seleccioná una o varias materias. Dejarán de formar parte únicamente de este plan, pero no se borra su
        historial. Las comisiones ya registradas siguen conservando la materia y las apariciones de esa misma materia en
        otros planes no se modifican.
      </p>
      <div className="max-h-64 space-y-1 overflow-auto rounded-lg border border-slate-200 p-3">
        {filas.map((f) => (
          <Check
            key={String(f.id)}
            checked={sel.includes(Number(f.id))}
            onChange={(v) => setSel((s) => (v ? [...s, Number(f.id)] : s.filter((x) => x !== Number(f.id))))}
            disabled={busy}
            label={etiqueta(f)}
          />
        ))}
      </div>
      {sel.length > 0 && <p className="text-xs text-slate-500">Materias seleccionadas: {sel.length}</p>}
      <Check
        checked={confirmar}
        onChange={setConfirmar}
        disabled={busy}
        label="Confirmo que quiero quitar del plan las materias seleccionadas"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <PrimaryButton tone="danger" onClick={quitar} busy={busy}>
        Quitar materias seleccionadas del plan
      </PrimaryButton>
    </Details>
  );
}

// ---------------------------------------------------------------------------------------------- Agregar materia
const MODO_NUEVA = "Crear materia nueva";
const MODO_REUSAR = "Usar materia ya creada";

export function AgregarTab({ data, onDone, onError }: TabProps) {
  const opciones = data.opciones_activas;
  const [carreraId, setCarreraId] = useState<number | null>(opciones[0]?.id ?? null);
  const [modo, setModo] = useState(MODO_NUEVA);
  if (opciones.length === 0) {
    return <FeedbackBox feedback={{ tone: "warning", text: "Primero registrá una carrera activa." }} />;
  }
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Agregar materia al plan de estudio</h3>
      <Field label="Carrera / plan destino">
        <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={carreraId ?? ""}
          onChange={(e) => setCarreraId(Number(e.target.value))}
        >
          {opciones.map((o) => (
            <option key={o.id ?? o.etiqueta} value={o.id ?? ""}>
              {o.etiqueta}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Cómo querés cargar la materia">
        <Radio name="modo_alta_materia" value={modo} options={[MODO_NUEVA, MODO_REUSAR]} onChange={setModo} />
      </Field>
      {!data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : modo === MODO_NUEVA ? (
        <FormularioMateria key={`nueva-${carreraId}`} data={data} carreraId={carreraId} onDone={onDone} onError={onError} />
      ) : (
        <Reutilizar key={`reusar-${carreraId}`} data={data} carreraId={carreraId} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

function FormularioMateria({
  data,
  carreraId,
  datos,
  soloAnio,
  boton = "Agregar materia",
  onDone,
  onError,
}: TabProps & { carreraId: number | null; datos?: Row; soloAnio?: boolean; boton?: string }) {
  const [form, setForm] = useState<MateriaForm>(() => materiaDefaults(data, datos));
  const accion = useAccion(onDone, onError);
  const dup = useConsulta<{ duplicadas: Row[] }>(
    "materias/duplicado",
    { carrera_id: carreraId, codigo: form.codigo, asignatura: form.asignatura },
    onError,
    0,
    Boolean(form.asignatura)
  );
  const duplicadas = form.asignatura ? (dup.data?.duplicadas ?? []) : [];

  async function submit() {
    accion.setError(null);
    if (!form.asignatura) return accion.setError("Completá al menos el nombre de la asignatura.");
    if (duplicadas.length) return accion.setError("La materia ya existe en este plan. No se creó una segunda aparición.");
    const r = await accion.run(() => post<WriteResult>("materias/alta", { ...form, carrera_id: carreraId }));
    if (r && !soloAnio) setForm(materiaDefaults(data));
  }

  return (
    <Card>
      <MateriaFields form={form} set={(p) => setForm((f) => ({ ...f, ...p }))} data={data} disabled={accion.busy}
        soloAnio={soloAnio} />
      {duplicadas.length > 0 && (
        <>
          <FeedbackBox
            feedback={{
              tone: "warning",
              text:
                "Esta materia ya existe dentro de esta carrera / plan. El sistema no permite duplicar el mismo " +
                "código/materia dentro de un plan.",
            }}
          />
          <DataTable
            rows={duplicadas}
            columns={["id", "codigo", "asignatura", "anio", "cuatrimestre", "carga_semanal", "carga_total"].map((k) => ({
              key: k,
              label: k,
            }))}
            rowKey={(_, i) => String(i)}
            maxHeight="max-h-40"
          />
        </>
      )}
      {accion.error && <p className="text-sm text-red-600">{accion.error}</p>}
      <PrimaryButton onClick={submit} busy={accion.busy}>
        {boton}
      </PrimaryButton>
    </Card>
  );
}

const EXISTENTES_COLS = [
  ["codigo", "Código"],
  ["asignatura", "Asignatura"],
  ["carrera", "Carrera"],
  ["escuela", "Unidad académica"],
  ["plan_version", "Plan"],
  ["anio", "Año"],
  ["cuatrimestre", "Cuatrimestre"],
  ["dictado", "Dictado"],
  ["carga_semanal", "Hs. sem."],
  ["carga_total", "Hs. total"],
  ["duracion", "Duración"],
  ["estado", "Estado"],
].map(([key, label]) => ({ key, label }));

function Reutilizar({ data, carreraId, onDone, onError }: TabProps & { carreraId: number | null }) {
  const [incluir, setIncluir] = useState(false);
  const [f, setF] = useState({ busqueda: "", escuela: "Todas", carrera: "Todas", cuatrimestre: "Todos", anio: "Todos",
    estado: "Todos" });
  const [sel, setSel] = useState<number | null>(null);
  const consulta = useConsulta<{ hay_existentes: boolean; opciones: Record<string, string[]>; materias: Row[] }>(
    "materias/existentes",
    { carrera_id: carreraId, incluir_mismo_plan: incluir, ...f },
    onError
  );
  const r = consulta.data;
  const fila = r?.materias.find((m) => Number(m.id) === sel) ?? r?.materias[0] ?? null;
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Elegí una materia ya cargada en otro plan o carrera y copiala al plan destino. En esta pantalla solo se puede
        cambiar el año; el resto de los datos se edita desde &apos;Editar / eliminar materia&apos;.
      </p>
      <Check checked={incluir} onChange={setIncluir} label="Incluir materias que ya están cargadas en el plan destino" />
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {r && !r.hay_existentes ? (
        <>
          <FeedbackBox
            feedback={{ tone: "info", text: "Todavía no hay materias previas para reutilizar. Cargá una materia nueva primero." }}
          />
          <FormularioMateria data={data} carreraId={carreraId} boton="Agregar materia nueva" onDone={onDone}
            onError={onError} />
        </>
      ) : (
        r && (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Buscar materia existente">
                <TextInput value={f.busqueda} onChange={(v) => set({ busqueda: v })}
                  placeholder="Código, nombre, unidad académica, carrera, plan..." />
              </Field>
              <Field label="Unidad académica">
                <Select value={f.escuela} options={["Todas", ...(r.opciones.escuela ?? [])]} onChange={(v) => set({ escuela: v })} />
              </Field>
              <Field label="Cuatrimestre">
                <Select value={f.cuatrimestre} options={["Todos", ...(r.opciones.cuatrimestre ?? [])]}
                  onChange={(v) => set({ cuatrimestre: v })} />
              </Field>
              <Field label="Carrera">
                <Select value={f.carrera} options={["Todas", ...(r.opciones.carrera ?? [])]} onChange={(v) => set({ carrera: v })} />
              </Field>
              <Field label="Año">
                <Select value={f.anio} options={["Todos", ...(r.opciones.anio ?? [])]} onChange={(v) => set({ anio: v })} />
              </Field>
              <Field label="Estado">
                <Select value={f.estado} options={["Todos", ...(r.opciones.estado ?? [])]} onChange={(v) => set({ estado: v })} />
              </Field>
            </div>
            {r.materias.length === 0 ? (
              <FeedbackBox feedback={{ tone: "warning", text: "No encontré materias con esos filtros." }} />
            ) : (
              fila && (
                <>
                  <p className="text-xs text-slate-500">Coincidencias encontradas: {r.materias.length}</p>
                  <p className="text-sm font-medium text-slate-700">Materias encontradas</p>
                  <DataTable rows={r.materias} columns={EXISTENTES_COLS} rowKey={(m) => String(m.id)}
                    selected={String(fila.id)} onSelect={(k) => setSel(Number(k))} maxHeight="max-h-72" />
                  <FeedbackBox
                    feedback={{
                      tone: "info",
                      text:
                        "Los datos de la materia seleccionada se copian debajo. Desde acá solo podés modificar el año " +
                        "para ubicarla en el plan destino.",
                    }}
                  />
                  <FormularioMateria key={String(fila.id)} data={data} carreraId={carreraId} datos={fila} soloAnio
                    boton="Agregar esta materia al plan destino" onDone={onDone} onError={onError} />
                </>
              )
            )}
          </>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- Carga rápida de plan
type Preview = {
  filas: Row[];
  duplicadas?: Row[];
  conflictos_tabla?: Row[];
  conflictos_base?: Row[];
  aviso: string | null;
};

const COLS_PREVIEW = ["codigo", "asignatura", "anio", "cuatrimestre", "dictado", "carga_semanal", "carga_total",
  "duracion", "orden", "estado", "observaciones"].map((k) => ({ key: k, label: etiquetaColumna(k) }));
const cols = (rows?: Row[]) => Object.keys(rows?.[0] ?? {}).map((k) => ({ key: k, label: etiquetaColumna(k) }));

export function CargaRapidaPlanTab({ data, onDone, onError }: TabProps) {
  const opciones = data.opciones_activas;
  const [carreraId, setCarreraId] = useState<number | null>(opciones[0]?.id ?? null);
  const [texto, setTexto] = useState("");
  const [reemplazar, setReemplazar] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  const prev = useConsulta<Preview>("carga-rapida/previsualizar", { carrera_id: carreraId, texto, reemplazar }, onError,
    0, Boolean(texto.trim()));
  const p = texto.trim() ? prev.data : null;

  async function cargar() {
    accion.setError(null);
    if (!confirmar) return accion.setError("Primero confirmá que revisaste la vista previa.");
    if ((p?.conflictos_tabla?.length ?? 0) || (p?.conflictos_base?.length ?? 0))
      return accion.setError(
        "Hay conflictos de código. Un mismo código no puede tener nombres distintos dentro de la misma universidad."
      );
    if (p?.duplicadas?.length)
      return accion.setError(
        "Hay materias duplicadas. Corregilas antes de cargar; el sistema no permite duplicados dentro del mismo plan."
      );
    const r = await accion.run(() =>
      post<WriteResult>("carga-rapida", { carrera_id: carreraId, texto, reemplazar, confirmar })
    );
    if (r) {
      setTexto("");
      setConfirmar(false);
      setReemplazar(false);
    }
  }

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Carga rápida de plan</h3>
      <FeedbackBox
        feedback={{
          tone: "warning",
          text:
            "Esta opción no importa archivos. Sirve para pegar una tabla copiada desde Excel y cargar muchas materias " +
            "dentro de la carrera seleccionada. Revisá la vista previa antes de confirmar.",
        }}
      />
      {opciones.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: "Primero registrá una carrera activa." }} />
      ) : (
        <>
          <Field label="Carrera / plan destino">
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={carreraId ?? ""}
              onChange={(e) => setCarreraId(Number(e.target.value))}
            >
              {opciones.map((o) => (
                <option key={o.id ?? o.etiqueta} value={o.id ?? ""}>
                  {o.etiqueta}
                </option>
              ))}
            </select>
          </Field>
          <div>
            <p className="mb-1 text-sm text-slate-700">Columnas aceptadas:</p>
            <code className="block rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
              codigo | asignatura | anio | cuatrimestre | dictado | carga_semanal | carga_total | duracion | orden
            </code>
          </div>
          {!data.permisos.puede_escribir && <ReadOnlyNote />}
          <Field label="Pegá acá la tabla del plan de estudio">
            <Textarea value={texto} onChange={setTexto} rows={9} disabled={accion.busy} />
          </Field>
          {prev.error && texto.trim() && <FeedbackBox feedback={{ tone: "error", text: prev.error }} />}
          {p?.aviso && <FeedbackBox feedback={{ tone: "error", text: p.aviso }} />}
          {p && p.filas.length > 0 && (
            <div className="space-y-4">
              <h4 className="text-base font-semibold text-brand-950">Vista previa</h4>
              <DataTable rows={p.filas} columns={COLS_PREVIEW} rowKey={(_, i) => String(i)} maxHeight="max-h-72" />
              <p className="text-xs text-slate-500">Materias detectadas: {p.filas.length}</p>
              <Check checked={reemplazar} onChange={setReemplazar} disabled={accion.busy}
                label="Reemplazar las materias existentes de esta carrera / plan antes de cargar" />
              {(p.conflictos_tabla?.length ?? 0) > 0 && (
                <>
                  <FeedbackBox feedback={{ tone: "error", text: "Atención: en la tabla pegada hay códigos repetidos con nombres de materia distintos. Corregí eso antes de cargar." }} />
                  <DataTable rows={p.conflictos_tabla ?? []} columns={cols(p.conflictos_tabla)} rowKey={(_, i) => String(i)} maxHeight="max-h-48" />
                </>
              )}
              {(p.conflictos_base?.length ?? 0) > 0 && (
                <>
                  <FeedbackBox feedback={{ tone: "error", text: "Atención: hay códigos que ya existen en la base con otro nombre de materia. No se pueden cargar así." }} />
                  <DataTable rows={p.conflictos_base ?? []} columns={cols(p.conflictos_base)} rowKey={(_, i) => String(i)} maxHeight="max-h-48" />
                </>
              )}
              {(p.duplicadas?.length ?? 0) > 0 && (
                <>
                  <FeedbackBox feedback={{ tone: "error", text: "Atención: hay materias repetidas dentro del plan o dentro de la tabla pegada. El régimen definitivo no permite duplicarlas; corregí esas filas o usá Reemplazar plan si corresponde." }} />
                  <DataTable rows={p.duplicadas ?? []} columns={cols(p.duplicadas)} rowKey={(_, i) => String(i)} maxHeight="max-h-48" />
                </>
              )}
              {data.permisos.puede_escribir && (
                <>
                  <Check checked={confirmar} onChange={setConfirmar} disabled={accion.busy}
                    label="Confirmo que revisé la vista previa y quiero cargar estas materias" />
                  {accion.error && <p className="text-sm text-red-600">{accion.error}</p>}
                  <PrimaryButton onClick={cargar} busy={accion.busy}>
                    Cargar materias pegadas
                  </PrimaryButton>
                </>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

