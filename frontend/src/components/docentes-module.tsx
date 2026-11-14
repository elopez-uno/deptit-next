"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { CargaIntegral } from "@/components/docentes-carga-integral";
import { DesignacionDesdeRegistro, Reincorporar } from "@/components/docentes-designacion";
import { ResumenDocente } from "@/components/docentes-resumen";
import {
  Card,
  Check,
  type Column,
  DataTable,
  Details,
  EmptyState,
  type Feedback,
  FeedbackBox,
  Field,
  PrimaryButton,
  Radio,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type CargaPreview,
  type Docente,
  type DocenteForm,
  type DocentesOverview,
  type Ficha,
  type Fila,
  type OtroDepartamento,
  type Plantel,
  type Equipos,
  type VerificacionCuil,
  type WriteResult,
  docentesApi,
  filtrarPorTexto,
  limpiarCuil,
  nivelPosgradoNormalizado,
  nombreCompleto,
  today,
} from "@/lib/docentes";
import { etiquetaColumna } from "@/lib/unidades-academicas";

// Módulo Docentes (B13-FIX02, entry l. 59801-61761). Pestañas, textos y confirmaciones del sistema certificado.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
const TABS = [
  { key: "plantel", label: "Plantel del período abierto" },
  { key: "base", label: "Base maestra de docentes" },
  { key: "registrar", label: "Registrar docente" },
  { key: "carga", label: "Carga rápida" },
  { key: "editar", label: "Editar / eliminar docente" },
  { key: "equipos", label: "Equipos docentes" },
  { key: "resumen", label: "Resumen docente" },
] as const;

type TabKey = (typeof TABS)[number]["key"];
type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;

const MODO_NUEVO = "Registrar un docente nuevo en la base maestra";
const MODO_BASE = "Seleccionar un docente de la base maestra y registrar su designación en el período actual";
const ACCION_PROPIO = "Registrar como propio y cargar una designación en el período actual";
const ACCION_PRESTADO = "Tomarlo solamente como prestado para asignarlo a comisiones";

const emptyForm = (): DocenteForm => ({
  apellido: "",
  nombres: "",
  cuil: "",
  legajo: "",
  titulo: "",
  titulo_posgrado: "",
  nivel_posgrado_salarial: "",
  antiguedad_anios: null,
  email: "",
  telefono: "",
  ref_legajo_fisico: "",
  observaciones: "",
});

const nivelLabel = (x: string) => (x ? x : "Sin adicional por posgrado");

