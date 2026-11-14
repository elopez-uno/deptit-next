"use client";

// Módulo Resoluciones y respaldos (B13-FIX02, render_repositorio_documental_v249, entry l. 51514-52129): las 3 pestañas
// certificadas en su orden original. El PDF vive en la base (bytea): se sube por multipart (sin base64, D-AK1) y se
// descarga bajo demanda (D-AK12); el listado nunca trae el binario. No hay ZIP, Excel, importación, exportación,
// versionado, edición de número/fecha/tipo ni borrado del PDF o de dependencias.
// La UI solo oculta lo que el rol no puede hacer (Eliminar: solo superadmin, D-AK6): FastAPI vuelve a autorizar todo.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { Aviso, Caption, DateInput, Tabla, filtrar, hoyIso } from "@/components/designaciones-shared";
import { Check, Details, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type Detalle,
  type FilaDesignacion,
  type FilaDocumento,
  type FilaProyecto,
  type Overview,
  type TablaDesignaciones,
  type TablaDocentes,
  type WriteResult,
  MAX_PDF_BYTES,
  descargarPdf,
  post,
  resolucionesApi,
  subir,
} from "@/lib/resoluciones-respaldos";

const CATEGORIA_DESIGNACION = "Designación docente";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;
type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Texto con **negritas** de st.caption / st.write (sin HTML del servidor).
function Md({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}
    </>
  );
}

function kb(file: File) {
  return `${(file.size / 1024).toFixed(1)} KB`;
}

function useAccion(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  async function run(fn: () => Promise<WriteResult>, recargar = true) {
    setBusy(true);
    setFeedback(null);
    try {
      const r = await fn();
      if (recargar) await onDone({ tone: r.tono ?? "success", text: r.mensaje });
      else setFeedback({ tone: r.tono ?? "success", text: r.mensaje });
      return r;
    } catch (e) {
      setFeedback(feedbackDe(onError(e)));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, feedback, setFeedback, run };
}

function Seccion({ children }: { children: React.ReactNode }) {
  return <h4 className="pt-2 text-base font-semibold text-slate-800">{children}</h4>;
}

function SelectorPdf({ label, archivo, onChange }: { label: string; archivo: File | null; onChange: (f: File | null) => void }) {
  return (
    <Field label={label}>
      <input
        type="file"
        accept="application/pdf,.pdf"
        aria-label={label}
        className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-800"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {archivo && <Caption>{`Archivo: ${archivo.name} — ${kb(archivo)}`}</Caption>}
    </Field>
  );
}

// ------------------------------------------------------------------ 📚 Repositorio (l. 51527-51719)
const COLUMNAS: { key: keyof FilaDocumento & string; label: string }[] = [
  { key: "fecha", label: "Fecha" },
  { key: "tipo_documento", label: "Tipo" },
  { key: "dependencia_emisora", label: "Dependencia emisora" },
  { key: "categoria", label: "Respalda" },
  { key: "numero", label: "N°" },
  { key: "periodo", label: "Período" },
  { key: "cantidad_docentes", label: "Cant. docentes" },
  { key: "docentes", label: "Docentes vinculados" },
  { key: "cantidad_proyectos", label: "Cant. proyectos" },
  { key: "proyectos", label: "Proyectos vinculados" },
  { key: "referencia", label: "Referencia" },
  { key: "titulo", label: "Título" },
  { key: "estado_pdf", label: "Estado PDF" },
  { key: "archivo_nombre", label: "Archivo" },
  { key: "tamano_kb", label: "Tamaño (KB)" },
];

function RepositorioTab({ data, version, onDone, onError }: TabProps) {
  const rep = data.repositorio;
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("Todos");
  const [categoria, setCategoria] = useState("Todas");
  const [dependencia, setDependencia] = useState("Todas");
  const [sel, setSel] = useState<number | null>(null);

  const vista = useMemo(() => {
    let filas = rep.filas;
    if (tipo !== "Todos") filas = filas.filter((f) => String(f.tipo_documento) === tipo);
    if (categoria !== "Todas") filas = filas.filter((f) => String(f.categoria) === categoria);
    if (dependencia !== "Todas") filas = filas.filter((f) => String(f.dependencia_emisora ?? "") === dependencia);
    return filtrar(filas, buscar, rep.busqueda);
  }, [rep, tipo, categoria, dependencia, buscar]);
  const seleccionada = sel !== null && vista.some((f) => f.id === sel) ? sel : null;

  if (!rep.filas.length) return <FeedbackBox feedback={{ tone: "info", text: rep.vacio }} />;
  return (
    <section className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_1.25fr]">
        <Field label="Buscar">
          <TextInput value={buscar} onChange={setBuscar} placeholder="Número, dependencia, docente, CUIL, proyecto, título..." />
        </Field>
        <Field label="Tipo">
          <Select value={tipo} options={rep.filtros.tipos} onChange={setTipo} />
        </Field>
        <Field label="Categoría">
          <Select value={categoria} options={rep.filtros.categorias} onChange={setCategoria} />
        </Field>
        <Field label="Dependencia">
          <Select value={dependencia} options={rep.filtros.dependencias} onChange={setDependencia} />
        </Field>
      </div>
      {vista.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: rep.sin_coincidencias }} />
      ) : (
        <>
          <p className="text-sm font-semibold text-slate-800">Documentación respaldatoria</p>
          <Tabla rows={vista} cols={COLUMNAS} rowKey={(r) => String(r.id)} selected={seleccionada === null ? null : String(seleccionada)} onSelect={(k) => setSel(Number(k))} />
          {seleccionada !== null && (
            <DocumentoSeleccionado key={`${seleccionada}-${version}`} id={seleccionada} data={data} version={version} onDone={onDone} onError={onError} />
          )}
        </>
      )}
    </section>
  );
}

