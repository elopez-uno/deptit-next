"use client";

// Submódulo 3 · Optativas / Electivas (pestaña certificada "🧩 Optativas / Electivas", entry l. 69763-70013).
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
import { type Row, type WriteResult, download, fileToBase64, materiasApi, pick, post } from "@/lib/materias";
import { etiquetaColumna } from "@/lib/unidades-academicas";

const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const colsAuto = (rows: Row[]) => Object.keys(rows[0] ?? {}).map((k) => ({ key: k, label: etiquetaColumna(k) }));
const OPCION_COLS = [
  ["tipo", "Tipo"], ["codigo", "Código"], ["nombre", "Opción concreta"], ["escuela_oferente", "Unidad académica oferente"],
  ["estado", "Estado"], ["cantidad_habilitaciones", "Habilitaciones"], ["carreras_habilitadas", "Carreras"],
  ["espacios_plan", "Espacios de plan"],
].map(([key, label]) => ({ key, label }));
const ESPACIO_COLS = [
  ["codigo", "Código"], ["asignatura", "Espacio"], ["carrera", "Carrera"], ["escuela", "Unidad académica"],
  ["plan_version", "Plan"], ["anio", "Año"], ["cuatrimestre", "Cuatrimestre"],
].map(([key, label]) => ({ key, label }));

type OpcionForm = { tipo: string; codigo: string; nombre: string; escuela_oferente: string; estado: string;
  observaciones: string };

export function OptativasTab({ data, onDone, onError }: TabProps) {
  const c = data.catalogos;
  const [version, setVersion] = useState(0);
  const after = async (f: Parameters<TabProps["onDone"]>[0]) => {
    setVersion((v) => v + 1);
    await onDone(f);
  };
  return (
    <section className="space-y-8">
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-brand-950">Optativas / Electivas · opciones concretas</h3>
        <FeedbackBox
          feedback={{
            tone: "info",
            text:
              "El Plan de Estudios conserva los espacios formales (por ejemplo, Optativa I, Optativa II o Electiva). " +
              "Acá se registran las materias concretas que pueden satisfacer esos espacios. Una misma opción puede " +
              "habilitarse para varios espacios/carreras; esa habilitación indica dónde PUEDE ofrecerse. Al abrir una " +
              "comisión, la opción queda vinculada únicamente al código/espacio formal seleccionado, y los demás " +
              "espacios se abren por separado.",
          }}
        />
        <p className="text-xs text-slate-500">
          Las Optativas pertenecen a los planes de las carreras. Las Electivas además registran la unidad
          académica oferente. Las habilitaciones que cambies acá afectan solo a futuras comisiones; las ya abiertas conservan su
          composición histórica.
        </p>
      </div>
      {data.permisos.puede_escribir ? (
        <>
          <AltaOpcion data={data} onDone={after} onError={onError} />
          <ExcelOpciones data={data} onDone={after} onError={onError} />
        </>
      ) : (
        <ReadOnlyNote />
      )}
      <Administrar data={data} onDone={after} onError={onError} version={version} tipos={c.tipos_opcion}
        estados={c.estados_opcion} />
    </section>
  );
}

function OpcionFields({ form, set, data, disabled }: { form: OpcionForm; set: (p: Partial<OpcionForm>) => void;
  data: TabProps["data"]; disabled?: boolean }) {
  const c = data.catalogos;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="space-y-4">
        <Field label="Tipo">
          <Select value={form.tipo} options={c.tipos_opcion} onChange={(v) => set({ tipo: v })} disabled={disabled} />
        </Field>
        <Field label="Código de la opción (opcional)">
          <TextInput value={form.codigo} onChange={(v) => set({ codigo: v })} disabled={disabled} />
        </Field>
      </div>
      <div className="space-y-4">
        <Field label="Materia concreta que se ofrece">
          <TextInput value={form.nombre} onChange={(v) => set({ nombre: v })} disabled={disabled}
            placeholder="Ej.: El Gobierno y Gestión Local" />
        </Field>
        <Field label="Estado">
          <Select value={form.estado} options={c.estados_opcion} onChange={(v) => set({ estado: v })} disabled={disabled} />
        </Field>
      </div>
      <div className="space-y-4">
        <EscuelaSelector
          label={"Unidad académica oferente" + (form.tipo === "Electiva" ? " *" : " (opcional)")}
          escuelas={data.escuelas}
          value={form.escuela_oferente}
          onChange={(v) => set({ escuela_oferente: v })}
          disabled={disabled}
        />
        <Field label="Observaciones">
          <Textarea value={form.observaciones} onChange={(v) => set({ observaciones: v })} disabled={disabled} />
        </Field>
      </div>
    </div>
  );
}

