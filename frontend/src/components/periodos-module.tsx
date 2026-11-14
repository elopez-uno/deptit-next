"use client";

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/brand";
import { CrearPeriodo, EliminarPeriodo, RevertirCierre } from "@/components/periodos-ciclo";
import { ApiError } from "@/lib/auth";
import { emitirPeriodoCambiado } from "@/lib/periodo-cambiado";
import {
  type Periodo,
  type PeriodosOverview,
  periodoLabel,
  periodosApi,
} from "@/lib/periodos";

// Módulo Períodos (B13-FIX02, entry l. 61933-63391). Pestañas, textos y confirmaciones del sistema certificado.
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura.
const TABS = [
  { key: "registrados", label: "Períodos registrados" },
  { key: "crear", label: "Crear nuevo período" },
  { key: "abrir", label: "Abrir período anterior" },
  { key: "volver", label: "Volver al período actual" },
  { key: "revertir", label: "Revertir último cierre" },
  { key: "eliminar", label: "Eliminar período" },
] as const;

type TabKey = (typeof TABS)[number]["key"];
type Feedback = { tone: "success" | "warning" | "error"; text: string } | null;

export function PeriodosModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<PeriodosOverview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("registrados");
  const [feedback, setFeedback] = useState<Feedback>(null);

  const handle = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) onAuthError(err);
      return err instanceof ApiError
        ? err
        : new ApiError(0, "ERROR", "No se pudo completar la operación.");
    },
    [onAuthError]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await periodosApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    periodosApi
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
    // P-01b: toda escritura de Períodos puede cambiar el período abierto -> el shell recalcula el contexto ya.
    emitirPeriodoCambiado();
    await load();
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando períodos…
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
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">Módulo Períodos</h2>
        </div>
        <OpenPeriodBadge abierto={data.abierto} />
      </div>

      <div
        role="tablist"
        aria-label="Secciones de Períodos"
        className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200"
      >
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
        {tab === "registrados" && <Registrados data={data} />}
        {tab === "crear" && <CrearPeriodo data={data} onDone={afterWrite} onError={handle} />}
        {tab === "abrir" && (
          <AbrirAnterior data={data} onDone={afterWrite} onError={handle} />
        )}
        {tab === "volver" && <VolverActual data={data} onDone={afterWrite} onError={handle} />}
        {tab === "revertir" && <RevertirCierre data={data} onDone={afterWrite} onError={handle} />}
        {tab === "eliminar" && <EliminarPeriodo data={data} onDone={afterWrite} onError={handle} />}
      </div>
    </div>
  );
}

function OpenPeriodBadge({ abierto }: { abierto: Periodo | null }) {
  if (!abierto) {
    return (
      <span className="rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700">
        Sin período abierto
      </span>
    );
  }
  return (
    <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
      Abierto: {abierto.nombre}
    </span>
  );
}