function DocumentoSeleccionado({ id, data, onDone, onError }: TabProps & { id: number }) {
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const [depSel, setDepSel] = useState<string>("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [confirmar, setConfirmar] = useState(false);
  const [bajando, setBajando] = useState(false);
  const dep = useAccion(onDone, onError);
  const pdf = useAccion(onDone, onError);
  const borrar = useAccion(onDone, onError);

  useEffect(() => {
    let cancel = false;
    post<Detalle>("documento", { id })
      .then((d) => {
        if (cancel) return;
        setDetalle(d);
        setDepSel(d.dependencias[d.dependencia_indice]?.etiqueta ?? "");
      })
      .catch((e) => !cancel && setError(feedbackDe(onError(e))));
    return () => {
      cancel = true;
    };
  }, [id, onError]);

  if (error) return <FeedbackBox feedback={error} />;
  if (!detalle) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="h-4 w-4 text-brand-600" /> Cargando documento…
      </div>
    );
  }
  const f = detalle.fila;
  const puedeEscribir = data.permisos.puede_escribir;
  const puedeBorrar = data.permisos.puede_borrar;
  const reemplazar = detalle.tiene_pdf;

  async function bajar() {
    setBajando(true);
    pdf.setFeedback(null);
    try {
      await descargarPdf(id);
    } catch (e) {
      pdf.setFeedback(feedbackDe(onError(e)));
    } finally {
      setBajando(false);
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <Seccion>Documento seleccionado</Seccion>
      <p className="text-sm text-slate-800">
        <strong>{detalle.encabezado}</strong> — {f.categoria}
      </p>
      {f.dependencia_emisora ? (
        <p className="text-sm text-slate-700">
          <strong>Dependencia emisora:</strong> {f.dependencia_emisora}
        </p>
      ) : (
        <FeedbackBox feedback={{ tone: "warning", text: detalle.aviso_dependencia }} />
      )}
      {f.cantidad_docentes > 0 && (
        <p className="text-sm text-slate-700">
          <strong>{`Docentes vinculados (${f.cantidad_docentes}):`}</strong> {f.docentes}
        </p>
      )}
      {f.cantidad_proyectos > 0 && (
        <p className="text-sm text-slate-700">
          <strong>{`Proyectos vinculados (${f.cantidad_proyectos}):`}</strong> {f.proyectos}
        </p>
      )}
      {f.referencia && <Caption>{f.referencia}</Caption>}
      {f.detalle && <p className="text-sm text-slate-700">{f.detalle}</p>}
      {detalle.designacion_pendiente && <FeedbackBox feedback={{ tone: "warning", text: detalle.designacion_pendiente }} />}
      {puedeEscribir && detalle.relaciones?.docentes && <AgregarDocentes id={id} data={data} onDone={onDone} onError={onError} />}
      {detalle.designacion_docente && (
        <DesignacionesDelDocumento id={id} detalle={detalle} puedeEscribir={puedeEscribir} onDone={onDone} onError={onError} />
      )}
      {detalle.relaciones?.proyectos && (
        <ProyectosDelDocumento id={id} tipo={detalle.relaciones.proyectos} vinculados={detalle.proyectos_vinculados} puedeEscribir={puedeEscribir} onDone={onDone} onError={onError} />
      )}

      {puedeEscribir && detalle.dependencias.length > 0 && (
        <Details summary="🏛️ Asignar o corregir dependencia emisora" defaultOpen={!f.dependencia_emisora}>
          {dep.feedback && <Aviso feedback={dep.feedback} />}
          <Field label="Dependencia">
            <Select value={depSel} options={detalle.dependencias.map((o) => o.etiqueta)} onChange={setDepSel} />
          </Field>
          <PrimaryButton
            busy={dep.busy}
            onClick={() =>
              dep.run(() =>
                post<WriteResult>("documento/dependencia", {
                  id,
                  dependencia_id: detalle.dependencias.find((o) => o.etiqueta === depSel)?.id ?? null,
                })
              )
            }
          >
            💾 Guardar dependencia del documento
          </PrimaryButton>
        </Details>
      )}

      {pdf.feedback && <Aviso feedback={pdf.feedback} />}
      {reemplazar ? (
        <PrimaryButton tone="secondary" busy={bajando} onClick={bajar}>
          ⬇️ Descargar PDF
        </PrimaryButton>
      ) : (
        <FeedbackBox feedback={{ tone: "warning", text: detalle.pdf_pendiente }} />
      )}

      {puedeEscribir && (
        <Details summary={`📎 ${reemplazar ? "Reemplazar PDF" : "Adjuntar PDF pendiente"}`} defaultOpen={!reemplazar}>
          <div key={inputKey}>
            <SelectorPdf label="Seleccionar PDF" archivo={archivo} onChange={setArchivo} />
          </div>
          {archivo && (
            <PrimaryButton
              busy={pdf.busy}
              onClick={() => {
                if (archivo.size > MAX_PDF_BYTES) {
                  pdf.setFeedback({ tone: "error", text: "El PDF supera 50 MB." });
                  return;
                }
                void pdf.run(() => subir<WriteResult>("documento/adjuntar-pdf", { id }, archivo)).then((r) => {
                  if (r) {
                    setArchivo(null);
                    setInputKey((k) => k + 1);
                  }
                });
              }}
            >
              {`💾 ${reemplazar ? "Reemplazar PDF" : "Adjuntar PDF"}`}
            </PrimaryButton>
          )}
        </Details>
      )}

      {puedeBorrar && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          {borrar.feedback && <Aviso feedback={borrar.feedback} />}
          <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que quiero eliminar este acto/documento del repositorio" />
          <PrimaryButton
            tone="danger"
            busy={borrar.busy}
            disabled={!confirmar}
            onClick={() => borrar.run(() => post<WriteResult>("documento/eliminar", { id, confirmar: true }))}
          >
            🗑️ Eliminar documento
          </PrimaryButton>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 6A-B3: designaciones concretas de un acto
const etiquetaDesignacion = (d: FilaDesignacion) =>
  `ID ${d.id} · ${d.docente} · ${d.periodo || "sin período"} · ${d.cargo} · ${d.dedicacion} · ${d.tipo_designacion} · ` +
  `${d.fecha_desde || "?"} → ${d.fecha_hasta || "?"} · ${d.estado || "sin estado"}` +
  (d.funcion_no_docente ? " · función no docente" : "");

// Una casilla por designación (no se asume una sola por docente). Si una elegida ya respalda OTRO acto se muestra y se
// exige confirmar el reemplazo (una designación tiene un único acto vinculado).
function SelectorDesignaciones({
  filas,
  value,
  onChange,
  documentoId,
  reemplazar,
  onReemplazar,
  disabled,
}: {
  filas: FilaDesignacion[];
  value: Set<number>;
  onChange: (v: Set<number>) => void;
  documentoId: number | null;
  reemplazar: boolean;
  onReemplazar: (v: boolean) => void;
  disabled?: boolean;
}) {
  const ajenas = filas.filter((d) => value.has(d.id) && d.acto_documento_id !== null && d.acto_documento_id !== documentoId);
  return (
    <div className="space-y-2">
      {filas.map((d) => (
        <div key={d.id} className="rounded-lg border border-slate-200 px-3 py-2">
          <Check
            checked={value.has(d.id)}
            disabled={disabled}
            label={etiquetaDesignacion(d)}
            onChange={(v) => {
              const next = new Set(value);
              if (v) next.add(d.id);
              else next.delete(d.id);
              onChange(next);
            }}
          />
          <p className="ml-7 text-xs text-slate-500">
            {d.acto_documento_id === null
              ? "Acto vinculado actual: ninguno"
              : d.acto_documento_id === documentoId
                ? "Acto vinculado actual: este documento"
                : `Acto vinculado actual: ${d.acto_administrativo}`}
          </p>
        </div>
      ))}
      {ajenas.length > 0 && (
        <Check
          checked={reemplazar}
          disabled={disabled}
          onChange={onReemplazar}
          label={`Confirmo reemplazar el acto vinculado de ${ajenas.length} designación/es por este documento`}
        />
      )}
    </div>
  );
}

function DesignacionesDelDocumento({ id, detalle, puedeEscribir, onDone, onError }: { id: number; detalle: Detalle; puedeEscribir: boolean; onDone: OnDone; onError: OnError }) {
  const [sel, setSel] = useState<Set<number>>(() => new Set(detalle.designaciones.filter((d) => d.vinculada).map((d) => d.id)));
  const [reemplazar, setReemplazar] = useState(false);
  const accion = useAccion(onDone, onError);
  const vinculadas = detalle.designaciones.filter((d) => d.vinculada);
  return (
    <Details summary={`🔗 Designaciones respaldadas por este acto (${vinculadas.length})`} defaultOpen={vinculadas.length === 0}>
      <Caption>{detalle.caption_designaciones}</Caption>
      {detalle.designaciones.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: "Los docentes vinculados a este acto no tienen designaciones registradas." }} />
      ) : (
        <SelectorDesignaciones
          filas={detalle.designaciones}
          value={sel}
          onChange={setSel}
          documentoId={id}
          reemplazar={reemplazar}
          onReemplazar={setReemplazar}
          disabled={!puedeEscribir}
        />
      )}
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puedeEscribir && detalle.designaciones.length > 0 && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() => accion.run(() => post<WriteResult>("documento/designaciones", { id, designaciones: [...sel].sort((a, b) => a - b), reemplazar_vinculos: reemplazar }))}
        >
          💾 Guardar designaciones vinculadas
        </PrimaryButton>
      )}
    </Details>
  );
}

