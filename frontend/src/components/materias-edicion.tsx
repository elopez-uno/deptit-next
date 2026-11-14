"use client";

// Submódulo 2 · Plan de estudio / Materias — pestañas "✏️ Editar / eliminar materia", "📊 Materias totales" y
// "🔎 Materias únicas" (entry l. 69307-69759).
import { useState } from "react";
import {
  Card,
  Check,
  DataTable,
  Details,
  FeedbackBox,
  Field,
  PrimaryButton,
  Select,
  TextInput,
} from "@/components/module-ui";
import {
  EscuelaFiltro,
  MateriaFields,
  ReadOnlyNote,
  type TabProps,
  materiaDefaults,
  useAccion,
  useConsulta,
} from "@/components/materias-shared";
import { type MateriaForm, type Opcion, type Row, type WriteResult, post } from "@/lib/materias";
import { etiquetaColumna } from "@/lib/unidades-academicas";

const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v).trim());
const colsDe = (keys: [string, string][]) => keys.map(([key, label]) => ({ key, label }));

// ---------------------------------------------------------------------------------------------- Editar / eliminar
const EDIT_COLS = colsDe([
  ["codigo", "Código"], ["asignatura", "Asignatura"], ["carrera", "Carrera"], ["escuela", "Unidad académica"],
  ["plan_version", "Plan"], ["anio", "Año"], ["cuatrimestre", "Cuatrimestre"], ["dictado", "Dictado"],
  ["carga_semanal", "Hs. sem."], ["carga_total", "Hs. total"], ["estado", "Estado"],
]);

export function EditarMateriaTab({ data, onDone, onError }: TabProps) {
  const opciones: Opcion[] = [{ etiqueta: "Todas", id: null }, ...data.opciones_todas];
  const [carreraId, setCarreraId] = useState<number | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [version, setVersion] = useState(0);
  const consulta = useConsulta<{ vacio: boolean; materias: Row[] }>("materias/consulta",
    { carrera_id: carreraId, busqueda }, onError, version);
  const r = consulta.data;
  const fila = r?.materias.find((m) => Number(m.id) === sel) ?? r?.materias[0] ?? null;

  if (data.opciones_todas.length === 0) {
    return <FeedbackBox feedback={{ tone: "info", text: "No hay carreras registradas." }} />;
  }
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar materia</h3>
      <Field label="Carrera / plan">
        <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={carreraId ?? ""}
          onChange={(e) => setCarreraId(e.target.value === "" ? null : Number(e.target.value))}
        >
          {opciones.map((o) => (
            <option key={o.etiqueta} value={o.id ?? ""}>
              {o.etiqueta}
            </option>
          ))}
        </select>
      </Field>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {r && r.vacio ? (
        <FeedbackBox
          feedback={{
            tone: "info",
            text:
              carreraId === null
                ? "No hay materias cargadas para editar en la universidad seleccionada."
                : "No hay materias para editar en esta carrera.",
          }}
        />
      ) : (
        r && (
          <>
            <Field label="Buscar materia por código o nombre">
              <TextInput value={busqueda} onChange={setBusqueda} placeholder="Escribí parte del código o de la asignatura" />
            </Field>
            {r.materias.length === 0 || !fila ? (
              <FeedbackBox
                feedback={{ tone: "info", text: "No hay materias que coincidan con la búsqueda dentro de esta carrera." }}
              />
            ) : (
              <>
                <p className="text-sm font-medium text-slate-700">Materias encontradas</p>
                <DataTable rows={r.materias} columns={EDIT_COLS} rowKey={(m) => String(m.id)} selected={String(fila.id)}
                  onSelect={(k) => setSel(Number(k))} maxHeight="max-h-72" />
                <MateriaSeleccionada
                  key={`${fila.id}|${fila.huella}`}
                  data={data}
                  id={Number(fila.id)}
                  todas={carreraId === null}
                  onDone={async (f) => {
                    setVersion((v) => v + 1);
                    await onDone(f);
                  }}
                  onError={onError}
                />
              </>
            )}
          </>
        )
      )}
    </section>
  );
}

