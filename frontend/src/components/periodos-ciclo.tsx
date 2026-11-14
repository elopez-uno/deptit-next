"use client";

// E4-10 / E4-11 / E4-12: pestañas "➕ Crear nuevo período", "↩️ Revertir último cierre" y "🗑️ Eliminar período"
// (B13-FIX02 entry l. 62685-63389). Cada operación es UNA transacción en el backend (D-E4-06); acá solo se arma la
// pantalla. Revertir y Eliminar: solo superadmin (el backend vuelve a autorizar). Eliminar es "NEXT solo vacío"
// (D-E4-03): la purga certificada con datos no existe. En la misma pestaña, separado del borrado, el bloque P-12b
// "♻️ Reparar finalizaciones automáticas del período abierto" (entry l. 63264-63284): solo superadmin y solo si el
// período abierto tiene finalizaciones automáticas por cierre (si no, no se muestra, como el certificado).
import { useEffect, useState } from "react";
import {
  Check,
  DataTable,
  FeedbackBox,
  Field,
  PrimaryButton,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type CrearContexto,
  type EliminarDiagnostico,
  type PeriodosOverview,
  type RepararDiagnostico,
  type RevertirDiagnostico,
  type TablaConteo,
  cicloApi,
  periodoLabel,
} from "@/lib/periodos";

type OnDone = (f: { tone: "success" | "warning" | "error"; text: string } | null) => Promise<void>;
type OnError = (e: unknown) => ApiError;

function Negrita({ texto }: { texto: string }) {
  const partes = texto.split("**");
  return <>{partes.map((p, i) => (i % 2 ? <b key={i}>{p}</b> : <span key={i}>{p}</span>))}</>;
}

function Metrica({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-semibold text-brand-950">{value}</p>
    </div>
  );
}

function Solo({ texto }: { texto: string }) {
  return <FeedbackBox feedback={{ tone: "error", text: texto }} />;
}