function AltaOpcion({ data, onDone, onError }: TabProps) {
  const c = data.catalogos;
  const vacio = (): OpcionForm => ({ tipo: c.tipos_opcion[0], codigo: "", nombre: "", escuela_oferente: "",
    estado: c.estados_opcion[0], observaciones: "" });
  const [form, setForm] = useState<OpcionForm>(vacio);
  const accion = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <h4 className="text-base font-semibold text-brand-950">Registrar opción curricular</h4>
      <Card>
        <OpcionFields form={form} set={(p) => setForm((f) => ({ ...f, ...p }))} data={data} disabled={accion.busy} />
        {accion.error && <p className="text-sm text-red-600">{accion.error}</p>}
        <PrimaryButton
          busy={accion.busy}
          onClick={async () => {
            const r = await accion.run(() => post<WriteResult>("opciones/alta", form));
            if (r) setForm(vacio());
          }}
        >
          Registrar opción curricular
        </PrimaryButton>
      </Card>
    </div>
  );
}

function ExcelOpciones({ onDone, onError }: TabProps) {
  const [archivo, setArchivo] = useState<{ nombre: string; b64: string } | null>(null);
  const [preview, setPreview] = useState<{ filas: Row[]; aviso: string | null } | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<Row[]>([]);

  async function bajar() {
    setError(null);
    try {
      download(await materiasApi.modeloExcel(), "modelo_carga_rapida_opciones_curriculares.xlsx");
    } catch (e) {
      setError(onError(e).message);
    }
  }

  async function elegir(file: File | undefined) {
    setPreview(null);
    setDetalle([]);
    setConfirmar(false);
    setError(null);
    if (!file) return setArchivo(null);
    if (!file.name.toLowerCase().endsWith(".xlsx") || file.size > 10 * 1024 * 1024) {
      setArchivo(null);
      return setError("El archivo debe ser un Excel .xlsx válido (hasta 10 MB).");
    }
    setBusy(true);
    try {
      const b64 = await fileToBase64(file);
      setArchivo({ nombre: file.name, b64 });
      setPreview(await post("opciones/excel/previsualizar", { contenido_b64: b64 }));
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  async function procesar() {
    if (!archivo) return;
    setBusy(true);
    setError(null);
    try {
      const r = await post<WriteResult>("opciones/excel/cargar", { contenido_b64: archivo.b64, confirmar });
      setDetalle(r.detalle ?? []);
      await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="Carga rápida de opciones curriculares desde Excel">
      <p className="text-xs text-slate-500">
        El modelo permite registrar varias opciones de una vez y definir sus habilitaciones. Tipo, Estado,
        Unidad académica oferente y cada Habilitación tienen listas desplegables; las listas de habilitación se filtran
        entre Optativa y Electiva según el Tipo de cada fila.
      </p>
      <PrimaryButton tone="secondary" onClick={bajar}>
        Descargar Excel modelo de opciones curriculares
      </PrimaryButton>
      <Field label="Subir Excel completo" hint="Usá preferentemente el modelo descargable de esta misma pestaña.">
        <input
          type="file"
          accept=".xlsx"
          disabled={busy}
          onChange={(e) => elegir(e.target.files?.[0])}
          className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-800"
        />
      </Field>
      {preview?.aviso && <FeedbackBox feedback={{ tone: "info", text: preview.aviso }} />}
      {preview && preview.filas.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-700">Vista previa de la carga</p>
          <DataTable rows={preview.filas} columns={colsAuto(preview.filas)} rowKey={(_, i) => String(i)} maxHeight="max-h-72" />
          <p className="text-xs text-slate-500">Filas a procesar: {preview.filas.length}</p>
          <Check checked={confirmar} onChange={setConfirmar} disabled={busy}
            label="Confirmo que quiero registrar estas opciones y habilitaciones" />
          <PrimaryButton onClick={procesar} busy={busy} disabled={!confirmar}>
            Procesar carga rápida de opciones
          </PrimaryButton>
        </div>
      )}
      {detalle.length > 0 && <DataTable rows={detalle} columns={colsAuto(detalle)} rowKey={(_, i) => String(i)} maxHeight="max-h-60" />}
      {error && <p className="whitespace-pre-line text-sm text-red-600">{error}</p>}
    </Details>
  );
}

function Administrar({ data, onDone, onError, version, tipos, estados }: TabProps & { version: number; tipos: string[];
  estados: string[] }) {
  const [f, setF] = useState({ tipo: "Todos", estado: "Todos", buscar: "" });
  const [sel, setSel] = useState<number | null>(null);
  const consulta = useConsulta<{ opciones: Row[] }>("opciones/consulta", f, onError, version);
  const ops = consulta.data?.opciones ?? [];
  const fila = ops.find((o) => Number(o.id) === sel) ?? ops[0] ?? null;
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  return (
    <div className="space-y-4">
      <h4 className="text-base font-semibold text-brand-950">Administrar opciones y habilitaciones</h4>
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Tipo">
          <Select value={f.tipo} options={["Todos", ...tipos]} onChange={(v) => set({ tipo: v })} />
        </Field>
        <Field label="Estado">
          <Select value={f.estado} options={["Todos", ...estados]} onChange={(v) => set({ estado: v })} />
        </Field>
        <Field label="Buscar opción">
          <TextInput value={f.buscar} onChange={(v) => set({ buscar: v })} placeholder="Nombre, código o unidad académica oferente" />
        </Field>
      </div>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {consulta.data && ops.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: "No hay opciones curriculares que coincidan con los filtros." }} />
      ) : (
        fila && (
          <>
            <p className="text-sm font-medium text-slate-700">Opciones curriculares encontradas</p>
            <DataTable rows={ops} columns={OPCION_COLS} rowKey={(o) => String(o.id)} selected={String(fila.id)}
              onSelect={(k) => setSel(Number(k))} maxHeight="max-h-72" />
            <OpcionSeleccionada key={`${fila.id}|${fila.huella}`} data={data} fila={fila} version={version} onDone={onDone}
              onError={onError} />
          </>
        )
      )}
    </div>
  );
}