// 6A-B3: agregar docentes a un acto ya cargado, con el mismo selector (modo / período) del alta.
function AgregarDocentes({ id, data, onDone, onError }: { id: number; data: Overview; onDone: OnDone; onError: OnError }) {
  const alta = data.alta;
  const [modo, setModo] = useState(alta.modos_docentes[0]);
  const [perDoc, setPerDoc] = useState(alta.periodos_docentes[alta.periodo_docentes_indice]?.etiqueta ?? "");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const accion = useAccion(onDone, onError);
  const perDocId = alta.periodos_docentes.find((o) => o.etiqueta === perDoc)?.id ?? null;
  const cuerpo = modo === alta.modos_docentes[0] ? { modo } : { modo, periodo_id: perDocId };
  const docentes = useConsulta<TablaDocentes>("docentes", cuerpo, onError, modo === alta.modos_docentes[0] || perDocId !== null);
  const filas = docentes.data?.filas ?? [];
  return (
    <Details summary="👥 Agregar docentes a este acto" defaultOpen={false}>
      <Field label="Mostrar docentes de">
        <Select value={modo} options={alta.modos_docentes} onChange={(v) => { setModo(v); setSel(new Set()); }} />
      </Field>
      {modo !== alta.modos_docentes[0] && alta.periodos_docentes.length > 0 && (
        <Field label="Período / cuatrimestre">
          <Select value={perDoc} options={alta.periodos_docentes.map((o) => o.etiqueta)} onChange={(v) => { setPerDoc(v); setSel(new Set()); }} />
        </Field>
      )}
      {docentes.error && <Aviso feedback={docentes.error} />}
      {docentes.data?.aviso && <FeedbackBox feedback={{ tone: "warning", text: docentes.data.aviso }} />}
      {filas.length > 0 && (
        <Tabla
          rows={filas}
          cols={[
            { key: "Docente", label: "Docente" },
            { key: "CUIL", label: "CUIL" },
          ]}
          rowKey={(r) => r.CUIL}
          checked={sel}
          onCheck={(k, v) => {
            const next = new Set(sel);
            if (v) next.add(k);
            else next.delete(k);
            setSel(next);
          }}
          maxHeight="max-h-64"
        />
      )}
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      <PrimaryButton
        busy={accion.busy}
        disabled={sel.size === 0}
        onClick={() => accion.run(() => post<WriteResult>("documento/docentes", { id, ...cuerpo, docentes: [...sel] }))}
      >
        ➕ Agregar docentes seleccionados
      </PrimaryButton>
    </Details>
  );
}