export function DocentesModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<DocentesOverview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  // st.tabs certificado: la primera pestaña (Plantel) es la visible al entrar.
  const [tab, setTab] = useState<TabKey>("plantel");
  const [feedback, setFeedback] = useState<Feedback>(null);

  const handle = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) onAuthError(err);
      return err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
    },
    [onAuthError]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await docentesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    docentesApi
      .overview()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(handle(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [handle]);

  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando docentes…
      </div>
    );
  }

  if (loadError && !data) {
    const scope = loadError.code.startsWith("SCOPE");
    return (
      <div
        className={`rounded-2xl border px-6 py-8 text-sm ${
          scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"
        }`}
      >
        <p>{loadError.message}</p>
        {!scope && (
          <button
            onClick={load}
            className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800"
          >
            Reintentar
          </button>
        )}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">
            {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">Módulo Docentes</h2>
        </div>
        {data.abierto ? (
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
            Período abierto: {data.abierto.nombre}
          </span>
        ) : (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700">
            Sin período abierto
          </span>
        )}
      </div>

      <div role="tablist" aria-label="Secciones de Docentes" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => {
              setTab(t.key);
              setFeedback(null);
            }}
            className={`-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2 text-sm transition ${
              tab === t.key
                ? "border-brand-600 font-medium text-brand-800"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {feedback && <FeedbackBox feedback={feedback} />}
      {loadError && data && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}

      <div role="tabpanel">
        {tab === "plantel" && <PlantelPeriodo onError={handle} />}
        {tab === "base" && <BaseMaestra data={data} />}
        {tab === "registrar" && <Registrar data={data} onDone={afterWrite} onError={handle} />}
        {tab === "carga" && <CargaRapida data={data} onDone={afterWrite} onError={handle} />}
        {tab === "editar" && <EditarEliminar data={data} onDone={afterWrite} onError={handle} />}
        {tab === "equipos" && <EquiposDocentes onError={handle} />}
        {tab === "resumen" && <ResumenDocente data={data} onError={handle} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- Plantel (E4-02)
// Pestaña certificada tab1 (entry l. 59813-59925): selector "Seleccioná el período" (por defecto el abierto), aviso,
// st.dataframe de get_plantel_periodo y conteo de docentes activos. El backend decide opciones, plantel y textos.
function Negritas({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return <>{partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}</>;
}

function PlantelPeriodo({ onError }: { onError: OnError }) {
  const [plantel, setPlantel] = useState<Plantel | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    docentesApi
      .plantel(null)
      .then((p) => {
        if (!cancelled) setPlantel(p);
      })
      .catch((err) => {
        if (!cancelled) setError(onError(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [onError]);

  async function elegir(nombre: string) {
    const p = plantel?.periodos.find((x) => x.nombre === nombre);
    if (!p) return;
    setBusy(true);
    try {
      setPlantel(await docentesApi.plantel(p.id));
      setError(null);
    } catch (err) {
      setError(onError(err));
    } finally {
      setBusy(false);
    }
  }

  const filas = useMemo(
    () =>
      (plantel?.tabla?.filas ?? []).map((f) =>
        Object.fromEntries((plantel?.tabla?.columnas ?? []).map((c, i) => [c, f[i]]))
      ) as Record<string, unknown>[],
    [plantel]
  );

  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Plantel por período</h3>
      {error && <FeedbackBox feedback={{ tone: "error", text: error.message }} />}
      {busy && !plantel && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4 text-brand-600" />
          Cargando plantel…
        </p>
      )}
      {plantel?.sin_periodos && <FeedbackBox feedback={{ tone: "warning", text: plantel.sin_periodos }} />}
      {plantel?.seleccionado && (
        <>
          <Field label="Seleccioná el período">
            <Select
              value={plantel.seleccionado.nombre}
              options={plantel.periodos.map((p) => p.nombre)}
              onChange={elegir}
              disabled={busy}
            />
          </Field>
          {plantel.info && (
            <div role="status" className="mb-4 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-800">
              <Negritas text={plantel.info} />
            </div>
          )}
          {plantel.vacio ? (
            <FeedbackBox feedback={{ tone: "info", text: plantel.vacio }} />
          ) : (
            plantel.tabla && (
              <>
                <DataTable
                  rows={filas}
                  columns={plantel.tabla.columnas.map((c) => ({ key: c, label: etiquetaColumna(c) }))}
                  rowKey={(_, i) => String(i)}
                />
                <p className="text-xs text-slate-500">
                  Total docentes activos con designaciones activas en el período seleccionado: {plantel.total_activos}
                </p>
              </>
            )
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- Equipos (E4-03)
// Pestaña certificada tab7 (entry l. 60828-60844): aviso, selector "Seleccioná el período" (por defecto el abierto),
// st.dataframe de get_equipos_docentes_periodo y conteo de materias. Solo lectura; el backend arma la tabla.
function EquiposDocentes({ onError }: { onError: OnError }) {
  const [equipos, setEquipos] = useState<Equipos | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    docentesApi
      .equipos(null)
      .then((e) => {
        if (!cancelled) setEquipos(e);
      })
      .catch((err) => {
        if (!cancelled) setError(onError(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [onError]);

  async function elegir(nombre: string) {
    const p = equipos?.periodos.find((x) => x.nombre === nombre);
    if (!p) return;
    setBusy(true);
    try {
      setEquipos(await docentesApi.equipos(p.id));
      setError(null);
    } catch (err) {
      setError(onError(err));
    } finally {
      setBusy(false);
    }
  }

  const filas = useMemo(
    () =>
      (equipos?.tabla?.filas ?? []).map((f) =>
        Object.fromEntries((equipos?.tabla?.columnas ?? []).map((c, i) => [c, f[i]]))
      ) as Record<string, unknown>[],
    [equipos]
  );

  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Equipos docentes por materia</h3>
      {equipos?.info && <FeedbackBox feedback={{ tone: "info", text: equipos.info }} />}
      {error && <FeedbackBox feedback={{ tone: "error", text: error.message }} />}
      {busy && !equipos && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4 text-brand-600" />
          Cargando equipos docentes…
        </p>
      )}
      {equipos?.sin_periodos && <FeedbackBox feedback={{ tone: "warning", text: equipos.sin_periodos }} />}
      {equipos?.seleccionado && (
        <>
          <Field label="Seleccioná el período">
            <Select
              value={equipos.seleccionado.nombre}
              options={equipos.periodos.map((p) => p.nombre)}
              onChange={elegir}
              disabled={busy}
            />
          </Field>
          {equipos.vacio ? (
            <FeedbackBox feedback={{ tone: "info", text: equipos.vacio }} />
          ) : (
            equipos.tabla && (
              <>
                <DataTable
                  rows={filas}
                  columns={equipos.tabla.columnas.map((c) => ({ key: c, label: etiquetaColumna(c) }))}
                  rowKey={(_, i) => String(i)}
                />
                <p className="text-xs text-slate-500">
                  Total materias con equipo docente registrado: {equipos.total_materias}
                </p>
              </>
            )
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- Base maestra
const BASE_COLUMNS: Column<Docente>[] = [
  { key: "cuil", label: "cuil" },
  { key: "legajo", label: "legajo" },
  { key: "apellido", label: "apellido" },
  { key: "nombres", label: "nombres" },
  { key: "nombre_completo", label: "nombre_completo" },
  { key: "titulo", label: "titulo" },
  { key: "titulo_posgrado", label: "titulo_posgrado" },
  { key: "antiguedad_anios", label: "antiguedad_anios" },
  { key: "nivel_posgrado_salarial", label: "nivel_posgrado_salarial" },
  { key: "email", label: "email" },
  { key: "telefono", label: "telefono" },
  { key: "ref_legajo_fisico", label: "ref_legajo_fisico" },
  { key: "tipo_docente", label: "tipo_docente" },
  { key: "observaciones", label: "observaciones" },
  { key: "fecha_alta", label: "fecha_alta" },
  { key: "fecha_finalizacion", label: "fecha_finalizacion" },
  { key: "estado_periodo_abierto", label: "estado_operativo_periodo_abierto" },
];

function BaseMaestra({ data }: { data: DocentesOverview }) {
  return (
    <section className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Base maestra de docentes</h3>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Acá figuran los docentes cargados como personas en el sistema. Fecha alta se calcula siempre como la " +
            "fecha de inicio más antigua de todas sus designaciones del departamento. Fecha finalización solo " +
            "aparece si ya no integra el plantel del período actual y corresponde a la finalización real más " +
            "reciente hasta hoy. El criterio es el mismo para todos los departamentos y se recalcula " +
            "automáticamente desde las designaciones.",
        }}
      />
      {data.docentes.length === 0 ? (
        <EmptyState text="Todavía no hay docentes registrados." />
      ) : (
        <>
          <DataTable rows={data.docentes} columns={BASE_COLUMNS} rowKey={(r) => r.cuil} />
          <p className="text-xs text-slate-500">Total docentes en base maestra: {data.docentes.length}</p>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- Registrar
function Registrar({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [modo, setModo] = useState(MODO_NUEVO);
  const [tipo, setTipo] = useState("Propio");

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Registrar docente</h3>
      <Field label="¿Qué querés hacer?">
        <Radio name="modo_registro" value={modo} options={[MODO_NUEVO, MODO_BASE]} onChange={setModo} />
      </Field>
      {modo === MODO_BASE ? (
        <Reincorporar version={data} onDone={onDone} onError={onError} />
      ) : !data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : (
        <>
          <div className="max-w-xs">
            <Field
              label="Tipo de docente"
              hint="Elegí Propio si tendrá una designación en este departamento. Elegí Prestado si solo será asignado a comisiones y su designación pertenece a otro departamento."
            >
              <Select value={tipo} options={data.catalogos.tipos} onChange={setTipo} />
            </Field>
          </div>
          {tipo === "Prestado" ? (
            <AltaPrestado data={data} onDone={onDone} onError={onError} />
          ) : (
            <AltaPropio data={data} onDone={onDone} onError={onError} />
          )}
        </>
      )}
    </section>
  );
}

const OTROS_COLUMNS: Column<OtroDepartamento>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "legajo", label: "Legajo" },
  { key: "departamento_origen", label: "Departamento de origen" },
];
const otroKey = (r: OtroDepartamento) => `${r.cuil}|${r.departamento_origen}`;

function AltaPrestado({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [rows, setRows] = useState<OtroDepartamento[] | null>(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    docentesApi
      .prestables()
      .then((r) => !cancelled && setRows(r.docentes))
      .catch((e) => !cancelled && setError(onError(e).message));
    return () => {
      cancelled = true;
    };
  }, [onError]);

  const filtered = useMemo(
    () => filtrarPorTexto(rows ?? [], q, ["nombre_completo", "cuil", "departamento_origen"]),
    [rows, q]
  );
  const chosen = filtered.find((r) => otroKey(r) === sel) ?? filtered[0] ?? null;

  async function submit() {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      const res = await docentesApi.prestado({
        flujo: "selector",
        cuil: chosen.cuil,
        departamento_origen: chosen.departamento_origen,
      });
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Buscá y seleccioná una persona ya registrada en otro departamento. No se muestran campos de carga " +
            "manual porque sus datos se recuperan por CUIL.",
        }}
      />
      {rows === null && !error ? (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Buscando docentes de otros departamentos…
        </p>
      ) : rows !== null && rows.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No encontré docentes activos registrados en otros departamentos." }} />
      ) : rows !== null ? (
        <>
          <Field label="Buscar docente prestado por nombre, apellido, CUIL o departamento">
            <TextInput value={q} onChange={setQ} />
          </Field>
          {filtered.length === 0 ? (
            <FeedbackBox feedback={{ tone: "warning", text: "No hay coincidencias con esa búsqueda." }} />
          ) : (
            <>
              <p className="text-sm font-medium text-slate-700">Docentes encontrados</p>
              <DataTable
                rows={filtered}
                columns={OTROS_COLUMNS}
                rowKey={otroKey}
                selected={chosen ? otroKey(chosen) : null}
                onSelect={setSel}
                maxHeight="max-h-80"
              />
              {chosen && (
                <p className="text-xs text-slate-500">
                  CUIL: {chosen.cuil || "-"} · Legajo: {chosen.legajo || "-"} · Origen:{" "}
                  {chosen.departamento_origen || "-"}
                </p>
              )}
              {!data.abierto && (
                <FeedbackBox feedback={{ tone: "warning", text: "No hay período abierto para registrar el préstamo." }} />
              )}
              <PrimaryButton onClick={submit} busy={busy} disabled={!chosen}>
                Registrar como docente prestado
              </PrimaryButton>
            </>
          )}
        </>
      ) : null}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

function DocenteFields({
  form,
  set,
  data,
  disabled,
  informar,
  setInformar,
  extra,
}: {
  form: DocenteForm;
  set: (patch: Partial<DocenteForm>) => void;
  data: DocentesOverview;
  disabled: boolean;
  informar: boolean;
  setInformar: (v: boolean) => void;
  extra?: React.ReactNode;
}) {
  const { antiguedad_min: min, antiguedad_max: max } = data.catalogos;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-4">
        <Field label="Apellido/s">
          <TextInput value={form.apellido} onChange={(v) => set({ apellido: v })} disabled={disabled} />
        </Field>
        <Field label="Nombre/s">
          <TextInput value={form.nombres} onChange={(v) => set({ nombres: v })} disabled={disabled} />
        </Field>
        <Field label="CUIL">
          <TextInput value={form.cuil} onChange={(v) => set({ cuil: v })} disabled={disabled} />
        </Field>
        <Field label="Legajo">
          <TextInput value={form.legajo} onChange={(v) => set({ legajo: v })} disabled={disabled} />
        </Field>
      </div>
      <div className="space-y-4">
        <Field label="Título de grado">
          <TextInput value={form.titulo} onChange={(v) => set({ titulo: v })} disabled={disabled} />
        </Field>
        <Field label="Título de posgrado">
          <TextInput value={form.titulo_posgrado} onChange={(v) => set({ titulo_posgrado: v })} disabled={disabled} />
        </Field>
        <Field
          label="Nivel de posgrado (adicional salarial)"
          hint="Especialista suma 5%, Magíster 8% y Doctor 18% del básico correspondiente a la dedicación."
        >
          <Select
            value={form.nivel_posgrado_salarial}
            options={data.catalogos.niveles_posgrado}
            label={nivelLabel}
            onChange={(v) => set({ nivel_posgrado_salarial: v })}
            disabled={disabled}
          />
        </Field>
        <Check
          checked={informar}
          onChange={(v) => {
            setInformar(v);
            set({ antiguedad_anios: v ? form.antiguedad_anios ?? 0 : null });
          }}
          disabled={disabled}
          label="Informar años de antigüedad"
        />
        {informar && (
          <Field label="Años de antigüedad">
            <input
              type="number"
              min={min}
              max={max}
              step={1}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.antiguedad_anios ?? 0}
              disabled={disabled}
              onChange={(e) => {
                const n = Math.trunc(Number(e.target.value));
                set({ antiguedad_anios: Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : 0 });
              }}
            />
          </Field>
        )}
        <Field label="Correo electrónico">
          <TextInput value={form.email} onChange={(v) => set({ email: v })} disabled={disabled} />
        </Field>
        <Field label="Teléfono">
          <TextInput value={form.telefono} onChange={(v) => set({ telefono: v })} disabled={disabled} />
        </Field>
        <Field label="Referencia legajo físico">
          <TextInput
            value={form.ref_legajo_fisico}
            onChange={(v) => set({ ref_legajo_fisico: v })}
            disabled={disabled}
          />
        </Field>
        {extra}
      </div>
    </div>
  );
}

function useCuilCheck(cuil: string, onError: OnError, version?: unknown) {
  const [check, setCheck] = useState<VerificacionCuil | null>(null);
  const limpio = limpiarCuil(cuil);
  useEffect(() => {
    let cancelled = false;
    if (!limpio) {
      const t = setTimeout(() => !cancelled && setCheck(null), 0);
      return () => {
        cancelled = true;
        clearTimeout(t);
      };
    }
    const t = setTimeout(() => {
      docentesApi
        .verificarCuil(limpio)
        .then((r) => !cancelled && setCheck(r))
        .catch((e) => {
          if (!cancelled) {
            onError(e);
            setCheck(null);
          }
        });
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [limpio, onError, version]);
  return check && check.cuil_limpio === limpio ? check : null;
}

function AltaPropio({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [form, setForm] = useState<DocenteForm>(emptyForm);
  const [informar, setInformar] = useState(false);
  const [fechaAlta, setFechaAlta] = useState(today());
  const [accion, setAccion] = useState(ACCION_PROPIO);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const check = useCuilCheck(form.cuil, onError, data);
  const set = (patch: Partial<DocenteForm>) => setForm((f) => ({ ...f, ...patch }));
  const nombre = nombreCompleto(form.apellido, form.nombres);

  async function run(fn: () => Promise<WriteResult>, reset: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res = await fn();
      if (reset) {
        setForm(emptyForm());
        setInformar(false);
      }
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  const otros = check?.otros_departamentos ?? [];
  const chosen = otros.find((r) => otroKey(r) === sel) ?? otros[0] ?? null;

  return (
    <Card>
      <DocenteFields
        form={form}
        set={set}
        data={data}
        disabled={busy}
        informar={informar}
        setInformar={setInformar}
        extra={
          <Field label="Fecha de alta del docente">
            <TextInput type="date" value={fechaAlta} onChange={setFechaAlta} disabled={busy} />
          </Field>
        }
      />
      <Field label="Observación">
        <Textarea
          value={form.observaciones}
          onChange={(v) => set({ observaciones: v })}
          disabled={busy}
          placeholder="Dato interno opcional sobre el docente."
        />
      </Field>

      {otros.length > 0 ? (
        <div className="space-y-4">
          <FeedbackBox
            feedback={{
              tone: "warning",
              text:
                "El CUIL ya pertenece a un docente registrado en otro departamento. Seleccioná cómo debe " +
                "incorporarse al departamento actual.",
            }}
          />
          <p className="text-sm font-medium text-slate-700">Coincidencias encontradas</p>
          <DataTable
            rows={otros}
            columns={OTROS_COLUMNS}
            rowKey={otroKey}
            selected={chosen ? otroKey(chosen) : null}
            onSelect={setSel}
            maxHeight="max-h-60"
          />
          <Field label="¿Cómo querés incorporarlo?">
            <Radio name="accion_cuil" value={accion} options={[ACCION_PROPIO, ACCION_PRESTADO]} onChange={setAccion} />
          </Field>
          {accion === ACCION_PRESTADO ? (
            <>
              <FeedbackBox
                feedback={{
                  tone: "info",
                  text: "Se copiarán sus datos personales por CUIL y no se creará una designación local.",
                }}
              />
              <PrimaryButton
                busy={busy}
                disabled={!chosen}
                onClick={() =>
                  chosen &&
                  run(
                    () =>
                      docentesApi.prestado({
                        flujo: "cuil_existente",
                        cuil: chosen.cuil,
                        departamento_origen: chosen.departamento_origen,
                        cuil_alta: form.cuil,
                      }),
                    false
                  )
                }
              >
                Registrar solamente como prestado
              </PrimaryButton>
            </>
          ) : (
            <DesignacionDesdeRegistro
              version={data}
              camino="cuil_existente"
              elegido={chosen}
              cuilAlta={form.cuil}
              onDone={onDone}
              onError={onError}
            />
          )}
        </div>
      ) : check?.local ? (
        <div className="space-y-4">
          <FeedbackBox
            feedback={{
              tone: "warning",
              text: `Este CUIL ya está registrado en el departamento actual como ${check.local.nombre || check.cuil_limpio}.`,
            }}
          />
          <DesignacionDesdeRegistro
            version={data}
            camino="cuil_local"
            cuilAlta={form.cuil}
            nombre={check.local.nombre}
            onDone={onDone}
            onError={onError}
          />
        </div>
      ) : (
        <div className="space-y-4">
          {nombre && <FeedbackBox feedback={{ tone: "info", text: `Nombre completo generado: ${nombre}` }} />}
          <PrimaryButton
            busy={busy}
            onClick={() =>
              run(() => docentesApi.alta({ ...form, fecha_alta: fechaAlta }), true)
            }
          >
            Guardar docente propio
          </PrimaryButton>
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </Card>
  );
}

// ---------------------------------------------------------------------------------------------- Carga rápida
const PREVIEW_COLUMNS = [
  "cuil",
  "apellido",
  "nombres",
  "docente",
  "legajo",
  "titulo",
  "titulo_posgrado",
  "antiguedad_anios",
  "nivel_posgrado_salarial",
  "email",
  "telefono",
  "ref_legajo_fisico",
  "estado",
  "observaciones",
].map((k) => ({ key: k, label: k }));

function CargaRapida({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [texto, setTexto] = useState("");
  const [preview, setPreview] = useState<CargaPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const n = ++seq.current;
    const t = setTimeout(() => {
      if (!texto.trim()) {
        setPreview(null);
        setPreviewError(null);
        return;
      }
      docentesApi
        .cargaPreview(texto)
        .then((p) => {
          if (n === seq.current) {
            setPreview(p);
            setPreviewError(null);
          }
        })
        .catch((e) => {
          if (n === seq.current) {
            setPreview(null);
            setPreviewError(onError(e).message);
          }
        });
    }, 500);
    return () => clearTimeout(t);
  }, [texto, onError]);

  async function download() {
    setDownloading(true);
    setError(null);
    try {
      const blob = await docentesApi.modeloExcel();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "modelo_carga_rapida_docentes.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setDownloading(false);
    }
  }

  const hayDup = (preview?.duplicados.length ?? 0) > 0;

  async function submit() {
    setError(null);
    if (hayDup && !confirmar) {
      setError("No se cargó nada. Hay duplicados: marcá la confirmación si realmente querés avanzar.");
      return;
    }
    setBusy(true);
    try {
      const res = await docentesApi.carga(texto, hayDup && confirmar);
      setTexto("");
      setConfirmar(false);
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-6">
      <CargaIntegral data={data} onDone={onDone} onError={onError} />
      <hr className="border-slate-200" />

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-brand-950">Carga rápida simple de docentes</h3>
        <div className="flex flex-wrap items-center gap-3">
          <PrimaryButton tone="secondary" onClick={download} busy={downloading}>
            Descargar Excel modelo solo para docentes
          </PrimaryButton>
        </div>
        <p className="text-xs text-slate-500">
          Completá la hoja Carga rápida, copiá la tabla con sus encabezados y pegala debajo. El modelo incluye formato,
          instrucciones y lista de estados válidos.
        </p>
        <FeedbackBox
          feedback={{
            tone: "info",
            text:
              "Pegá una tabla copiada desde Excel. Encabezados admitidos: cuil, apellido, nombres, docente, legajo, " +
              "titulo, titulo_posgrado, email, telefono, ref_legajo_fisico, estado.",
          }}
        />
        {!data.permisos.puede_escribir && <ReadOnlyNote />}
        <Field label="Pegá acá los docentes">
          <Textarea value={texto} onChange={setTexto} rows={9} disabled={busy} />
        </Field>
        {previewError && <FeedbackBox feedback={{ tone: "warning", text: previewError }} />}
        {preview?.aviso && <FeedbackBox feedback={{ tone: "warning", text: preview.aviso }} />}
        {preview && preview.filas.length > 0 && (
          <div className="space-y-4">
            <h4 className="text-base font-semibold text-brand-950">Vista previa</h4>
            <DataTable rows={preview.filas} columns={PREVIEW_COLUMNS} rowKey={(_, i) => String(i)} maxHeight="max-h-80" />
            <p className="text-xs text-slate-500">Filas detectadas: {preview.filas.length}</p>
            {hayDup && (
              <>
                <FeedbackBox
                  feedback={{
                    tone: "warning",
                    text:
                      "Hay docentes que ya existen o están repetidos dentro de la tabla pegada. El sistema no los " +
                      "cargará dos veces sin confirmación.",
                  }}
                />
                <DataTable
                  rows={preview.duplicados}
                  columns={[
                    { key: "fila_pegada", label: "fila_pegada" },
                    { key: "cuil", label: "cuil" },
                    { key: "apellido", label: "apellido" },
                    { key: "nombres", label: "nombres" },
                    { key: "motivo", label: "motivo" },
                  ]}
                  rowKey={(_, i) => String(i)}
                  maxHeight="max-h-60"
                />
                <Check
                  checked={confirmar}
                  onChange={setConfirmar}
                  disabled={busy}
                  label="Confirmo que quiero actualizar docentes existentes y omitir duplicados internos"
                />
              </>
            )}
            {data.permisos.puede_escribir && (
              <PrimaryButton onClick={submit} busy={busy}>
                Cargar docentes pegados
              </PrimaryButton>
            )}
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- Editar / eliminar
const EDIT_COLUMNS: Column<Docente>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "legajo", label: "Legajo" },
  { key: "titulo", label: "Título" },
  { key: "email", label: "Correo" },
  { key: "tipo_docente", label: "Tipo" },
  { key: "estado", label: "Estado" },
];
const CURRENT_FIELDS: (keyof Docente)[] = [
  "cuil",
  "legajo",
  "apellido",
  "nombres",
  "titulo",
  "titulo_posgrado",
  "nivel_posgrado_salarial",
  "antiguedad_anios",
  "email",
  "telefono",
  "tipo_docente",
  "estado",
  "fecha_alta",
  "fecha_finalizacion",
  "observaciones",
];

function EditarEliminar({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const filtered = useMemo(
    () =>
      filtrarPorTexto(data.docentes, q, [
        "nombre_completo",
        "apellido",
        "nombres",
        "cuil",
        "legajo",
        "titulo",
        "email",
        "tipo_docente",
      ]),
    [data.docentes, q]
  );
  if (data.docentes.length === 0) return <EmptyState text="No hay docentes para editar." />;
  const fila = filtered.find((r) => r.cuil === sel) ?? filtered[0] ?? null;

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar docente</h3>
      <Field label="Buscar docente">
        <TextInput value={q} onChange={setQ} placeholder="Nombre, apellido, CUIL, legajo, título o correo" />
      </Field>
      {filtered.length === 0 || !fila ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay docentes que coincidan con la búsqueda." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Docentes encontrados</p>
          <DataTable
            rows={filtered}
            columns={EDIT_COLUMNS}
            rowKey={(r) => r.cuil}
            selected={fila.cuil}
            onSelect={setSel}
            maxHeight="max-h-72"
          />
          <DocenteSeleccionado
            key={`${fila.cuil}|${fila.huella}`}
            data={data}
            fila={fila}
            onDone={async (f, nuevoCuil) => {
              if (nuevoCuil) setSel(nuevoCuil);
              await onDone(f);
            }}
            onError={onError}
          />
        </>
      )}
    </section>
  );
}

function DocenteSeleccionado({
  data,
  fila,
  onDone,
  onError,
}: {
  data: DocentesOverview;
  fila: Docente;
  onDone: (f: Feedback, nuevoCuil?: string) => Promise<void>;
  onError: OnError;
}) {
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [fichaError, setFichaError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    docentesApi
      .ficha(fila.cuil)
      .then((f) => !cancelled && setFicha(f))
      .catch((e) => !cancelled && setFichaError(onError(e).message));
    return () => {
      cancelled = true;
    };
  }, [fila.cuil, onError]);

  return (
    <div className="space-y-5">
      <Details summary="Datos actuales del docente seleccionado" defaultOpen>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {CURRENT_FIELDS.map((k) => (
            <div key={k} className="min-w-0">
              <dt className="text-xs text-slate-400">{k}</dt>
              <dd className="truncate text-slate-800">{fila[k] === null || fila[k] === "" ? "-" : String(fila[k])}</dd>
            </div>
          ))}
        </dl>
      </Details>

      {data.permisos.puede_escribir ? (
        <EditarForm data={data} fila={fila} onDone={onDone} onError={onError} />
      ) : (
        <ReadOnlyNote />
      )}

      {fichaError && <FeedbackBox feedback={{ tone: "error", text: fichaError }} />}
      {!ficha && !fichaError && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Revisando cargas vinculadas…
        </p>
      )}
      {ficha && (
        <>
          <Eliminar data={data} fila={fila} ficha={ficha} onDone={onDone} onError={onError} />
          {(fila.tipo_docente || "Propio").trim() === "Prestado" && data.abierto && (
            <Prestamo data={data} fila={fila} ficha={ficha} onDone={onDone} onError={onError} />
          )}
          <Huerfanos data={data} fila={fila} ficha={ficha} onDone={onDone} onError={onError} />
        </>
      )}
    </div>
  );
}

function EditarForm({
  data,
  fila,
  onDone,
  onError,
}: {
  data: DocentesOverview;
  fila: Docente;
  onDone: (f: Feedback, nuevoCuil?: string) => Promise<void>;
  onError: OnError;
}) {
  const nivelActual = nivelPosgradoNormalizado(fila.nivel_posgrado_salarial);
  const [form, setForm] = useState<DocenteForm>({
    apellido: fila.apellido ?? "",
    nombres: fila.nombres ?? "",
    cuil: fila.cuil,
    legajo: fila.legajo ?? "",
    titulo: fila.titulo ?? "",
    titulo_posgrado: fila.titulo_posgrado ?? "",
    nivel_posgrado_salarial: nivelActual,
    antiguedad_anios: fila.antiguedad_anios,
    email: fila.email ?? "",
    telefono: fila.telefono ?? "",
    ref_legajo_fisico: fila.ref_legajo_fisico ?? "",
    observaciones: fila.observaciones ?? "",
  });
  const [informar, setInformar] = useState(fila.antiguedad_anios !== null);
  const pick = (opts: string[], v: string | null, def: string) => (v !== null && opts.includes(v) ? v : def);
  const [estado, setEstado] = useState(pick(data.catalogos.estados, fila.estado || "Activo", data.catalogos.estados[0]));
  const [tipo, setTipo] = useState(pick(data.catalogos.tipos, fila.tipo_docente || "Propio", data.catalogos.tipos[0]));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<DocenteForm>) => setForm((f) => ({ ...f, ...patch }));
  const nombre = nombreCompleto(form.apellido, form.nombres);
  const cambiaCuil = limpiarCuil(form.cuil) !== limpiarCuil(fila.cuil);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await docentesApi.editar({
        ...form,
        cuil_original: fila.cuil,
        huella: fila.huella,
        estado,
        tipo_docente: tipo,
      });
      await onDone({ tone: res.tono, text: res.mensaje }, res.cuil);
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h4 className="text-base font-semibold text-brand-950">Editar datos</h4>
      <DocenteFields
        form={form}
        set={set}
        data={data}
        disabled={busy}
        informar={informar}
        setInformar={setInformar}
        extra={
          <>
            <Field label="Estado docente">
              <Select value={estado} options={data.catalogos.estados} onChange={setEstado} disabled={busy} />
            </Field>
            <Field label="Tipo de docente">
              <Select value={tipo} options={data.catalogos.tipos} onChange={setTipo} disabled={busy} />
            </Field>
          </>
        }
      />
      <Field label="Observación">
        <Textarea value={form.observaciones} onChange={(v) => set({ observaciones: v })} disabled={busy} />
      </Field>
      {nombre && <FeedbackBox feedback={{ tone: "info", text: `Nombre completo generado: ${nombre}` }} />}
      {cambiaCuil && (
        <FeedbackBox
          feedback={{
            tone: "warning",
            text:
              "Estás modificando el CUIL de una persona existente. Al guardar, la app conservará al mismo docente y " +
              "actualizará en una sola transacción sus designaciones, comisiones, proyectos, actividades, " +
              "movimientos y datos de disposición. No se creará un docente nuevo.",
          }}
        />
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <PrimaryButton onClick={submit} busy={busy}>
        Guardar cambios
      </PrimaryButton>
    </Card>
  );
}

const REF_TABLES: { key: keyof Ficha["referencias"]; titulo: string }[] = [
  { key: "designaciones", titulo: "Designaciones" },
  { key: "comisiones", titulo: "Asignaciones en comisiones" },
  { key: "investigacion", titulo: "Asignaciones de investigación" },
];

function FilasTable({ rows }: { rows: Fila[] }) {
  const columns = Object.keys(rows[0] ?? {}).map((k) => ({ key: k, label: etiquetaColumna(k) }));
  return <DataTable rows={rows} columns={columns} rowKey={(_, i) => String(i)} maxHeight="max-h-60" />;
}

function Eliminar({
  data,
  fila,
  ficha,
  onDone,
  onError,
}: {
  data: DocentesOverview;
  fila: Docente;
  ficha: Ficha;
  onDone: (f: Feedback) => Promise<void>;
  onError: OnError;
}) {
  const [confirmar, setConfirmar] = useState(false);
  const [integral, setIntegral] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refs = ficha.referencias;

  if (!data.permisos.puede_borrar) {
    return (
      <p className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
        La eliminación física de docentes por error de carga solo está habilitada para el superadmin. Para una baja
        real, se cambia el estado del docente.
      </p>
    );
  }

  async function submit() {
    setError(null);
    if (!confirmar) {
      setError("Primero confirmá la eliminación.");
      return;
    }
    setBusy(true);
    try {
      const res = await docentesApi.eliminar({
        cuil: fila.cuil,
        huella: fila.huella,
        confirmar,
        integral: refs.total > 0 && integral,
      });
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h4 className="text-base font-semibold text-brand-950">Eliminar docente</h4>
      <p className="text-xs text-slate-500">
        La eliminación física se usa solo para una carga errónea. Nunca modifica al mismo docente en otros
        departamentos.
      </p>
      {refs.total > 0 && (
        <>
          <FeedbackBox
            feedback={{
              tone: "warning",
              text:
                "Este registro todavía tiene cargas en el departamento actual: " +
                `${refs.designaciones.length} designación/es, ${refs.comisiones.length} comisión/es y ` +
                `${refs.investigacion.length} asignación/es de investigación.`,
            }}
          />
          <Details summary="Ver cargas locales que impiden la eliminación">
            {REF_TABLES.filter((t) => (refs[t.key] as Fila[]).length > 0).map((t) => (
              <div key={t.key} className="space-y-2">
                <p className="text-sm font-semibold text-slate-700">{t.titulo}</p>
                <FilasTable rows={refs[t.key] as Fila[]} />
              </div>
            ))}
          </Details>
        </>
      )}
      <Check
        checked={confirmar}
        onChange={setConfirmar}
        disabled={busy}
        label="Confirmo que quiero eliminar este docente por error de carga"
      />
      {refs.total > 0 && (
        <>
          <Check
            checked={integral}
            onChange={setIntegral}
            disabled={busy}
            label="Eliminar también todas sus cargas de este departamento en todos los períodos (designaciones, comisiones, investigación y rastros administrativos)"
          />
          <FeedbackBox
            feedback={{
              tone: "error",
              text:
                "Esta opción es irreversible, pero queda limitada al departamento actual. Las designaciones de " +
                "otros departamentos se conservan.",
            }}
          />
        </>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <PrimaryButton tone="danger" onClick={submit} busy={busy}>
        Eliminar docente
      </PrimaryButton>
    </Card>
  );
}

function Prestamo({
  data,
  fila,
  ficha,
  onDone,
  onError,
}: {
  data: DocentesOverview;
  fila: Docente;
  ficha: Ficha;
  onDone: (f: Feedback) => Promise<void>;
  onError: OnError;
}) {
  const activo = ficha.prestamo?.activo ?? null;
  const [fecha, setFecha] = useState(today());
  const [obs, setObs] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const periodo = data.abierto?.nombre ?? "";

  async function submit() {
    setError(null);
    if (!confirmar) {
      setError("Confirmá la finalización del préstamo.");
      return;
    }
    setBusy(true);
    try {
      const res = await docentesApi.finalizarPrestamo({
        cuil: fila.cuil,
        huella: fila.huella,
        fecha_fin: fecha,
        observaciones: obs,
        confirmar,
      });
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="Préstamo docente del período" defaultOpen={activo !== null}>
      {activo === null ? (
        <FeedbackBox
          feedback={{
            tone: "info",
            text: `Este docente no tiene un préstamo activo en ${periodo}. Si vuelve a ser prestado, registralo nuevamente desde 'Registrar docente'.`,
          }}
        />
      ) : (
        <>
          <FeedbackBox
            feedback={{
              tone: "info",
              text: `Préstamo activo en ${periodo} · Origen: ${activo.departamento_origen} · Desde: ${activo.fecha_desde}`,
            }}
          />
          {data.permisos.puede_escribir ? (
            <>
              <Field label="Fecha de finalización del préstamo">
                <TextInput type="date" value={fecha} onChange={setFecha} disabled={busy} />
              </Field>
              <Field label="Motivo / observación de la finalización">
                <Textarea value={obs} onChange={setObs} disabled={busy} />
              </Field>
              <Check
                checked={confirmar}
                onChange={setConfirmar}
                disabled={busy}
                label="Confirmo que quiero finalizar el préstamo en este departamento"
              />
              <p className="text-xs text-slate-500">
                Al finalizarlo, sale del plantel operativo y se finalizan sus asignaciones activas en comisiones del
                período. El historial no se borra.
              </p>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <PrimaryButton onClick={submit} busy={busy}>
                Finalizar préstamo
              </PrimaryButton>
            </>
          ) : (
            <ReadOnlyNote />
          )}
        </>
      )}
    </Details>
  );
}

function Huerfanos({
  data,
  fila,
  ficha,
  onDone,
  onError,
}: {
  data: DocentesOverview;
  fila: Docente;
  ficha: Ficha;
  onDone: (f: Feedback) => Promise<void>;
  onError: OnError;
}) {
  const lista = ficha.huerfanos;
  const [elegido, setElegido] = useState(lista[0]?.cuil_huerfano ?? "");
  const [confirmar, setConfirmar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const detalle = lista.find((h) => h.cuil_huerfano === elegido);

  async function submit() {
    setError(null);
    if (!confirmar) {
      setError("Confirmá primero que el CUIL huérfano pertenece a esta misma persona.");
      return;
    }
    setBusy(true);
    try {
      const res = await docentesApi.repararCuil({
        cuil: fila.cuil,
        huella: fila.huella,
        cuil_huerfano: elegido,
        confirmar,
      });
      await onDone({ tone: res.tono, text: res.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="Reparar CUIL anterior / referencias huérfanas">
      <p className="text-xs text-slate-500">
        Usá esta herramienta únicamente cuando el CUIL de esta misma persona fue corregido antes de la v168 y quedaron
        cargas con el CUIL anterior. Las cargas válidas se trasladan al CUIL actual; si una designación o asignación ya
        fue recreada, se elimina solamente el duplicado viejo.
      </p>
      {lista.length === 0 ? (
        <FeedbackBox
          feedback={{ tone: "success", text: "No se detectaron CUIL huérfanos en las cargas operativas de la institución." }}
        />
      ) : (
        <>
          <DataTable
            rows={lista}
            columns={[
              { key: "cuil_huerfano", label: "CUIL huérfano" },
              { key: "referencias", label: "Referencias" },
              { key: "detalle", label: "Detalle" },
            ]}
            rowKey={(r) => r.cuil_huerfano}
            maxHeight="max-h-60"
          />
          {data.permisos.puede_escribir ? (
            <>
              <Field label="CUIL anterior que pertenecía a este docente">
                <Select
                  value={elegido}
                  options={lista.map((h) => h.cuil_huerfano)}
                  onChange={setElegido}
                  disabled={busy}
                />
              </Field>
              {detalle && (
                <FeedbackBox
                  feedback={{ tone: "info", text: `Se migrarán al CUIL actual ${fila.cuil}: ${detalle.detalle}` }}
                />
              )}
              <Check
                checked={confirmar}
                onChange={setConfirmar}
                disabled={busy}
                label={`Confirmo que ${elegido} era el CUIL anterior de ${fila.nombre_completo}`}
              />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <PrimaryButton onClick={submit} busy={busy}>
                Migrar cargas al CUIL actual
              </PrimaryButton>
            </>
          ) : (
            <ReadOnlyNote />
          )}
        </>
      )}
    </Details>
  );
}

function ReadOnlyNote() {
  return (
    <p className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
      Tu rol puede consultar los docentes, pero no modificarlos.
    </p>
  );
}