function OpcionSeleccionada({ data, fila, version, onDone, onError }: TabProps & { fila: Row; version: number }) {
  const c = data.catalogos;
  const [form, setForm] = useState<OpcionForm>({
    tipo: pick(c.tipos_opcion, txt(fila.tipo) || "Optativa"),
    codigo: txt(fila.codigo),
    nombre: txt(fila.nombre),
    escuela_oferente: txt(fila.escuela_oferente),
    estado: pick(c.estados_opcion, txt(fila.estado) || "Activa"),
    observaciones: txt(fila.observaciones),
  });
  const guardar = useAccion(onDone, onError);
  const borrar = useAccion(onDone, onError);
  const [confirmar, setConfirmar] = useState(false);
  const base = { id: fila.id, huella: fila.huella };
  return (
    <div className="space-y-5">
      <h5 className="font-semibold text-slate-800">Datos de la opción seleccionada</h5>
      {data.permisos.puede_escribir ? (
        <Card>
          <OpcionFields form={form} set={(p) => setForm((s) => ({ ...s, ...p }))} data={data} disabled={guardar.busy} />
          {guardar.error && <p className="text-sm text-red-600">{guardar.error}</p>}
          <div className="flex flex-wrap items-start gap-6">
            <PrimaryButton busy={guardar.busy}
              onClick={() => guardar.run(() => post<WriteResult>("opciones/editar", { ...form, ...base }))}>
              Guardar datos de la opción
            </PrimaryButton>
            {data.permisos.puede_borrar && (
              <div className="space-y-2">
                <Check checked={confirmar} onChange={setConfirmar} disabled={borrar.busy} label="Confirmo eliminación definitiva" />
                <PrimaryButton tone="danger" busy={borrar.busy} onClick={() => {
                  borrar.setError(null);
                  if (!confirmar) return borrar.setError("Primero confirmá la eliminación.");
                  return borrar.run(() => post<WriteResult>("opciones/eliminar", { ...base, confirmar }));
                }}>
                  Eliminar opción
                </PrimaryButton>
                {borrar.error && <p className="text-sm text-red-600">{borrar.error}</p>}
              </div>
            )}
          </div>
        </Card>
      ) : (
        <ReadOnlyNote />
      )}
      <Habilitaciones data={data} fila={fila} tipo={form.tipo} version={version} onDone={onDone} onError={onError} />
    </div>
  );
}