// 6A-B3: proyectos de un acto de Investigación / Extensión (agregar y, con permiso de borrado, quitar).
function ProyectosDelDocumento({ id, tipo, vinculados, puedeEscribir, onDone, onError }: { id: number; tipo: "investigacion" | "extension"; vinculados: number[]; puedeEscribir: boolean; onDone: OnDone; onError: OnError }) {
  const proyectos = useConsulta<{ filas: FilaProyecto[]; aviso: string }>("proyectos", { tipo }, onError, true);
  const [sel, setSel] = useState<Set<number>>(() => new Set(vinculados));
  const accion = useAccion(onDone, onError);
  const filas = proyectos.data?.filas ?? [];
  const extra = vinculados.filter((v) => !filas.some((f) => f.ID === v)); // vinculados que ya no figuran en el catálogo
  return (
    <Details summary={`🔬 Proyectos vinculados a este acto (${vinculados.length})`} defaultOpen={false}>
      {proyectos.error && <Aviso feedback={proyectos.error} />}
      {proyectos.data?.aviso && <FeedbackBox feedback={{ tone: "warning", text: proyectos.data.aviso }} />}
      <div className="max-h-72 space-y-1 overflow-auto">
        {[...filas.map((f) => ({ id: f.ID, label: `${f.Código ? `[${f.Código}] ` : ""}${f.Proyecto} · ${f.Estado}` })), ...extra.map((v) => ({ id: v, label: `Proyecto ${v}` }))].map((p) => (
          <Check
            key={p.id}
            checked={sel.has(p.id)}
            disabled={!puedeEscribir}
            label={p.label}
            onChange={(v) => {
              const next = new Set(sel);
              if (v) next.add(p.id);
              else next.delete(p.id);
              setSel(next);
            }}
          />
        ))}
      </div>
      <Caption>Quitar un proyecto requiere permiso de borrado (superadmin), igual que en Investigación / Extensión. Debe quedar al menos uno.</Caption>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puedeEscribir && (
        <PrimaryButton busy={accion.busy} disabled={sel.size === 0} onClick={() => accion.run(() => post<WriteResult>("documento/proyectos", { id, proyectos: [...sel].sort((a, b) => a - b) }))}>
          💾 Guardar proyectos vinculados
        </PrimaryButton>
      )}
    </Details>
  );
}

// ------------------------------------------------------------------ ➕ Cargar acto (l. 51721-52079)
function useConsulta<T>(path: string, body: unknown, onError: OnError, enabled: boolean) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const seq = useRef(0);
  const key = JSON.stringify(body);
  useEffect(() => {
    if (!enabled) return;
    const n = ++seq.current;
    post<T>(path, JSON.parse(key))
      .then((d) => {
        if (n === seq.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (n === seq.current) {
          setData(null);
          setError(feedbackDe(onError(e)));
        }
      });
  }, [path, key, onError, enabled]);
  return { data: enabled ? data : null, error: enabled ? error : null };
}