function Registrados({ data }: { data: PeriodosOverview }) {
  if (data.periodos.length === 0) {
    return <EmptyState text="Todavía no hay períodos registrados." />;
  }
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              {["Nombre", "Año", "Semestre", "Inicio", "Fin", "Estado", "Observaciones"].map((h) => (
                <th key={h} scope="col" className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.periodos.map((p) => (
              <tr key={p.id} className={p.estado === "Abierto" ? "bg-emerald-50/40" : undefined}>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{p.nombre}</td>
                <td className="px-4 py-3 text-slate-700">{p.anio}</td>
                <td className="px-4 py-3 text-slate-700">{p.semestre}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{p.fecha_inicio}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{p.fecha_fin}</td>
                <td className="px-4 py-3">
                  <StateChip estado={p.estado} />
                </td>
                <td className="max-w-xs px-4 py-3 text-slate-600">
                  <span className="line-clamp-2">{p.observaciones}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.abierto ? (
        <FeedbackBox
          feedback={{
            tone: "success",
            text: `Período abierto: ${data.abierto.nombre} (${data.abierto.fecha_inicio} al ${data.abierto.fecha_fin})`,
          }}
        />
      ) : (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay período abierto." }} />
      )}
    </div>
  );
}

function AbrirAnterior({
  data,
  onDone,
  onError,
}: {
  data: PeriodosOverview;
  onDone: (f: Feedback) => Promise<void>;
  onError: (e: unknown) => ApiError;
}) {
  const [selected, setSelected] = useState<number | null>(data.periodos[0]?.id ?? null);
  const [obs, setObs] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const [confirmUse, setConfirmUse] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (data.periodos.length === 0) return <EmptyState text="Todavía no hay períodos registrados." />;

  async function submit() {
    setError(null);
    if (!confirmClose || !confirmUse) {
      setError("Tenés que marcar ambas confirmaciones antes de abrir un período anterior.");
      return;
    }
    if (selected === null) return;
    setBusy(true);
    try {
      const res = await periodosApi.openPrevious({
        periodo_id: selected,
        observaciones: obs,
        confirmar_cierre: confirmClose,
        confirmar_excepcional: confirmUse,
      });
      setObs("");
      setConfirmClose(false);
      setConfirmUse(false);
      await onDone({ tone: "warning", text: res.mensaje });
    } catch (err) {
      setError(onError(err).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Abrir período anterior por excepción</h3>
      <FeedbackBox
        feedback={{
          tone: "error",
          text:
            "Uso excepcional: al abrir un período anterior, se cerrará el período actualmente abierto. " +
            "Esto debe usarse solo para correcciones puntuales de períodos pasados.",
        }}
      />
      {!data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <Field label="Seleccioná el período que querés abrir">
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={selected ?? ""}
              disabled={busy}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {data.periodos.map((p) => (
                <option key={p.id} value={p.id}>
                  {periodoLabel(p)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Motivo / observaciones de la apertura excepcional">
            <Textarea value={obs} onChange={setObs} disabled={busy} />
          </Field>
          <Check
            checked={confirmClose}
            onChange={setConfirmClose}
            disabled={busy}
            label="Entiendo que se cerrará el período abierto actual y se abrirá el período seleccionado."
          />
          <Check
            checked={confirmUse}
            onChange={setConfirmUse}
            disabled={busy}
            label="Confirmo que esta apertura es excepcional y necesaria para corregir datos del período seleccionado."
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <PrimaryButton onClick={submit} busy={busy} disabled={!confirmClose || !confirmUse}>
            Abrir período seleccionado
          </PrimaryButton>
        </div>
      )}
    </section>
  );
}

function VolverActual({
  data,
  onDone,
  onError,
}: {
  data: PeriodosOverview;
  onDone: (f: Feedback) => Promise<void>;
  onError: (e: unknown) => ApiError;
}) {
  const [obs, setObs] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const [confirmReturn, setConfirmReturn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { actual, abierto } = data;

  if (data.periodos.length === 0 || actual === null) {
    return <EmptyState text="Todavía no hay períodos registrados." />;
  }
  if (abierto && abierto.id === actual.id) {
    return (
      <section className="max-w-2xl">
        <h3 className="mb-4 text-lg font-semibold text-brand-950">Volver al período actual</h3>
        <FeedbackBox
          feedback={{
            tone: "success",
            text: `Ya estás trabajando sobre el período actual: ${actual.nombre} (${actual.fecha_inicio} al ${actual.fecha_fin}).`,
          }}
        />
      </section>
    );
  }

  const withoutOpen = abierto === null;
  const ready = withoutOpen ? confirmReturn : confirmClose && confirmReturn;

  async function submit() {
    setError(null);
    if (!ready) {
      setError(
        withoutOpen
          ? "Tenés que confirmar la acción antes de continuar."
          : "Tenés que marcar ambas confirmaciones antes de volver al período actual."
      );
      return;
    }
    setBusy(true);
    try {
      const res = await periodosApi.returnCurrent({
        observaciones: obs,
        confirmar_cierre_anterior: !withoutOpen && confirmClose,
        confirmar_retorno: confirmReturn,
      });
      setObs("");
      setConfirmClose(false);
      setConfirmReturn(false);
      await onDone({ tone: "success", text: res.mensaje });
    } catch (err) {
      setError(onError(err).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Volver al período actual</h3>
      {withoutOpen ? (
        <>
          <FeedbackBox feedback={{ tone: "warning", text: "No hay período abierto actualmente." }} />
          <FeedbackBox
            feedback={{
              tone: "info",
              text: `El último período creado es ${actual.nombre} (${actual.fecha_inicio} al ${actual.fecha_fin}).`,
            }}
          />
        </>
      ) : (
        <>
          <FeedbackBox
            feedback={{
              tone: "error",
              text: `Actualmente está abierto un período anterior: ${abierto.nombre} (${abierto.fecha_inicio} al ${abierto.fecha_fin}).`,
            }}
          />
          <FeedbackBox
            feedback={{
              tone: "info",
              text: `El período actual, entendido como el último período creado, es: ${actual.nombre} (${actual.fecha_inicio} al ${actual.fecha_fin}).`,
            }}
          />
          <FeedbackBox
            feedback={{
              tone: "warning",
              text:
                "Al volver al período actual, se cerrará el período anterior que está abierto ahora. " +
                "Usá esta opción cuando terminaste la corrección excepcional del período pasado.",
            }}
          />
        </>
      )}
      {!data.permisos.puede_escribir ? (
        <ReadOnlyNote />
      ) : (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <Field
            label={withoutOpen ? "Motivo / observaciones" : "Motivo / observaciones del retorno al período actual"}
          >
            <Textarea value={obs} onChange={setObs} disabled={busy} />
          </Field>
          {!withoutOpen && (
            <Check
              checked={confirmClose}
              onChange={setConfirmClose}
              disabled={busy}
              label="Entiendo que se cerrará el período anterior abierto actualmente."
            />
          )}
          <Check
            checked={confirmReturn}
            onChange={setConfirmReturn}
            disabled={busy}
            label={
              withoutOpen
                ? "Confirmo que quiero abrir el último período creado como período actual."
                : "Confirmo que ya terminé las correcciones excepcionales y quiero volver al último período creado."
            }
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <PrimaryButton onClick={submit} busy={busy} disabled={!ready}>
            {withoutOpen ? "Abrir período actual" : "Volver al período actual"}
          </PrimaryButton>
        </div>
      )}
    </section>
  );
}

function ReadOnlyNote() {
  return (
    <p className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
      Tu rol puede consultar los períodos, pero no modificarlos.
    </p>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
      {text}
    </div>
  );
}

function FeedbackBox({ feedback }: { feedback: { tone: string; text: string } }) {
  const tones: Record<string, string> = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    error: "border-red-200 bg-red-50 text-red-700",
    info: "border-brand-100 bg-brand-50 text-brand-800",
  };
  return (
    <div role="status" className={`mb-4 rounded-xl border px-4 py-3 text-sm ${tones[feedback.tone]}`}>
      {feedback.text}
    </div>
  );
}

function StateChip({ estado }: { estado: string | null }) {
  const open = estado === "Abierto";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        open ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
      }`}
    >
      {estado ?? "-"}
    </span>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function Textarea({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <textarea
      className="min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

function Check({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled: boolean;
  label: string;
}) {
  return (
    <label className="flex items-start gap-3 text-sm text-slate-700">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-brand-600"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

function PrimaryButton({
  onClick,
  busy,
  disabled,
  children,
}: {
  onClick: () => void;
  busy: boolean;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className="flex items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}