function Habilitaciones({ data, fila, tipo, version, onDone, onError }: TabProps & { fila: Row; tipo: string;
  version: number }) {
  const [f, setF] = useState({ filtro_escuela: "Todas", filtro_carrera: "", filtro_espacio: "" });
  const consulta = useConsulta<{ vinculos: Row[]; espacios: Row[] }>("opciones/habilitaciones",
    { id: fila.id, tipo, ...f }, onError, version);
  const [quitarSel, setQuitarSel] = useState<string | null>(null);
  const [agregar, setAgregar] = useState<number[]>([]);
  const accion = useAccion(onDone, onError);
  const r = consulta.data;
  const nombre = txt(fila.nombre).trim() || `ID ${fila.id}`;
  const base = { id: fila.id, huella: fila.huella };
  const vinc = r?.vinculos ?? [];
  const filaQuitar = vinc.find((v) => String(v.vinculo_id) === quitarSel) ?? null;
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));

  return (
    <div className="space-y-5">
      <h5 className="font-semibold text-slate-800">Espacios habilitados para: {nombre}</h5>
      {consulta.error && <FeedbackBox feedback={{ tone: "error", text: consulta.error }} />}
      {r && vinc.length === 0 && (
        <FeedbackBox feedback={{ tone: "warning", text: "Esta opción todavía no está habilitada para ningún espacio de un plan." }} />
      )}
      {vinc.length > 0 && (
        <>
          <p className="text-xs text-slate-500">
            {vinc.length} {vinc.length === 1 ? "habilitación" : "habilitaciones"} {vinc.length === 1 ? "actual" : "actuales"}.
            Seleccioná una fila solamente si necesitás quitarla.
          </p>
          <p className="text-sm font-medium text-slate-700">Habilitaciones actuales</p>
          <DataTable rows={vinc} columns={ESPACIO_COLS} rowKey={(v) => String(v.vinculo_id)} selected={quitarSel}
            onSelect={data.permisos.puede_borrar ? setQuitarSel : undefined} maxHeight="max-h-60" />
          {filaQuitar && data.permisos.puede_borrar && (
            <PrimaryButton tone="secondary" busy={accion.busy} onClick={async () => {
              const res = await accion.run(() =>
                post<WriteResult>("opciones/habilitaciones/quitar", { ...base, materia_id: filaQuitar.materia_id }));
              if (res) setQuitarSel(null);
            }}>
              Quitar habilitación seleccionada
            </PrimaryButton>
          )}
        </>
      )}
      {data.permisos.puede_escribir && (
        <div className="space-y-3">
          <h5 className="font-semibold text-slate-800">Agregar habilitaciones</h5>
          <p className="text-xs text-slate-500">
            Marcá todos los espacios de los planes para los cuales esta opción es válida. Pueden ser distintas carreras e
            incluso Optativa I en una carrera y Optativa II en otra.
          </p>
          <div className="grid gap-4 md:grid-cols-3">
            <EscuelaFiltro label="Unidad académica destino" escuelas={data.escuelas} value={f.filtro_escuela}
              onChange={(v) => set({ filtro_escuela: v })} />
            <Field label="Filtrar carrera">
              <TextInput value={f.filtro_carrera} onChange={(v) => set({ filtro_carrera: v })} />
            </Field>
            <Field label="Filtrar espacio/código">
              <TextInput value={f.filtro_espacio} onChange={(v) => set({ filtro_espacio: v })} />
            </Field>
          </div>
          {r && r.espacios.length === 0 ? (
            <FeedbackBox feedback={{ tone: "info", text: "No hay otros espacios compatibles que coincidan con los filtros." }} />
          ) : (
            r && (
              <>
                <p className="text-sm font-medium text-slate-700">Espacios disponibles</p>
                <div className="max-h-72 overflow-auto rounded-xl border border-slate-200 bg-white p-3">
                  {r.espacios.map((e) => (
                    <Check
                      key={String(e.materia_id)}
                      checked={agregar.includes(Number(e.materia_id))}
                      onChange={(v) =>
                        setAgregar((s) => (v ? [...s, Number(e.materia_id)] : s.filter((x) => x !== Number(e.materia_id))))
                      }
                      label={`${txt(e.codigo)} - ${txt(e.asignatura)} · ${txt(e.carrera)} · ${txt(e.escuela)} · ${txt(e.plan_version)} · ${txt(e.anio)} · C${txt(e.cuatrimestre)}`}
                    />
                  ))}
                </div>
                <PrimaryButton busy={accion.busy} onClick={async () => {
                  accion.setError(null);
                  if (agregar.length === 0) return accion.setError("Marcá al menos un espacio del plan.");
                  const res = await accion.run(() =>
                    post<WriteResult>("opciones/habilitaciones/agregar", { ...base, materia_ids: agregar }));
                  if (res) setAgregar([]);
                }}>
                  Agregar espacios seleccionados
                </PrimaryButton>
              </>
            )
          )}
        </div>
      )}
      {accion.error && <p className="text-sm text-red-600">{accion.error}</p>}
    </div>
  );
}
