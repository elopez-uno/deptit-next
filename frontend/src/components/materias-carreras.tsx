"use client";

// Submódulo 1 · Carreras / Planes (pestaña certificada "🏫 Facultades/Escuelas y carreras", entry l. 68581-68789).
import { useState } from "react";
import {
  Card,
  Check,
  DataTable,
  Details,
  EmptyState,
  FeedbackBox,
  Field,
  PrimaryButton,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import {
  EscuelaFiltro,
  EscuelaSelector,
  ReadOnlyNote,
  type TabProps,
  useAccion,
  useConsulta,
} from "@/components/materias-shared";
import { type Carrera, type Row, type WriteResult, pick, post } from "@/lib/materias";
import { etiquetaColumna } from "@/lib/unidades-academicas";

type CarreraForm = {
  escuela: string;
  codigo: string;
  nombre: string;
  titulo_otorga: string;
  plan_version: string;
  duracion: string;
  estado: string;
  observaciones: string;
};

const LISTADO_COLS = ["escuela", "codigo", "nombre", "titulo_otorga", "plan_version", "duracion", "estado",
  "observaciones"].map((k) => ({ key: k, label: etiquetaColumna(k) }));
const EDIT_COLS = [
  { key: "codigo", label: "Código" },
  { key: "nombre", label: "Carrera" },
  { key: "escuela", label: "Unidad académica" },
  { key: "plan_version", label: "Plan" },
  { key: "titulo_otorga", label: "Título" },
  { key: "duracion", label: "Duración" },
  { key: "estado", label: "Estado" },
] as const;

function CarreraFields({
  form,
  set,
  escuelas,
  estados,
  disabled,
}: {
  form: CarreraForm;
  set: (p: Partial<CarreraForm>) => void;
  escuelas: string[];
  estados: string[];
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-4">
        <EscuelaSelector
          label="Unidad académica"
          escuelas={escuelas}
          value={form.escuela}
          onChange={(v) => set({ escuela: v })}
          disabled={disabled}
        />
        <Field label="Código de carrera">
          <TextInput value={form.codigo} onChange={(v) => set({ codigo: v })} disabled={disabled} />
        </Field>
        <Field label="Nombre de la carrera">
          <TextInput value={form.nombre} onChange={(v) => set({ nombre: v })} disabled={disabled} />
        </Field>
        <Field label="Título que otorga">
          <TextInput value={form.titulo_otorga} onChange={(v) => set({ titulo_otorga: v })} disabled={disabled} />
        </Field>
      </div>
      <div className="space-y-4">
        <Field label="Plan / versión">
          <TextInput value={form.plan_version} onChange={(v) => set({ plan_version: v })} disabled={disabled} />
        </Field>
        <Field label="Duración de la carrera">
          <TextInput value={form.duracion} onChange={(v) => set({ duracion: v })} disabled={disabled} />
        </Field>
        <Field label="Estado">
          <Select value={form.estado} options={estados} onChange={(v) => set({ estado: v })} disabled={disabled} />
        </Field>
        <Field label="Observaciones">
          <Textarea value={form.observaciones} onChange={(v) => set({ observaciones: v })} disabled={disabled} />
        </Field>
      </div>
    </div>
  );
}

function useDuplicadas(form: CarreraForm, onError: TabProps["onError"], excluir?: number) {
  const habilitado = Boolean(form.escuela && form.nombre && form.plan_version);
  const { data } = useConsulta<{ duplicadas: Row[] }>(
    "carreras/duplicado",
    { ...form, excluir_id: excluir ?? null },
    onError,
    0,
    habilitado
  );
  return habilitado ? (data?.duplicadas ?? []) : [];
}

export function CarrerasTab({ data, onDone, onError }: TabProps) {
  const estados = data.catalogos.estados_carrera;
  const vacio = (): CarreraForm => ({
    escuela: "",
    codigo: "",
    nombre: "",
    titulo_otorga: "",
    plan_version: data.catalogos.plan_vigente,
    duracion: "",
    estado: estados[0],
    observaciones: "",
  });
  const [alta, setAlta] = useState<CarreraForm>(vacio);
  const dupAlta = useDuplicadas(alta, onError);
  const accionAlta = useAccion(onDone, onError);
  const [filtroEscuela, setFiltroEscuela] = useState("Todas");
  const [filtroEstado, setFiltroEstado] = useState("Todos");
  const [busqueda, setBusqueda] = useState("");
  const [version, setVersion] = useState(0);
  const consulta = useConsulta<{ listado: Row[]; edicion: Carrera[] }>(
    "carreras/consulta",
    { escuela: filtroEscuela, estado: filtroEstado, busqueda },
    onError,
    version + data.carreras.length
  );
  const [sel, setSel] = useState<number | null>(null);

  async function guardarAlta() {
    accionAlta.setError(null);
    if (!(alta.escuela && alta.nombre && alta.plan_version)) {
      accionAlta.setError("Completá al menos Unidad académica, Nombre de la carrera y Plan / versión.");
      return;
    }
    if (dupAlta.length) {
      accionAlta.setError(
        "No se guardó la carrera porque ya existe una carrera / plan con esos mismos datos. Editá la carrera " +
          "existente o cambiá los datos si realmente es otro plan."
      );
      return;
    }
    const r = await accionAlta.run(() => post<WriteResult>("carreras/alta", alta));
    if (r) {
      setAlta(vacio());
      setVersion((v) => v + 1);
    }
  }

  const edicion = consulta.data?.edicion ?? [];
  const fila = edicion.find((c) => c.id === sel) ?? edicion[0] ?? null;

  return (
    <section className="space-y-8">
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-brand-950">Registrar nueva carrera / plan</h3>
        {!data.permisos.puede_escribir ? (
          <ReadOnlyNote />
        ) : (
          <Card>
            <CarreraFields
              form={alta}
              set={(p) => setAlta((f) => ({ ...f, ...p }))}
              escuelas={data.escuelas}
              estados={estados}
              disabled={accionAlta.busy}
            />
            {dupAlta.length > 0 && (
              <>
                <FeedbackBox
                  feedback={{
                    tone: "warning",
                    text:
                      "Esta carrera / plan ya está cargada en el sistema. Si apretás guardar, estarías generando una " +
                      "carrera duplicada.",
                  }}
                />
                <DataTable rows={dupAlta} columns={LISTADO_COLS} rowKey={(_, i) => String(i)} maxHeight="max-h-48" />
              </>
            )}
            {accionAlta.error && <p className="text-sm text-red-600">{accionAlta.error}</p>}
            <PrimaryButton onClick={guardarAlta} busy={accionAlta.busy}>
              Guardar carrera
            </PrimaryButton>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-brand-950">Carreras registradas</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <EscuelaFiltro
            label="Filtrar por unidad académica"
            escuelas={data.escuelas}
            value={filtroEscuela}
            onChange={setFiltroEscuela}
          />
          <Field label="Filtrar por estado">
            <Select value={filtroEstado} options={["Todos", ...estados]} onChange={setFiltroEstado} />
          </Field>
        </div>
        {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
        {consulta.data && consulta.data.listado.length === 0 ? (
          <EmptyState text="Todavía no hay carreras registradas." />
        ) : (
          consulta.data && (
            <>
              <DataTable rows={consulta.data.listado} columns={LISTADO_COLS} rowKey={(_, i) => String(i)} />
              <p className="text-xs text-slate-500">Total carreras / planes: {consulta.data.listado.length}</p>
            </>
          )
        )}
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar carrera</h3>
        {data.carreras.length === 0 ? (
          <EmptyState text="No hay carreras para editar." />
        ) : (
          <>
            <p className="text-xs text-slate-500">
              Buscá la carrera o plan ya creado y editá sus datos. Si cambiás la unidad académica, también se
              actualizan las materias vinculadas a ese plan.
            </p>
            <Field label="Buscar carrera / plan para editar">
              <TextInput
                value={busqueda}
                onChange={setBusqueda}
                placeholder="Buscar por nombre, código, unidad académica, plan o título"
              />
            </Field>
            {consulta.data && edicion.length === 0 ? (
              <FeedbackBox feedback={{ tone: "warning", text: "No encontré carreras/planes con esa búsqueda." }} />
            ) : (
              fila && (
                <>
                  <p className="text-sm font-medium text-slate-700">Carreras / planes encontrados</p>
                  <DataTable
                    rows={edicion}
                    columns={[...EDIT_COLS]}
                    rowKey={(r) => String(r.id)}
                    selected={String(fila.id)}
                    onSelect={(k) => setSel(Number(k))}
                    maxHeight="max-h-72"
                  />
                  <EditarCarrera
                    key={`${fila.id}|${fila.huella}`}
                    data={data}
                    fila={fila}
                    onDone={async (f) => {
                      setVersion((v) => v + 1);
                      await onDone(f);
                    }}
                    onError={onError}
                  />
                </>
              )
            )}
          </>
        )}
      </div>
    </section>
  );
}

function EditarCarrera({ data, fila, onDone, onError }: TabProps & { fila: Carrera }) {
  const estados = data.catalogos.estados_carrera;
  const [form, setForm] = useState<CarreraForm>({
    escuela: fila.escuela ?? "",
    codigo: fila.codigo ?? "",
    nombre: fila.nombre ?? "",
    titulo_otorga: fila.titulo_otorga ?? "",
    plan_version: fila.plan_version ?? "",
    duracion: fila.duracion ?? "",
    estado: pick(estados, fila.estado || "Activa"),
    observaciones: fila.observaciones ?? "",
  });
  const dup = useDuplicadas(form, onError, fila.id);
  const guardar = useAccion(onDone, onError);
  const borrar = useAccion(onDone, onError);
  const [conMaterias, setConMaterias] = useState(false);
  const [confirmar, setConfirmar] = useState(false);

  async function submit() {
    guardar.setError(null);
    if (!form.escuela || !form.nombre || !form.plan_version) {
      guardar.setError("Completá al menos Unidad académica, Nombre de la carrera y Plan / versión.");
      return;
    }
    if (dup.length) {
      guardar.setError("No se actualizaron los datos porque ya existe otra carrera / plan con esos mismos datos.");
      return;
    }
    await guardar.run(() => post<WriteResult>("carreras/editar", { ...form, carrera_id: fila.id, huella: fila.huella }));
  }

  async function eliminar() {
    borrar.setError(null);
    if (!confirmar) {
      borrar.setError("Primero confirmá la eliminación.");
      return;
    }
    await borrar.run(() =>
      post<WriteResult>("carreras/eliminar", {
        carrera_id: fila.id,
        huella: fila.huella,
        confirmar,
        eliminar_materias: conMaterias,
      })
    );
  }

  return (
    <div className="space-y-4">
      <Details summary="Datos actuales de la carrera / plan seleccionado" defaultOpen>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {(["id", "escuela", "codigo", "nombre", "titulo_otorga", "plan_version", "duracion", "estado",
            "observaciones"] as const).map((k) => (
            <div key={k} className="min-w-0">
              <dt className="text-xs text-slate-400">{k}</dt>
              <dd className="truncate text-slate-800">{fila[k] === null || fila[k] === "" ? "-" : String(fila[k])}</dd>
            </div>
          ))}
        </dl>
      </Details>
      {!data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : (
        <>
          <Card>
            <CarreraFields
              form={form}
              set={(p) => setForm((f) => ({ ...f, ...p }))}
              escuelas={data.escuelas}
              estados={estados}
              disabled={guardar.busy}
            />
            {dup.length > 0 && (
              <>
                <FeedbackBox
                  feedback={{
                    tone: "warning",
                    text:
                      "Los datos editados coinciden con otra carrera / plan ya cargada. Si guardaras esto, quedarían " +
                      "dos carreras iguales.",
                  }}
                />
                <DataTable rows={dup} columns={LISTADO_COLS} rowKey={(_, i) => String(i)} maxHeight="max-h-48" />
              </>
            )}
            {guardar.error && <p className="text-sm text-red-600">{guardar.error}</p>}
            <PrimaryButton onClick={submit} busy={guardar.busy}>
              Guardar cambios de carrera
            </PrimaryButton>
          </Card>
          {data.permisos.puede_borrar && (
            <Card>
              <h4 className="text-base font-semibold text-brand-950">Eliminar carrera</h4>
              <Check
                checked={conMaterias}
                onChange={setConMaterias}
                disabled={borrar.busy}
                label="Eliminar también las materias de esta carrera"
              />
              <Check
                checked={confirmar}
                onChange={setConfirmar}
                disabled={borrar.busy}
                label="Confirmo que quiero eliminar esta carrera"
              />
              {borrar.error && <p className="text-sm text-red-600">{borrar.error}</p>}
              <PrimaryButton tone="danger" onClick={eliminar} busy={borrar.busy}>
                Eliminar carrera
              </PrimaryButton>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