type Aparicion = Row & { etiqueta: string; modo_etiqueta: string };

function MateriaSeleccionada({ data, id, todas, onDone, onError }: TabProps & { id: number; todas: boolean }) {
  const det = useConsulta<{ materia: Row; apariciones: Aparicion[] }>("materias/detalle", { id }, onError);
  if (det.error) return <FeedbackBox feedback={{ tone: "error", text: det.error }} />;
  if (!det.data) return <p className="text-sm text-slate-500">Cargando materia…</p>;
  return <EditarMateriaForm key={String(det.data.materia.huella)} data={data} materia={det.data.materia}
    apariciones={det.data.apariciones} todas={todas} onDone={onDone} onError={onError} />;
}

function EditarMateriaForm({
  data,
  materia,
  apariciones,
  todas,
  onDone,
  onError,
}: TabProps & { materia: Row; apariciones: Aparicion[]; todas: boolean }) {
  const etiquetas = data.catalogos.comparticion.map(([e]) => e);
  const modoAEtiqueta = Object.fromEntries(data.catalogos.comparticion.map(([e, m]) => [m, e]));
  const [form, setForm] = useState<MateriaForm>(() => materiaDefaults(data, materia));
  const carreraActual = data.opciones_todas.find((o) => o.id === Number(materia.carrera_id))?.id
    ?? data.opciones_todas[0]?.id ?? null;
  const [carreraId, setCarreraId] = useState<number | null>(carreraActual);
  const [modo, setModo] = useState<string>(modoAEtiqueta[txt(materia.comparticion_modo)] ?? etiquetas[0]);
  const grupo = txt(materia.comparticion_grupo);
  const defaults = grupo
    ? apariciones.filter((a) => txt(a.comparticion_grupo) === grupo).map((a) => Number(a.id))
    : [];
  const [seleccion, setSeleccion] = useState<number[]>(defaults.length ? defaults : [Number(materia.id)]);
  const guardar = useAccion(onDone, onError);
  const borrar = useAccion(onDone, onError);
  const [confirmar, setConfirmar] = useState(false);
  const esSeleccionada = modo === etiquetas[2];
  const campos = todas
    ? ["id", "carrera", "escuela", "plan_version", "codigo", "asignatura", "anio", "cuatrimestre", "dictado",
      "carga_semanal", "carga_total", "duracion", "estado", "observaciones"]
    : ["id", "codigo", "asignatura", "anio", "cuatrimestre", "dictado", "carga_semanal", "carga_total", "duracion",
      "estado", "observaciones"];

  async function submit() {
    const ids = esSeleccionada ? seleccion : [Number(materia.id)];
    await guardar.run(() =>
      post<WriteResult>("materias/editar", {
        ...form,
        id: materia.id,
        carrera_id: carreraId,
        huella: materia.huella,
        comparticion_modo: modo,
        seleccionados: ids,
      })
    );
  }

  async function eliminar() {
    borrar.setError(null);
    if (!confirmar) return borrar.setError("Primero confirmá la eliminación.");
    await borrar.run(() => post<WriteResult>("materias/eliminar", { id: materia.id, huella: materia.huella, confirmar }));
  }

  return (
    <div className="space-y-5">
      <Details summary="Datos actuales de la materia seleccionada" defaultOpen>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {campos.map((k) => (
            <div key={k} className="min-w-0">
              <dt className="text-xs text-slate-400">{etiquetaColumna(k)}</dt>
              <dd className="truncate text-slate-800">{txt(materia[k]) || "-"}</dd>
            </div>
          ))}
        </dl>
      </Details>
      {!data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : (
        <Card>
          <MateriaFields
            form={form}
            set={(p) => setForm((f) => ({ ...f, ...p }))}
            data={data}
            disabled={guardar.busy}
            extraIzquierda={
              <Field label="Carrera / plan">
                <select
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={carreraId ?? ""}
                  disabled={guardar.busy}
                  onChange={(e) => setCarreraId(Number(e.target.value))}
                >
                  {data.opciones_todas.map((o) => (
                    <option key={o.id ?? o.etiqueta} value={o.id ?? ""}>
                      {o.etiqueta}
                    </option>
                  ))}
                </select>
              </Field>
            }
          />
          <div className="space-y-3 border-t border-slate-100 pt-4">
            <h4 className="text-base font-semibold text-brand-950">Comportamiento entre planes</h4>
            <p className="text-xs text-slate-500">
              Por defecto, mismo código + mismo nombre se interpreta como una materia compartida. Podés hacer una
              excepción sin cambiar códigos oficiales ni recrear la materia.
            </p>
            <Field
              label="Comportamiento entre planes"
              hint="Automática agrupa todas las apariciones que mantengan ese modo. Específica deja esta aparición independiente. Seleccionada permite armar un grupo exacto de carreras/planes."
            >
              <Select value={modo} options={etiquetas} onChange={setModo} disabled={guardar.busy} />
            </Field>
            {apariciones.length > 0 && (
              <>
                <p className="text-sm font-medium text-slate-700">Apariciones con el mismo código y nombre:</p>
                <DataTable
                  rows={apariciones.map((a) => ({ ...a, comparticion_modo: a.modo_etiqueta }) as Row)}
                  columns={["id", "codigo", "asignatura", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
                    "comparticion_modo"].map((k) => ({ key: k, label: etiquetaColumna(k) }))}
                  rowKey={(a) => String(a.id)}
                  maxHeight="max-h-48"
                />
              </>
            )}
            {esSeleccionada ? (
              <>
                <Field label="Planes/carreras que compartirán esta materia"
                  hint="La aparición que estás editando se incluirá siempre. Elegí al menos otro plan/carrera.">
                  <div className="max-h-48 space-y-1 overflow-auto rounded-lg border border-slate-200 p-3">
                    {apariciones.map((a) => (
                      <Check
                        key={String(a.id)}
                        checked={seleccion.includes(Number(a.id))}
                        onChange={(v) =>
                          setSeleccion((s) => (v ? [...s, Number(a.id)] : s.filter((x) => x !== Number(a.id))))
                        }
                        disabled={guardar.busy}
                        label={a.etiqueta}
                      />
                    ))}
                  </div>
                </Field>
                <FeedbackBox
                  feedback={{
                    tone: "info",
                    text:
                      "Los planes no seleccionados que todavía estaban en modo automático (o que salgan del grupo que " +
                      "estás editando) quedarán como materias específicas. Los otros grupos seleccionados que ya hayas " +
                      "configurado se conservan, por lo que podés tener varios grupos independientes con el mismo " +
                      "código y nombre.",
                  }}
                />
              </>
            ) : modo === etiquetas[0] ? (
              <FeedbackBox feedback={{ tone: "info", text: "Esta materia se compartirá automáticamente con todas sus apariciones que tengan el mismo código y nombre." }} />
            ) : (
              <FeedbackBox feedback={{ tone: "info", text: "Esta aparición quedará vinculada únicamente a esta carrera/plan, aunque existan otras con el mismo código y nombre." }} />
            )}
          </div>
          {guardar.error && <p className="text-sm text-red-600">{guardar.error}</p>}
          <PrimaryButton onClick={submit} busy={guardar.busy}>
            Guardar cambios
          </PrimaryButton>
        </Card>
      )}
      {data.permisos.puede_borrar && (
        <Card>
          <h4 className="text-base font-semibold text-brand-950">Eliminar materia</h4>
          <p className="text-xs text-slate-500">
            Esta opción elimina definitivamente la materia y sus apariciones equivalentes. Solo se permite si ninguna
            comisión actual o histórica la referencia. Para retirarla de un plan conservando la historia, usá
            &apos;Quitar materias de este plan&apos;.
          </p>
          <Check checked={confirmar} onChange={setConfirmar} disabled={borrar.busy}
            label="Confirmo que quiero eliminar esta materia" />
          {borrar.error && <p className="text-sm text-red-600">{borrar.error}</p>}
          <PrimaryButton tone="danger" onClick={eliminar} busy={borrar.busy}>
            Eliminar materia
          </PrimaryButton>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- Materias totales
type TotalesResp = {
  materias: Row[];
  total_base: number;
  opciones_carrera: Opcion[];
  hay_fuera_plan: boolean;
  archivadas: Row[];
  archivadas_huella?: string;
};

const colsAuto = (rows: Row[]) => Object.keys(rows[0] ?? {}).map((k) => ({ key: k, label: etiquetaColumna(k) }));

export function TotalesTab({ data, onDone, onError }: TabProps) {
  const c = data.catalogos;
  const [f, setF] = useState({ escuela: "Todas", carrera_id: null as number | null, cuatrimestre: "Todos",
    estado: "Todos", busqueda: "" });
  const [version, setVersion] = useState(0);
  const consulta = useConsulta<TotalesResp>("totales", f, onError, version);
  const r = consulta.data;
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Materias totales</h3>
      <p className="text-xs text-slate-500">
        Fuente: base única de planes de la institución · Se muestran solo materias que actualmente pertenecen a un plan.
      </p>
      <div className="grid gap-4 md:grid-cols-4">
        <EscuelaFiltro label="Unidad académica" escuelas={data.escuelas} value={f.escuela}
          onChange={(v) => set({ escuela: v, carrera_id: null })} />
        <Field label="Carrera / plan">
          <select
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={f.carrera_id ?? ""}
            onChange={(e) => set({ carrera_id: e.target.value === "" ? null : Number(e.target.value) })}
          >
            {(r?.opciones_carrera ?? [{ etiqueta: "Todas", id: null }]).map((o) => (
              <option key={o.etiqueta} value={o.id ?? ""}>
                {o.etiqueta}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Cuatrimestre">
          <Select value={f.cuatrimestre} options={["Todos", ...c.cuatrimestres]} onChange={(v) => set({ cuatrimestre: v })} />
        </Field>
        <Field label="Estado">
          <Select value={f.estado} options={["Todos", ...c.estados_materia]} onChange={(v) => set({ estado: v })} />
        </Field>
      </div>
      <Field label="Buscar por código o nombre">
        <TextInput value={f.busqueda} onChange={(v) => set({ busqueda: v })}
          placeholder="Escribí parte del código o de la asignatura. Ej.: 01-1, 011, Taller" />
      </Field>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {r && (r.materias.length === 0 ? (
        <FeedbackBox
          feedback={{
            tone: "info",
            text: `No hay materias que coincidan con los filtros seleccionados. Materias vigentes en planes antes de filtrar: ${r.total_base}.`,
          }}
        />
      ) : (
        <>
          <DataTable rows={r.materias} columns={colsAuto(r.materias)} rowKey={(m) => String(m.id)} />
          <p className="text-xs text-slate-500">
            Total materias mostradas: {r.materias.length} | Total de apariciones vigentes en planes: {r.total_base}
          </p>
        </>
      ))}
      {r && f.carrera_id !== null && r.archivadas.length > 0 && data.permisos.puede_borrar && (
        <Limpiar key={r.archivadas_huella} carreraId={f.carrera_id} archivadas={r.archivadas}
          huella={r.archivadas_huella ?? ""} onDone={async (fb) => {
            setVersion((v) => v + 1);
            await onDone(fb);
          }} onError={onError} />
      )}
      {r && f.carrera_id === null && r.hay_fuera_plan && (
        <p className="text-xs text-slate-500">
          Para limpiar físicamente registros viejos, seleccioná una carrera concreta en el filtro Carrera / plan.
        </p>
      )}
    </section>
  );
}

function Limpiar({
  carreraId,
  archivadas,
  huella,
  onDone,
  onError,
}: {
  carreraId: number;
  archivadas: Row[];
  huella: string;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensajes, setMensajes] = useState<{ tono: string; texto: string }[]>([]);

  async function limpiar() {
    setError(null);
    if (!confirmar) return setError("Primero confirmá la limpieza.");
    setBusy(true);
    try {
      const r = await post<{ mensajes: { tono: string; texto: string }[] }>("totales/limpiar", {
        carrera_id: carreraId,
        confirmar,
        huella,
      });
      setMensajes(r.mensajes);
      await onDone({ tone: "success", text: r.mensajes.map((m) => m.texto).join(" ") });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="Limpiar registros que ya no pertenecen a este plan">
      <p className="text-xs text-slate-500">
        Estos registros ya no se muestran en Materias totales. Podés borrar físicamente los que no estén vinculados a
        ninguna comisión. Los que sostienen historia se conservarán internamente, pero seguirán fuera del plan y fuera
        de esta vista.
      </p>
      <DataTable rows={archivadas} columns={colsAuto(archivadas)} rowKey={(m) => String(m.id)} maxHeight="max-h-48" />
      <p className="text-xs text-slate-500">Registros fuera del plan detectados: {archivadas.length}</p>
      <Check checked={confirmar} onChange={setConfirmar} disabled={busy}
        label="Confirmo que quiero limpiar los registros fuera de este plan que no tengan comisiones asociadas" />
      {mensajes.map((m, i) => (
        <FeedbackBox key={i} feedback={{ tone: m.tono === "success" ? "success" : "info", text: m.texto }} />
      ))}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <PrimaryButton onClick={limpiar} busy={busy}>
        Limpiar registros fuera del plan
      </PrimaryButton>
    </Details>
  );
}

// ---------------------------------------------------------------------------------------------- Materias únicas
export function UnicasTab({ data, onError }: TabProps) {
  const c = data.catalogos;
  const [f, setF] = useState({ escuela: "Todas", cuatrimestre: "Todos", estado: "Todos", busqueda: "" });
  const consulta = useConsulta<{ materias: Row[]; total_fuente: number }>("unicas", f, onError);
  const r = consulta.data;
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const apariciones = (r?.materias ?? []).reduce((acc, m) => acc + (Number(m.apariciones_en_planes) || 0), 0);
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Materias únicas</h3>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Esta vista consolida materias repetidas por código y nombre. Si una misma materia aparece en varias " +
            "carreras, se muestra una sola vez y la columna de carreras indica en qué planes aparece. Materias totales " +
            "queda sin cambios para revisar el detalle carrera por carrera. En Optativas/Electivas esta consolidación " +
            "representa el espacio formal del plan; las materias concretas ofrecidas y sus carreras habilitadas se " +
            "administran en la pestaña Optativas / Electivas.",
        }}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <EscuelaFiltro label="Unidad académica" escuelas={data.escuelas} value={f.escuela} onChange={(v) => set({ escuela: v })} />
        <Field label="Cuatrimestre">
          <Select value={f.cuatrimestre} options={["Todos", ...c.cuatrimestres]} onChange={(v) => set({ cuatrimestre: v })} />
        </Field>
        <Field label="Estado">
          <Select value={f.estado} options={["Todos", ...c.estados_materia]} onChange={(v) => set({ estado: v })} />
        </Field>
      </div>
      <Field label="Buscar por código o nombre">
        <TextInput value={f.busqueda} onChange={(v) => set({ busqueda: v })}
          placeholder="Escribí parte del código o de la asignatura. Ej.: 01-1, 011, Taller" />
      </Field>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {r && (r.materias.length === 0 ? (
        <FeedbackBox
          feedback={{
            tone: "info",
            text: `No hay materias únicas que coincidan con los filtros o con la búsqueda ingresada. Materias cargadas en la fuente única antes de filtrar: ${r.total_fuente}.`,
          }}
        />
      ) : (
        <>
          <DataTable rows={r.materias} columns={colsAuto(r.materias)} rowKey={(_, i) => String(i)} />
          <p className="text-xs text-slate-500">
            Total materias únicas mostradas: {r.materias.length} | Apariciones en planes filtrados: {apariciones}
          </p>
        </>
      ))}
    </section>
  );
}