// ---------------------------------------------------------------------------------------------- E4-10 Crear
export function CrearPeriodo({ data, onDone, onError }: { data: PeriodosOverview; onDone: OnDone; onError: OnError }) {
  const [anio, setAnio] = useState<string | null>(null);
  const [semestre, setSemestre] = useState("1");
  const [copiar, setCopiar] = useState(true);
  const [obs, setObs] = useState("");
  const [ctx, setCtx] = useState<CrearContexto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const anioNum = anio === null ? null : Number(anio);
  useEffect(() => {
    let cancelled = false;
    const a = anioNum ?? new Date().getFullYear();
    if (!Number.isInteger(a) || a < 2020 || a > 2100) return;
    const t = setTimeout(() => {
      cicloApi
        .crearContexto(a, Number(semestre))
        .then((r) => {
          if (cancelled) return;
          setCtx(r);
          if (anio === null) setAnio(String(r.anio_default));
        })
        .catch((e) => !cancelled && setError(onError(e).message));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [anioNum, anio, semestre, data, onError]);

  async function crear() {
    if (!ctx || anioNum === null) return;
    setBusy(true);
    setError(null);
    try {
      const r = await cicloApi.crear({ anio: anioNum, semestre: Number(semestre), copiar_anterior: copiar, observaciones: obs });
      setObs("");
      await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Crear nuevo período</h3>
      {ctx && <FeedbackBox feedback={{ tone: "warning", text: ctx.aviso }} />}
      {ctx?.gate.aviso && <FeedbackBox feedback={{ tone: "info", text: ctx.gate.aviso }} />}
      {ctx && !ctx.puede_escribir ? (
        <p className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
          Tu rol puede consultar los períodos, pero no modificarlos.
        </p>
      ) : (
        ctx && (
          <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <Field label="Año">
              <TextInput type="number" value={anio ?? ""} onChange={setAnio} disabled={busy} />
            </Field>
            <Field label="Semestre">
              <Select
                value={semestre}
                options={ctx.semestres.map((s) => String(s.valor))}
                label={(v) => ctx.semestres.find((s) => String(s.valor) === v)?.etiqueta ?? v}
                onChange={setSemestre}
                disabled={busy}
              />
            </Field>
            <Check
              checked={copiar}
              onChange={setCopiar}
              disabled={busy}
              label="Copiar designaciones activas no concursadas del período anterior"
            />
            <Field label="Observaciones del período">
              <Textarea value={obs} onChange={setObs} disabled={busy} />
            </Field>
            <FeedbackBox
              feedback={{
                tone: "info",
                text: `Período a crear: ${ctx.objetivo.nombre} (${ctx.objetivo.fecha_inicio} al ${ctx.objetivo.fecha_fin})`,
              }}
            />
            {ctx.existente && (
              <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <Negrita
                  texto={`El período **${ctx.objetivo.nombre}** ya existe y no puede volver a crearse. Estado actual: **${ctx.existente.estado ?? ""}**.`}
                />
              </p>
            )}
            {error && <p className="text-sm text-red-600">{error}</p>}
            <PrimaryButton busy={busy} disabled={ctx.existente !== null} onClick={crear}>
              🗓️ Crear período
            </PrimaryButton>
          </div>
        )
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- E4-11 Revertir
function Bloqueos({ filas }: { filas: TablaConteo[] }) {
  return (
    <DataTable
      rows={filas}
      columns={[
        { key: "etiqueta", label: "Información del período" },
        { key: "filas", label: "Filas" },
      ]}
      rowKey={(r) => `${r.tabla}-${r.etiqueta}`}
      maxHeight="max-h-60"
    />
  );
}

export function RevertirCierre({ data, onDone, onError }: { data: PeriodosOverview; onDone: OnDone; onError: OnError }) {
  const [diag, setDiag] = useState<RevertirDiagnostico | null>(null);
  const [obs, setObs] = useState("");
  const [c1, setC1] = useState(false);
  const [c2, setC2] = useState(false);
  const [c3, setC3] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    cicloApi
      .revertirDiagnostico()
      .then((r) => !cancelled && setDiag(r))
      .catch((e) => !cancelled && setError(onError(e).message));
    return () => {
      cancelled = true;
    };
  }, [data, onError]);

  async function revertir() {
    setError(null);
    if (!c1 || !c2 || !c3) {
      setError("Tenés que marcar las tres confirmaciones antes de revertir el cierre.");
      return;
    }
    setBusy(true);
    try {
      const r = await cicloApi.revertir({ observaciones: obs, confirmar_1: c1, confirmar_2: c2, confirmar_3: c3, huella: diag?.huella ?? "" });
      setObs("");
      setC1(false);
      setC2(false);
      setC3(false);
      await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-3xl space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Revertir último cierre de período</h3>
      {diag && <FeedbackBox feedback={{ tone: "info", text: diag.info }} />}
      {error && !diag && <p className="text-sm text-red-600">{error}</p>}
      {diag && !diag.es_superadmin && <Solo texto={diag.mensaje_permiso ?? ""} />}
      {diag?.es_superadmin && !diag.ok && <FeedbackBox feedback={{ tone: "warning", text: diag.mensaje ?? "" }} />}
      {diag?.es_superadmin && diag.ok && diag.periodo_nuevo && diag.periodo_anterior && (
        <div className="space-y-4">
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <Negrita
              texto={`Se revertiría el cierre que creó el período **${diag.periodo_nuevo.nombre}** y se reabriría **${diag.periodo_anterior.nombre}**.`}
            />
          </p>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Metrica label="Período a eliminar" value={diag.periodo_nuevo.nombre ?? "-"} />
            <Metrica label="Designaciones del período nuevo" value={diag.designaciones_nuevo ?? 0} />
            <Metrica label="Cierres automáticos detectados" value={diag.cierres_anterior ?? 0} />
            <Metrica label="Activas actuales en período anterior" value={diag.activas_anterior ?? 0} />
          </div>
          {!diag.puede_revertir ? (
            <div className="space-y-3">
              <FeedbackBox feedback={{ tone: "error", text: diag.mensaje_bloqueo ?? "" }} />
              <Bloqueos filas={diag.bloqueos ?? []} />
            </div>
          ) : (
            <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <Field label="Motivo / observaciones de la reversión">
                <Textarea value={obs} onChange={setObs} disabled={busy} />
              </Field>
              <Check checked={c1} onChange={setC1} disabled={busy}
                label="Entiendo que se eliminará el último período creado y sus renovaciones automáticas." />
              <Check checked={c2} onChange={setC2} disabled={busy}
                label="Entiendo que se reabrirá el período anterior y se reactivarán solo las designaciones cerradas automáticamente." />
              <Check checked={c3} onChange={setC3} disabled={busy} label="Confirmo que quiero revertir el último cierre de período." />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <PrimaryButton busy={busy} onClick={revertir}>
                ↩️ Revertir último cierre
              </PrimaryButton>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------- E4-12 / P-12b Reparar
function RepararFinalizaciones({ data, onDone, onError }: { data: PeriodosOverview; onDone: OnDone; onError: OnError }) {
  const [diag, setDiag] = useState<RepararDiagnostico | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    cicloApi
      .repararDiagnostico()
      .then((r) => !cancelled && setDiag(r))
      .catch(() => !cancelled && setDiag(null)); // certificado: si el diagnóstico falla, el bloque no se muestra
    return () => {
      cancelled = true;
    };
  }, [data]);

  async function reparar() {
    setError(null);
    setBusy(true);
    try {
      const r = await cicloApi.reparar(diag?.huella ?? "");
      await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  if (!diag?.es_superadmin || !diag.visible) return null;
  return (
    <div className="space-y-3 rounded-xl border border-amber-200 bg-white p-5 shadow-sm" data-testid="reparar-finalizaciones">
      {diag.puede_reparar ? (
        <>
          <FeedbackBox feedback={{ tone: "warning", text: diag.mensaje ?? "" }} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <PrimaryButton busy={busy} onClick={reparar}>
            {diag.boton ?? "♻️ Reparar finalizaciones automáticas del período abierto"}
          </PrimaryButton>
        </>
      ) : (
        <>
          <FeedbackBox feedback={{ tone: "error", text: diag.mensaje ?? "" }} />
          <Bloqueos filas={diag.bloqueos ?? []} />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- E4-12 Eliminar
export function EliminarPeriodo({ data, onDone, onError }: { data: PeriodosOverview; onDone: OnDone; onError: OnError }) {
  const [sel, setSel] = useState<number | null>(data.periodos[0]?.id ?? null);
  const [diag, setDiag] = useState<EliminarDiagnostico | null>(null);
  const [obs, setObs] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [texto, setTexto] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actual = sel !== null && data.periodos.some((p) => p.id === sel) ? sel : (data.periodos[0]?.id ?? null);

  useEffect(() => {
    let cancelled = false;
    cicloApi
      .eliminarDiagnostico(actual)
      .then((r) => !cancelled && setDiag(r))
      .catch((e) => !cancelled && setError(onError(e).message));
    return () => {
      cancelled = true;
    };
  }, [actual, data, onError]);

  async function eliminar() {
    setError(null);
    if (!diag?.periodo || actual === null) return;
    if (!confirmar) {
      setError("Tenés que marcar la confirmación antes de eliminar el período.");
      return;
    }
    if (texto.trim() !== diag.texto_confirmacion) {
      setError(`La confirmación escrita no coincide. Escribí: ${diag.texto_confirmacion}`);
      return;
    }
    setBusy(true);
    try {
      const r = await cicloApi.eliminar({ periodo_id: actual, observaciones: obs, confirmar, texto_confirmacion: texto, huella: diag.huella ?? "" });
      setObs("");
      setConfirmar(false);
      setTexto("");
      await onDone({ tone: "success", text: r.mensaje });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  const conteo = (tabla: string) => diag?.conteos?.find((c) => c.tabla === tabla)?.filas ?? 0;
  return (
    <section className="max-w-3xl space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Eliminar período</h3>
      {diag && <FeedbackBox feedback={{ tone: "info", text: diag.info }} />}
      <RepararFinalizaciones data={data} onDone={onDone} onError={onError} />
      {diag && !diag.es_superadmin && <Solo texto={diag.mensaje_permiso ?? ""} />}
      {diag?.es_superadmin &&
        (data.periodos.length === 0 ? (
          <FeedbackBox feedback={{ tone: "info", text: "Todavía no hay períodos registrados." }} />
        ) : (
          <div className="space-y-4">
            <Field label="Seleccioná el período a eliminar">
              <Select
                value={String(actual)}
                options={data.periodos.map((p) => String(p.id))}
                label={(v) => {
                  const p = data.periodos.find((x) => String(x.id) === v);
                  return p ? periodoLabel(p) : v;
                }}
                onChange={(v) => {
                  setSel(Number(v));
                  setTexto("");
                  setConfirmar(false);
                }}
              />
            </Field>
            {diag.periodo && (
              <>
                <p className="text-sm text-slate-700">
                  <Negrita texto={`Período seleccionado: **${diag.periodo.nombre}** (${diag.periodo.fecha_inicio} al ${diag.periodo.fecha_fin}).`} />
                </p>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <Metrica label="Designaciones" value={conteo("designaciones")} />
                  <Metrica label="Movimientos" value={diag.movimientos ?? 0} />
                  <Metrica label="Comisiones" value={conteo("comisiones")} />
                  <Metrica label="Estado" value={diag.periodo.estado ?? "-"} />
                </div>
                {!diag.vacio ? (
                  <div className="space-y-3">
                    <FeedbackBox feedback={{ tone: "error", text: diag.mensaje ?? "" }} />
                    <Bloqueos filas={diag.bloqueos ?? []} />
                  </div>
                ) : (
                  <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <FeedbackBox
                      feedback={{
                        tone: "success",
                        text:
                          diag.apertura_automatica !== null && diag.apertura_automatica !== undefined
                            ? "El período está vacío: su único movimiento es la apertura automática del sistema, que se eliminará junto con el período."
                            : "El período está vacío.",
                      }}
                    />
                    {diag.proximo_activo && (
                      <p className="text-sm text-slate-700">
                        <Negrita
                          texto={`Después de eliminarlo, quedará activo el período **${diag.proximo_activo.nombre}** (${diag.proximo_activo.fecha_inicio} al ${diag.proximo_activo.fecha_fin}).`}
                        />
                      </p>
                    )}
                    <Field label="Motivo / observaciones de la eliminación">
                      <Textarea value={obs} onChange={setObs} disabled={busy} />
                    </Field>
                    <Check checked={confirmar} onChange={setConfirmar} disabled={busy}
                      label="Entiendo que se eliminará el período vacío seleccionado y que esta acción no se puede deshacer desde la app." />
                    <Field label={`Para confirmar, escribí exactamente: ${diag.texto_confirmacion}`}>
                      <TextInput value={texto} onChange={setTexto} disabled={busy} />
                    </Field>
                    {error && <p className="text-sm text-red-600">{error}</p>}
                    <PrimaryButton busy={busy} tone="danger" onClick={eliminar}>
                      🗑️ Eliminar período vacío
                    </PrimaryButton>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
    </section>
  );
}