function CargarActoTab({ data, onDone, onError }: TabProps) {
  const alta = data.alta;
  const t = alta.textos;
  const [categoria, setCategoria] = useState(alta.categorias[0]);
  const sugerido = categoria === "Proyecto de Investigación" ? "Disposición" : "Resolución";
  const [tipoPor, setTipoPor] = useState<Record<string, string>>({});
  const tipo = tipoPor[categoria] ?? sugerido;
  const [depPor, setDepPor] = useState<Record<string, string>>({});
  const depKey = `${tipo}|${categoria}`;
  const dependencia = depPor[depKey] ?? alta.dependencias[0]?.etiqueta ?? "Seleccionar dependencia";
  const dependenciaId = alta.dependencias.find((o) => o.etiqueta === dependencia)?.id ?? null;
  const [numero, setNumero] = useState("");
  const [fecha, setFecha] = useState(hoyIso());
  const [periodo, setPeriodo] = useState(alta.periodos[0]?.etiqueta ?? "Sin período");
  const [modo, setModo] = useState(alta.modos_docentes[0]);
  const [perDoc, setPerDoc] = useState(alta.periodos_docentes[alta.periodo_docentes_indice]?.etiqueta ?? "");
  const [buscarDoc, setBuscarDoc] = useState("");
  const [buscarProy, setBuscarProy] = useState("");
  const [docSel, setDocSel] = useState<Set<string>>(new Set());
  const [proySel, setProySel] = useState<Set<string>>(new Set());
  const [todosDoc, setTodosDoc] = useState(false);
  const [todosProy, setTodosProy] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [detallePor, setDetallePor] = useState<Record<string, string>>({});
  const detalle = detallePor[categoria] ?? "";
  const [observaciones, setObservaciones] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const guardar = useAccion(onDone, onError);

  const requiereDocentes = alta.categorias_docente.includes(categoria);
  const requiereProyectos = alta.categorias_proyecto.includes(categoria);
  const proyectoTipo = categoria === "Proyecto de Extensión" ? "extension" : "investigacion";
  const perDocId = alta.periodos_docentes.find((o) => o.etiqueta === perDoc)?.id ?? null;
  const docentes = useConsulta<TablaDocentes>(
    "docentes",
    modo === alta.modos_docentes[0] ? { modo } : { modo, periodo_id: perDocId },
    onError,
    requiereDocentes && (modo === alta.modos_docentes[0] || perDocId !== null)
  );
  const proyectos = useConsulta<{ filas: FilaProyecto[]; aviso: string }>("proyectos", { tipo: proyectoTipo }, onError, requiereProyectos);

  const filasDoc = useMemo(() => filtrar(docentes.data?.filas ?? [], buscarDoc, ["Docente", "CUIL"]), [docentes.data, buscarDoc]);
  const filasProy = useMemo(
    () => filtrar(proyectos.data?.filas ?? [], buscarProy, ["Código", "Proyecto", "Estado", "Departamento creador"]),
    [proyectos.data, buscarProy]
  );
  // data_editor con clave = firma de las filas mostradas: cambiar el filtro reinicia la selección (como el certificado).
  const firmaDoc = `${filasDoc.map((f) => f.CUIL).join("|")}|${modo}|${perDocId}`;
  const firmaProy = `${filasProy.map((f) => f.ID).join("|")}|${proyectoTipo}`;
  const [firmaDocActual, setFirmaDocActual] = useState(firmaDoc);
  const [firmaProyActual, setFirmaProyActual] = useState(firmaProy);
  if (firmaDoc !== firmaDocActual) {
    setFirmaDocActual(firmaDoc);
    setDocSel(new Set());
  }
  if (firmaProy !== firmaProyActual) {
    setFirmaProyActual(firmaProy);
    setProySel(new Set());
  }
  const docentesElegidos = filasDoc.filter((f) => todosDoc || docSel.has(f.CUIL));
  const proyectosElegidos = filasProy.filter((f) => todosProy || proySel.has(String(f.ID)));
  // 6A-B3: en "Designación docente", designaciones concretas (ids reales) de los docentes elegidos.
  const esDesignacion = categoria === CATEGORIA_DESIGNACION;
  const cuilesElegidos = docentesElegidos.map((d) => d.CUIL);
  const designaciones = useConsulta<TablaDesignaciones>("designaciones", { cuiles: cuilesElegidos }, onError, esDesignacion && cuilesElegidos.length > 0);
  const [desSel, setDesSel] = useState<Set<number>>(new Set());
  const [reemplazar, setReemplazar] = useState(false);
  const firmaDes = `${categoria}|${cuilesElegidos.join("|")}`;
  const [firmaDesActual, setFirmaDesActual] = useState(firmaDes);
  if (firmaDes !== firmaDesActual) {
    setFirmaDesActual(firmaDes);
    setDesSel(new Set());
    setReemplazar(false);
  }
  const filasDes = designaciones.data?.filas ?? [];
  const desElegidas = filasDes.filter((d) => desSel.has(d.id)).map((d) => d.id);

  let referencia = "";
  if (requiereDocentes && docentesElegidos.length) {
    referencia = `${categoria}: ${docentesElegidos.map((d) => `${d.Docente.trim()} — CUIL ${d.CUIL.trim()}`).join("; ")}`;
  } else if (requiereProyectos && proyectosElegidos.length) {
    referencia = `${categoria}: ${proyectosElegidos.map((p) => (p.Código.trim() ? `[${p.Código.trim()}] ` : "") + p.Proyecto.trim()).join("; ")}`;
  }
  const faltaDocente = requiereDocentes && docentesElegidos.length === 0;
  const faltaProyecto = requiereProyectos && proyectosElegidos.length === 0;
  const faltaDependencia = alta.tipos_con_dependencia.includes(tipo) && dependenciaId === null;

  if (!data.permisos.puede_escribir) return <FeedbackBox feedback={{ tone: "warning", text: t.solo_lectura }} />;

  function enviar() {
    if (archivo && archivo.size > MAX_PDF_BYTES) {
      guardar.setFeedback({ tone: "error", text: t.pdf_grande });
      return;
    }
    const datos: Record<string, unknown> = {
      categoria,
      tipo_documento: tipo,
      dependencia_id: dependenciaId,
      numero,
      fecha,
      periodo_id: alta.periodos.find((o) => o.etiqueta === periodo)?.id ?? null,
      titulo,
      detalle,
      observaciones,
    };
    if (requiereDocentes) {
      datos.modo_docentes = modo;
      datos.periodo_docentes_id = perDocId;
      datos.docentes = docentesElegidos.map((d) => d.CUIL);
      if (esDesignacion && desElegidas.length) {
        datos.designaciones = desElegidas;
        datos.reemplazar_vinculos = reemplazar;
      }
    }
    if (requiereProyectos) datos.proyectos = proyectosElegidos.map((p) => p.ID);
    void guardar.run(async () => {
      const r = await subir<WriteResult>("actos/guardar", datos, archivo);
      return r.aviso ? { ...r, mensaje: `${r.mensaje} ⚠️ ${r.aviso}`, tono: "warning" } : r;
    });
  }

  return (
    <section className="max-w-4xl space-y-4">
      <Field label="¿Qué respalda este documento?">
        <Select value={categoria} options={alta.categorias} onChange={setCategoria} />
      </Field>
      <Field label="Tipo de documento">
        <Select value={tipo} options={alta.tipos} onChange={(v) => setTipoPor({ ...tipoPor, [categoria]: v })} />
      </Field>
      <Field label="Dependencia emisora" hint={t.dependencia}>
        <Select value={dependencia} options={alta.dependencias.map((o) => o.etiqueta)} onChange={(v) => setDepPor({ ...depPor, [depKey]: v })} />
      </Field>
      {alta.sin_dependencias && <FeedbackBox feedback={{ tone: "info", text: alta.sin_dependencias }} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-4">
          <Field label="Número del acto">
            <TextInput value={numero} onChange={setNumero} placeholder="Ej.: 123/2026" />
          </Field>
          <Field label="Fecha del acto">
            <DateInput value={fecha} onChange={setFecha} label="Fecha del acto" />
          </Field>
        </div>
        <Field label="Período relacionado (opcional)">
          <Select value={periodo} options={alta.periodos.map((o) => o.etiqueta)} onChange={setPeriodo} />
        </Field>
      </div>

      {requiereDocentes && (
        <div className="space-y-3">
          <Seccion>Docentes alcanzados por la resolución</Seccion>
          <Caption>{t.docentes}</Caption>
          <Field label="Mostrar docentes de" hint={t.modo}>
            <Select value={modo} options={alta.modos_docentes} onChange={setModo} />
          </Field>
          {modo !== alta.modos_docentes[0] && alta.periodos_docentes.length > 0 && (
            <Field label="Período / cuatrimestre">
              <Select value={perDoc} options={alta.periodos_docentes.map((o) => o.etiqueta)} onChange={setPerDoc} />
            </Field>
          )}
          {docentes.error && <Aviso feedback={docentes.error} />}
          {docentes.data?.caption && (
            <Caption>
              <Md text={docentes.data.caption} />
            </Caption>
          )}
          {docentes.data?.aviso && <FeedbackBox feedback={{ tone: "warning", text: docentes.data.aviso }} />}
          {docentes.data && docentes.data.filas.length > 0 && (
            <>
              <Field label="Buscar docente">
                <TextInput value={buscarDoc} onChange={setBuscarDoc} placeholder="Apellido, nombre o CUIL..." />
              </Field>
              {filasDoc.length === 0 ? (
                <FeedbackBox feedback={{ tone: "warning", text: "No hay docentes que coincidan con la búsqueda." }} />
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-6">
                    <Check checked={todosDoc} onChange={setTodosDoc} label="Seleccionar todos los docentes filtrados" />
                    <Caption>{`Docentes mostrados: ${filasDoc.length}`}</Caption>
                  </div>
                  <Tabla
                    rows={filasDoc}
                    cols={[
                      { key: "Docente", label: "Docente" },
                      { key: "CUIL", label: "CUIL" },
                    ]}
                    rowKey={(r) => r.CUIL}
                    checked={todosDoc ? new Set(filasDoc.map((f) => f.CUIL)) : docSel}
                    onCheck={(k, v) => {
                      const next = new Set(todosDoc ? filasDoc.map((f) => f.CUIL) : docSel);
                      if (v) next.add(k);
                      else next.delete(k);
                      setTodosDoc(false);
                      setDocSel(next);
                    }}
                  />
                  <Caption>
                    <Md text={`Docentes seleccionados: **${docentesElegidos.length}**`} />
                  </Caption>
                </>
              )}
            </>
          )}
          {esDesignacion && cuilesElegidos.length > 0 && (
            <div className="space-y-2">
              <Seccion>Designaciones respaldadas por la resolución</Seccion>
              {designaciones.data?.caption && <Caption>{designaciones.data.caption}</Caption>}
              {designaciones.error && <Aviso feedback={designaciones.error} />}
              {designaciones.data?.aviso && <FeedbackBox feedback={{ tone: "warning", text: designaciones.data.aviso }} />}
              {filasDes.length > 0 && (
                <>
                  <SelectorDesignaciones filas={filasDes} value={desSel} onChange={setDesSel} documentoId={null} reemplazar={reemplazar} onReemplazar={setReemplazar} />
                  <Caption>
                    <Md text={`Designaciones seleccionadas: **${desElegidas.length}**`} />
                  </Caption>
                  {desElegidas.length === 0 && (
                    <FeedbackBox feedback={{ tone: "warning", text: "Sin designación seleccionada el acto queda vinculado solo al docente y la Disposición no podrá tomar su número. Podés vincularla después desde 📚 Repositorio." }} />
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {requiereProyectos && (
        <div className="space-y-3">
          <Seccion>Proyectos alcanzados por el documento</Seccion>
          <Caption>{t.proyectos}</Caption>
          {proyectos.error && <Aviso feedback={proyectos.error} />}
          {proyectos.data?.aviso && <FeedbackBox feedback={{ tone: "warning", text: proyectos.data.aviso }} />}
          {proyectos.data && proyectos.data.filas.length > 0 && (
            <>
              <Field label="Buscar proyecto">
                <TextInput value={buscarProy} onChange={setBuscarProy} placeholder="Código, nombre, estado o departamento..." />
              </Field>
              {filasProy.length === 0 ? (
                <FeedbackBox feedback={{ tone: "warning", text: "No hay proyectos que coincidan con la búsqueda." }} />
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-6">
                    <Check checked={todosProy} onChange={setTodosProy} label="Seleccionar todos los proyectos filtrados" />
                    <Caption>{`Proyectos mostrados: ${filasProy.length}`}</Caption>
                  </div>
                  <Tabla
                    rows={filasProy}
                    cols={[
                      { key: "ID", label: "ID" },
                      { key: "Código", label: "Código" },
                      { key: "Proyecto", label: "Proyecto" },
                      { key: "Estado", label: "Estado" },
                      { key: "Inicio", label: "Inicio" },
                      { key: "Fin", label: "Fin" },
                      { key: "Departamento creador", label: "Departamento creador" },
                    ]}
                    rowKey={(r) => String(r.ID)}
                    checked={todosProy ? new Set(filasProy.map((f) => String(f.ID))) : proySel}
                    onCheck={(k, v) => {
                      const next = new Set(todosProy ? filasProy.map((f) => String(f.ID)) : proySel);
                      if (v) next.add(k);
                      else next.delete(k);
                      setTodosProy(false);
                      setProySel(next);
                    }}
                  />
                  <Caption>
                    <Md text={`Proyectos seleccionados: **${proyectosElegidos.length}**`} />
                  </Caption>
                </>
              )}
            </>
          )}
        </div>
      )}

      {referencia && (
        <Caption>
          <Md text={`**Referencia automática:** ${referencia}`} />
        </Caption>
      )}
      <Field label="Título / asunto">
        <TextInput value={titulo} onChange={setTitulo} placeholder="Descripción breve del acto" />
      </Field>
      <Field label="Detalle / referencia adicional">
        <Textarea value={detalle} onChange={(v) => setDetallePor({ ...detallePor, [categoria]: v })} />
      </Field>
      <Field label="Observaciones internas">
        <Textarea value={observaciones} onChange={setObservaciones} />
      </Field>
      <SelectorPdf label="PDF respaldatorio (opcional; puede cargarse después)" archivo={archivo} onChange={setArchivo} />
      <Caption>{`Tamaño máximo del PDF: 50 MB. Debe ser un PDF real (firma %PDF-).`}</Caption>

      {faltaDocente && <FeedbackBox feedback={{ tone: "info", text: t.falta_docente }} />}
      {faltaProyecto && <FeedbackBox feedback={{ tone: "info", text: t.falta_proyecto }} />}
      {faltaDependencia && <FeedbackBox feedback={{ tone: "info", text: t.falta_dependencia }} />}
      {guardar.feedback && <Aviso feedback={guardar.feedback} />}
      <PrimaryButton busy={guardar.busy} disabled={faltaDocente || faltaProyecto || faltaDependencia} onClick={enviar}>
        💾 Guardar acto respaldatorio
      </PrimaryButton>
    </section>
  );
}

// ------------------------------------------------------------------ 🏛️ Dependencias (l. 52081-52128)
function DependenciasTab({ data, onDone, onError }: TabProps) {
  const d = data.dependencias;
  const [nombre, setNombre] = useState("");
  const [obs, setObs] = useState("");
  const [editSel, setEditSel] = useState(d.opciones_edicion[0]?.etiqueta ?? "");
  const agregar = useAccion(onDone, onError);
  const editar = useAccion(onDone, onError);
  const editId = d.opciones_edicion.find((o) => o.etiqueta === editSel)?.id ?? null;
  const fila = d.filas.find((f) => f.id === editId);
  const [edicion, setEdicion] = useState<Record<number, { nombre: string; estado: string; obs: string }>>({});
  const actual = editId !== null ? edicion[editId] ?? { nombre: fila?.nombre ?? "", estado: fila?.estado === "Inactiva" ? "Inactiva" : "Activa", obs: fila?.observaciones ?? "" } : null;

  // D-AK5: para roles sin escritura el certificado termina el render en "➕ Cargar acto" (return) y esta pestaña
  // queda vacía. Se conserva durante la equivalencia.
  if (!data.permisos.puede_escribir) return null;
  return (
    <section className="max-w-3xl space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Dependencias emisoras</h3>
      <Caption>{d.caption}</Caption>
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Dependencias activas</p>
          <p className="text-2xl font-semibold text-brand-950">{d.activas}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Dependencias cargadas</p>
          <p className="text-2xl font-semibold text-brand-950">{d.cargadas}</p>
        </div>
      </div>
      {d.filas.length === 0 ? (
        <FeedbackBox feedback={{ tone: "info", text: d.vacio }} />
      ) : (
        <Tabla
          rows={d.filas}
          cols={[
            { key: "nombre", label: "Dependencia" },
            { key: "estado", label: "Estado" },
            { key: "observaciones", label: "Observaciones" },
          ]}
          rowKey={(r) => String(r.id)}
        />
      )}
      <Seccion>Agregar dependencia</Seccion>
      {agregar.feedback && <Aviso feedback={agregar.feedback} />}
      <Field label="Nombre de la dependencia">
        <TextInput value={nombre} onChange={setNombre} placeholder="Ej.: Secretaría de Ciencia y Tecnología" />
      </Field>
      <Field label="Observaciones (opcional)">
        <Textarea value={obs} onChange={setObs} />
      </Field>
      <PrimaryButton busy={agregar.busy} onClick={() => agregar.run(() => post<WriteResult>("dependencias/agregar", { nombre, observaciones: obs }))}>
        ➕ Agregar dependencia
      </PrimaryButton>
      {d.filas.length > 0 && actual && editId !== null && (
        <>
          <hr className="border-slate-200" />
          <Seccion>Editar, activar o desactivar dependencia</Seccion>
          {editar.feedback && <Aviso feedback={editar.feedback} />}
          <Field label="Seleccioná una dependencia">
            <Select value={editSel} options={d.opciones_edicion.map((o) => o.etiqueta)} onChange={setEditSel} />
          </Field>
          <Field label="Nombre">
            <TextInput value={actual.nombre} onChange={(v) => setEdicion({ ...edicion, [editId]: { ...actual, nombre: v } })} />
          </Field>
          <Field label="Estado">
            <Select value={actual.estado} options={d.estados} onChange={(v) => setEdicion({ ...edicion, [editId]: { ...actual, estado: v } })} />
          </Field>
          <Field label="Observaciones">
            <Textarea value={actual.obs} onChange={(v) => setEdicion({ ...edicion, [editId]: { ...actual, obs: v } })} />
          </Field>
          <PrimaryButton
            busy={editar.busy}
            onClick={() =>
              editar.run(() =>
                post<WriteResult>("dependencias/editar", { id: editId, nombre: actual.nombre, estado: actual.estado, observaciones: actual.obs })
              )
            }
          >
            💾 Guardar cambios de la dependencia
          </PrimaryButton>
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ módulo
const PANELS = [RepositorioTab, CargarActoTab, DependenciasTab];

export function ResolucionesRespaldosModule({ onAuthError }: { onAuthError: (e: ApiError) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [tab, setTab] = useState(0);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [version, setVersion] = useState(0);

  const handle = useCallback(
    (err: unknown): ApiError => {
      const e = err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
      if (e.status === 401) onAuthError(e);
      return e;
    },
    [onAuthError]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await resolucionesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    resolucionesApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  // st.rerun(): después de una escritura se releen las lecturas.
  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando resoluciones y respaldos…
      </div>
    );
  }
  if (loadError && !data) {
    const scope = loadError.code.startsWith("SCOPE");
    return (
      <div className={`rounded-2xl border px-6 py-8 text-sm ${scope ? "border-slate-200 bg-white text-slate-700" : "border-red-200 bg-red-50 text-red-700"}`}>
        <p>{loadError.message}</p>
        {!scope && (
          <button onClick={load} className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">
            Reintentar
          </button>
        )}
      </div>
    );
  }
  if (!data) return null;
  const Panel = PANELS[tab] ?? RepositorioTab;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">{data.titulo}</h2>
      </div>
      <FeedbackBox feedback={{ tone: "info", text: data.info }} />
      <div role="tablist" aria-label="Pestañas de Resoluciones y respaldos" className="mb-6 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {data.tabs.map((label, i) => (
          <button
            key={label}
            role="tab"
            aria-selected={tab === i}
            onClick={() => {
              setTab(i);
              setFeedback(null);
            }}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm transition ${
              tab === i ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {feedback && <Aviso feedback={feedback} />}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      <div role="tabpanel">
        <Panel key={tab} data={data} version={version} onDone={afterWrite} onError={handle} />
      </div>
    </div>
  );
}
