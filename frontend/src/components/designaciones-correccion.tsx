"use client";

// Pestañas "🛠️ Editar / eliminar por error" (entry l. 64296-64689) y "📥 Carga rápida" (l. 64690-64822).
// Sobre el período abierto. Las correcciones por error no registran movimientos.
import { useEffect, useMemo, useState } from "react";
import { Check, Field, FeedbackBox, PrimaryButton, Radio, Select, Textarea, TextInput } from "@/components/module-ui";
import {
  Aviso,
  Caption,
  type Col,
  DateInput,
  FuncionNoDocenteTexto,
  type OnDone,
  type OnError,
  type TabProps,
  Tabla,
  filtrar,
  hoyIso,
  safeDate,
  useAccion,
  usePeriodo,
} from "@/components/designaciones-shared";
import {
  type Carga,
  type Designacion,
  type Overview,
  type Periodo,
  type WriteResult,
  designacionesApi,
  download,
  esNoDocente,
  horasSegunDedicacion,
  pick,
  post,
  textoLimpio,
} from "@/lib/designaciones";

// ------------------------------------------------------------------ Pestaña 4: Editar / eliminar por error
export function CorreccionTab({ data, version, onDone, onError }: TabProps) {
  const abierto = data.abierto;
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Editar / eliminar designación por error</h3>
      <FeedbackBox
        feedback={{
          tone: "warning",
          text:
            "Esta pestaña es solo para corregir errores de carga de una designación. Los cambios realizados acá NO quedan " +
            "registrados en Movimientos ni en el Resumen docente. Si el cambio es real durante el período, usá la pestaña " +
            "'Modificar / finalizar designación'.",
        }}
      />
      {!abierto ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay período abierto." }} />
      ) : (
        <CorreccionLista data={data} abierto={abierto} version={version} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

// Hasta visible = vencimiento previsto vigente (fecha_hasta_prevista; si está vacío, fecha_hasta).
const hastaCorreccion = (d: Designacion) =>
  String(d.fecha_hasta_prevista ?? "").trim() ? d.fecha_hasta_prevista : d.fecha_hasta;

function CorreccionLista({
  data,
  abierto,
  version,
  onDone,
  onError,
}: {
  data: Overview;
  abierto: Periodo;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const { data: pd, error } = usePeriodo(abierto.id, version, onError);
  const [q, setQ] = useState("");
  const [todas, setTodas] = useState(false);
  const filas = useMemo(
    () =>
      filtrar(pd?.designaciones ?? [], q, ["nombre_completo", "cuil", "cargo", "dedicacion", "tipo_designacion", "acto_administrativo", "estado"]),
    [pd, q]
  );
  if (error) return <FeedbackBox feedback={{ tone: "error", text: error }} />;
  if (!pd) return <Caption>Cargando designaciones del período abierto…</Caption>;
  if (pd.designaciones.length === 0) {
    return <FeedbackBox feedback={{ tone: "info", text: "No hay designaciones para editar/eliminar en el período abierto." }} />;
  }
  // Firma v224: ids visibles + "seleccionar todas". Si cambia, la grilla se reinicia como en el certificado.
  const firma = `${filas.map((f) => f.id).join("|")}|all=${todas ? 1 : 0}|v=${version}`;
  return (
    <div className="space-y-5">
      <Field label="Buscar designación a corregir">
        <TextInput value={q} onChange={setQ} placeholder="Docente, CUIL, cargo, dedicación o tipo" />
      </Field>
      {filas.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay designaciones que coincidan con la búsqueda." }} />
      ) : (
        <>
          {data.permisos.puede_borrar && (
            <div title="Marca para eliminación todas las filas visibles con el filtro actual. No elimina nada hasta que confirmes y presiones el botón de eliminación masiva.">
              <Check checked={todas} onChange={setTodas} label="Seleccionar todas las designaciones mostradas para eliminar" />
            </div>
          )}
          <GrillaCorreccion key={firma} data={data} abierto={abierto} filas={filas} todas={todas} version={version} onDone={onDone} onError={onError} />
        </>
      )}
    </div>
  );
}

type FilaGrilla = Designacion & { _editar: string; _eliminar: string; _hasta: string | null };

const COLS_GRILLA: Col<FilaGrilla>[] = [
  { key: "_editar", label: "Editar / eliminar" },
  { key: "_eliminar", label: "Eliminar" },
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "cargo", label: "Cargo" },
  { key: "dedicacion", label: "Dedicación" },
  { key: "horas", label: "Hs." },
  { key: "tipo_designacion", label: "Tipo" },
  { key: "acto_administrativo", label: "Acto administrativo" },
  { key: "ad_honorem", label: "Ad Honorem" },
  { key: "funcion_no_docente", label: "Función no docente" },
  { key: "estado", label: "Estado" },
  { key: "fecha_desde", label: "Desde" },
  { key: "_hasta", label: "Hasta" },
];

function GrillaCorreccion({
  data,
  abierto,
  filas,
  todas,
  version,
  onDone,
  onError,
}: {
  data: Overview;
  abierto: Periodo;
  filas: Designacion[];
  todas: boolean;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const p = data.permisos;
  const [editar, setEditar] = useState<Set<number>>(new Set());
  const [eliminar, setEliminar] = useState<Set<number>>(() => new Set(todas && p.puede_borrar ? filas.map((f) => f.id) : []));
  const [edits, setEdits] = useState<Record<number, { desde: string; hasta: string }>>({});
  const [confirmarMasivo, setConfirmarMasivo] = useState(false);
  const fechas = useAccion(onDone, onError);
  const masivo = useAccion(onDone, onError);

  const original = (d: Designacion) => ({ desde: safeDate(d.fecha_desde, ""), hasta: safeDate(hastaCorreccion(d), "") });
  const valor = (d: Designacion) => edits[d.id] ?? original(d);
  const rows: FilaGrilla[] = filas.map((d) => ({ ...d, _editar: "", _eliminar: "", _hasta: hastaCorreccion(d) }));
  const cols = COLS_GRILLA.filter((c) => c.key !== "_eliminar" || p.puede_borrar);

  const { cambios, errores } = useMemo(() => {
    const cambios: { id: number; huella: string; desde: string; hasta: string }[] = [];
    const errores: string[] = [];
    for (const d of filas) {
      const e = edits[d.id];
      if (!e) continue;
      const o = { desde: safeDate(d.fecha_desde, ""), hasta: safeDate(hastaCorreccion(d), "") };
      if (e.desde === o.desde && e.hasta === o.hasta) continue;
      if (!e.desde || !e.hasta) errores.push(`Designación ID ${d.id}: Desde y Hasta son obligatorios.`);
      else if (e.desde > e.hasta) errores.push(`Designación ID ${d.id}: Desde no puede ser posterior a Hasta.`);
      else cambios.push({ id: d.id, huella: d.huella, desde: e.desde, hasta: e.hasta });
    }
    return { cambios, errores };
  }, [edits, filas]);

  const toggle = (set: Set<number>, id: number, v: boolean) => {
    const next = new Set(set);
    if (v) next.add(id);
    else next.delete(id);
    return next;
  };
  const aEliminar = filas.filter((f) => eliminar.has(f.id));
  const aEditar = filas.filter((f) => editar.has(f.id));
  // La corrección detallada refleja las fechas tal como se ven en la grilla aunque no se hayan guardado.
  const filaDetalle: Designacion | null =
    aEditar.length === 1
      ? (() => {
          const v = valor(aEditar[0]);
          return {
            ...aEditar[0],
            fecha_desde: v.desde || aEditar[0].fecha_desde,
            ...(v.hasta ? { fecha_hasta: v.hasta, fecha_hasta_prevista: v.hasta } : {}),
          };
        })()
      : null;

  return (
    <div className="space-y-5">
      <p className="text-sm font-medium text-slate-700">Designaciones encontradas</p>
      <Caption>
        Resultados encontrados: {filas.length}. Podés corregir directamente &apos;Desde&apos; y &apos;Hasta&apos; y guardar todos los
        cambios juntos. El acto administrativo se vincula desde el repositorio. Para borrar varias, marcá la columna
        &apos;Eliminar&apos; o usá &apos;Seleccionar todas las designaciones mostradas&apos;. La columna &apos;Editar / eliminar&apos; sigue
        siendo para abrir la corrección detallada de una sola fila.
      </Caption>
      <Tabla
        rows={rows}
        cols={cols}
        rowKey={(d) => String(d.id)}
        render={(d, key) => {
          if (key === "_editar" || key === "_eliminar") {
            const set = key === "_editar" ? editar : eliminar;
            const setter = key === "_editar" ? setEditar : setEliminar;
            return (
              <input
                type="checkbox"
                aria-label={`${key === "_editar" ? "Editar / eliminar" : "Eliminar"} designación ${d.id}`}
                className="h-4 w-4 accent-brand-600"
                checked={set.has(d.id)}
                onChange={(e) => setter(toggle(set, d.id, e.target.checked))}
              />
            );
          }
          if (key === "fecha_desde" || key === "_hasta") {
            const v = valor(d);
            const campo = key === "fecha_desde" ? "desde" : "hasta";
            if (!p.puede_escribir) return v[campo];
            return (
              <DateInput
                label={`${campo === "desde" ? "Desde" : "Hasta"} de la designación ${d.id}`}
                value={v[campo]}
                onChange={(nuevo) => setEdits((prev) => ({ ...prev, [d.id]: { ...valor(d), [campo]: nuevo } }))}
              />
            );
          }
          return undefined;
        }}
      />
      {errores.length > 0 && (
        <Aviso feedback={{ tone: "error", text: "No se pueden guardar los cambios de fechas:\n- " + errores.join("\n- ") }} />
      )}
      {fechas.feedback && <Aviso feedback={fechas.feedback} />}
      {p.puede_escribir && (
        <div className="flex flex-wrap items-center gap-4">
          <PrimaryButton
            busy={fechas.busy}
            disabled={cambios.length === 0 || errores.length > 0}
            onClick={() => fechas.run(() => post<WriteResult>("fechas", { cambios }), () => setEdits({}))}
          >
            💾 Guardar fechas
          </PrimaryButton>
          <Caption>{cambios.length ? `Filas con cambios pendientes de guardar: ${cambios.length}` : "No hay cambios directos pendientes."}</Caption>
        </div>
      )}

      {p.puede_borrar && aEliminar.length > 0 && (
        <div className="space-y-3">
          <hr className="border-slate-200" />
          <FeedbackBox
            feedback={{
              tone: "error",
              text:
                `⚠️ Tenés ${aEliminar.length} designación/es seleccionada/s para eliminar. Esta operación es destructiva, no ` +
                "genera movimientos y elimina también los movimientos que correspondan únicamente a esas cargas erróneas.",
            }}
          />
          <Check
            checked={confirmarMasivo}
            onChange={setConfirmarMasivo}
            label={`Confirmo que las ${aEliminar.length} designación/es seleccionada/s fueron cargadas por error y quiero eliminarlas definitivamente.`}
          />
          {masivo.feedback && <Aviso feedback={masivo.feedback} />}
          <PrimaryButton
            tone="danger"
            busy={masivo.busy}
            disabled={!confirmarMasivo}
            onClick={() =>
              masivo.run(() =>
                post<WriteResult>("eliminar-masivo", {
                  seleccion: aEliminar.map((f) => ({ id: f.id, huella: f.huella })),
                  confirmar: true,
                })
              )
            }
          >
            🗑️ Eliminar {aEliminar.length} designación/es seleccionada/s
          </PrimaryButton>
        </div>
      )}

      {aEditar.length > 1 && (
        <FeedbackBox
          feedback={{
            tone: "warning",
            text: "Marcá una sola designación en 'Editar / eliminar' para continuar con la corrección completa o la eliminación.",
          }}
        />
      )}
      {filaDetalle && (
        <CorreccionDetalle key={filaDetalle.id} data={data} abierto={abierto} fila={filaDetalle} version={version} onDone={onDone} onError={onError} />
      )}
    </div>
  );
}

const ACCIONES = ["Editar datos cargados por error", "Eliminar designación cargada por error"];

function CorreccionDetalle({
  data,
  abierto,
  fila,
  onDone,
  onError,
}: {
  data: Overview;
  abierto: Periodo;
  fila: Designacion;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const c = data.catalogos;
  const p = data.permisos;
  const hoy = hoyIso();
  const [accionError, setAccionError] = useState(ACCIONES[0]);
  const [cargo, setCargo] = useState(pick(c.cargos, fila.cargo));
  const [dedicacion, setDedicacion] = useState(pick(c.dedicaciones, fila.dedicacion));
  const [tipo, setTipo] = useState(pick(c.tipos, fila.tipo_designacion));
  const [adh, setAdh] = useState(pick(c.ad_honorem, fila.ad_honorem || "No"));
  const [funcion, setFuncion] = useState(esNoDocente(fila.funcion_no_docente));
  const [desde, setDesde] = useState(safeDate(fila.fecha_desde, safeDate(abierto.fecha_inicio, hoy)));
  const [hasta, setHasta] = useState(safeDate(fila.fecha_hasta_prevista || fila.fecha_hasta, safeDate(abierto.fecha_fin, hoy)));
  const [estado, setEstado] = useState(pick(c.estados, fila.estado || "Activa"));
  const [texto, setTexto] = useState(textoLimpio(fila.texto_funcion_no_docente));
  const [obs, setObs] = useState(fila.observaciones ?? "");
  const [confirmarCorr, setConfirmarCorr] = useState(false);
  const [confirmarDel, setConfirmarDel] = useState(false);
  const accion = useAccion(onDone, onError);
  const horas = horasSegunDedicacion(c.horas_por_dedicacion, dedicacion, fila.horas ?? 0);
  const acto = fila.acto_administrativo || "Pendiente de vincular";

  function corregir() {
    if (funcion && !textoLimpio(texto)) {
      accion.setFeedback({ tone: "error", text: "Completá las funciones no docentes antes de guardar la corrección." });
      return;
    }
    if (!confirmarCorr) {
      accion.setFeedback({ tone: "error", text: "Tenés que confirmar que es una corrección de error." });
      return;
    }
    accion.run(() =>
      post<WriteResult>("corregir", {
        id: fila.id,
        huella: fila.huella,
        cargo,
        dedicacion,
        tipo_designacion: tipo,
        ad_honorem: adh,
        funcion_no_docente: funcion,
        fecha_desde: desde,
        fecha_hasta: hasta,
        estado,
        texto_funcion_no_docente: funcion ? texto : "",
        observaciones: obs,
        confirmar: true,
      })
    );
  }

  function eliminar() {
    if (!confirmarDel) {
      accion.setFeedback({ tone: "error", text: "Primero confirmá la eliminación por error." });
      return;
    }
    accion.run(() => post<WriteResult>("eliminar", { id: fila.id, huella: fila.huella, confirmar: true }));
  }

  return (
    <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            `Designación seleccionada: ${fila.nombre_completo} - ${fila.cargo} - ${fila.dedicacion} - ${fila.horas ?? ""} hs - ` +
            `${fila.tipo_designacion} - Acto administrativo: ${acto} - Ad Honorem: ${fila.ad_honorem} - Estado: ${fila.estado}`,
        }}
      />
      <div>
        <p className="mb-2 text-xs font-medium text-slate-500">Qué querés hacer</p>
        <Radio name={`accion_error_desig_${fila.id}`} value={accionError} options={ACCIONES} onChange={setAccionError} />
      </div>
      {accionError === ACCIONES[0] ? (
        <>
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-3">
              <Field label="Cargo">
                <Select value={cargo} options={c.cargos} onChange={setCargo} />
              </Field>
              <Field label="Dedicación">
                <Select value={dedicacion} options={c.dedicaciones} onChange={setDedicacion} />
              </Field>
              <Caption>
                Horas automáticas según dedicación: <b>{horas} hs</b>
              </Caption>
              <Field label="Tipo designación">
                <Select value={tipo} options={c.tipos} onChange={setTipo} />
              </Field>
              <Caption>
                Acto administrativo: {acto}. Para corregirlo, usá el vínculo al repositorio en &apos;Designaciones del período&apos;.
              </Caption>
            </div>
            <div className="space-y-3">
              <Field label="Ad Honorem">
                <Select value={adh} options={c.ad_honorem} onChange={setAdh} />
              </Field>
              <Check checked={funcion} onChange={setFuncion} label="Designación para funciones no docentes" />
              <Field label="Fecha desde">
                <DateInput value={desde} onChange={setDesde} />
              </Field>
              <Field label="Fecha hasta">
                <DateInput value={hasta} onChange={setHasta} />
              </Field>
              <Field label="Estado">
                <Select value={estado} options={c.estados} onChange={setEstado} />
              </Field>
            </div>
          </div>
          {funcion && (
            <FuncionNoDocenteTexto
              label="Funciones no docentes corregidas"
              value={texto}
              onChange={setTexto}
              ayuda={
                <>
                  La disposición ya aporta <b>«…el cumplimiento de funciones»</b>. Corregí únicamente la continuación que debe ir
                  después de esa frase.
                </>
              }
              preview={(t) => `Vista previa: «…el cumplimiento de funciones ${t}.»`}
            />
          )}
          <Field label="Observaciones corregidas">
            <Textarea value={obs} onChange={setObs} />
          </Field>
          <Check
            checked={confirmarCorr}
            onChange={setConfirmarCorr}
            label="Confirmo que esto es una corrección de error y que no debe quedar como movimiento registrado."
          />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {p.puede_escribir && (
            <PrimaryButton onClick={corregir} busy={accion.busy}>
              🛠️ Guardar corrección sin registrar movimiento
            </PrimaryButton>
          )}
        </>
      ) : (
        <>
          <FeedbackBox
            feedback={{
              tone: "error",
              text: "Esta eliminación es destructiva y no quedará en el historial. Usala solo si la designación fue cargada por error.",
            }}
          />
          <Check
            checked={confirmarDel}
            onChange={setConfirmarDel}
            label="Confirmo que quiero eliminar esta designación por error de carga y que no debe quedar movimiento registrado."
          />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {p.puede_borrar && (
            <PrimaryButton tone="danger" onClick={eliminar} busy={accion.busy}>
              🗑️ Eliminar designación sin registrar movimiento
            </PrimaryButton>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Pestaña 5: Carga rápida
type Fila = Record<string, string | number | null>;

export function CargaRapidaTab({ data, version, onDone, onError }: TabProps) {
  const [texto, setTexto] = useState("");
  const [preview, setPreview] = useState<Carga | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [excelBusy, setExcelBusy] = useState(false);
  const [excelError, setExcelError] = useState<string | null>(null);
  const accion = useAccion(onDone, onError);

  // parsear_designaciones_pegadas + docentes inexistentes + duplicados, con los datos actuales (cada rerun).
  useEffect(() => {
    let cancel = false;
    const t = setTimeout(() => {
      if (!texto.trim()) {
        setPreview(null);
        setPreviewError(null);
        return;
      }
      post<Carga>("carga-rapida/previsualizar", { texto })
        .then((r) => {
          if (cancel) return;
          setPreview(r);
          setPreviewError(null);
        })
        .catch((e) => !cancel && setPreviewError(onError(e).message));
    }, 400);
    return () => {
      cancel = true;
      clearTimeout(t);
    };
  }, [texto, version, onError]);

  async function modelo() {
    setExcelBusy(true);
    setExcelError(null);
    try {
      download(await designacionesApi.modeloExcel());
    } catch (e) {
      setExcelError(`No se pudo generar el Excel modelo de designaciones: ${onError(e).message}`);
    } finally {
      setExcelBusy(false);
    }
  }

  const filas = preview?.filas ?? [];
  const inexistentes = preview?.inexistentes ?? [];
  const duplicados = preview?.duplicados ?? [];

  function cargar() {
    if (inexistentes.length) {
      accion.setFeedback({ tone: "error", text: "No se cargó nada. Primero registrá los docentes que faltan." });
      return;
    }
    if (duplicados.length && !confirmar) {
      accion.setFeedback({
        tone: "error",
        text: "No se cargó nada. Hay duplicados o errores: marcá la confirmación si realmente querés avanzar.",
      });
      return;
    }
    accion.run(() => post<WriteResult>("carga-rapida", { texto, confirmar_duplicados: duplicados.length > 0 && confirmar }));
  }

  const colsDe = (rows: Fila[]): Col<Fila>[] => (rows.length ? Object.keys(rows[0]).map((k) => ({ key: k, label: k })) : []);

  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Carga rápida de designaciones</h3>
      {!data.abierto && (
        <FeedbackBox
          feedback={{
            tone: "warning",
            text: "Primero tenés que crear o abrir un período. Si la tabla no trae columna período, se usará el período abierto.",
          }}
        />
      )}
      <div className="space-y-2">
        {excelError && <FeedbackBox feedback={{ tone: "warning", text: excelError }} />}
        <PrimaryButton tone="secondary" busy={excelBusy} onClick={modelo}>
          📥 Descargar Excel modelo para designaciones
        </PrimaryButton>
        <Caption>
          El modelo incluye los docentes del departamento, los períodos existentes y listas desplegables para cargo, dedicación,
          tipo, condición ad honorem y estado. Al seleccionar la dedicación, Horas se calcula automáticamente; al seleccionar el
          docente, el CUIL también se completa automáticamente.
        </Caption>
      </div>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Pegá una tabla copiada desde Excel. Encabezados admitidos: periodo, cuil, cargo, dedicacion, horas, tipo_designacion, " +
            "numero_resolucion, ad_honorem, fecha_desde, fecha_hasta, estado, observaciones. La columna horas se conserva por " +
            "compatibilidad pero se recalcula siempre desde dedicacion. Si no pegás período, se usa el período abierto.",
        }}
      />
      <Field label="Pegá acá las designaciones">
        <Textarea value={texto} onChange={setTexto} rows={10} />
      </Field>
      {previewError && <Aviso feedback={{ tone: "error", text: previewError }} />}
      {filas.length > 0 ? (
        <div className="space-y-4">
          <h4 className="text-base font-semibold text-slate-800">Vista previa</h4>
          <Tabla rows={filas} cols={colsDe(filas)} rowKey={(r) => String(filas.indexOf(r))} maxHeight="max-h-80" />
          <Caption>Filas detectadas: {filas.length}</Caption>
          {inexistentes.length > 0 && (
            <>
              <FeedbackBox
                feedback={{
                  tone: "error",
                  text: "Hay designaciones con CUIL que no existen en la base maestra. Esas filas no se pueden cargar.",
                }}
              />
              <Tabla
                rows={inexistentes as unknown as Fila[]}
                cols={[
                  { key: "fila_pegada", label: "fila_pegada" },
                  { key: "cuil", label: "cuil" },
                  { key: "motivo", label: "motivo" },
                ]}
                rowKey={(r) => String(r.fila_pegada)}
                maxHeight="max-h-60"
              />
            </>
          )}
          {duplicados.length > 0 && (
            <>
              <FeedbackBox
                feedback={{
                  tone: "warning",
                  text:
                    "Hay designaciones ya existentes, repetidas dentro de la tabla pegada o con período inexistente. El sistema no " +
                    "las cargará dos veces sin confirmación.",
                }}
              />
              <Tabla rows={duplicados} cols={colsDe(duplicados)} rowKey={(r) => String(r.fila_pegada)} maxHeight="max-h-60" />
              <Check
                checked={confirmar}
                onChange={setConfirmar}
                label="Confirmo que quiero cargar igualmente las designaciones duplicadas válidas"
              />
            </>
          )}
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {data.permisos.puede_escribir && (
            <PrimaryButton onClick={cargar} busy={accion.busy}>
              📥 Cargar designaciones pegadas
            </PrimaryButton>
          )}
        </div>
      ) : (
        preview?.aviso && <FeedbackBox feedback={{ tone: "warning", text: preview.aviso }} />
      )}
    </section>
  );
}
