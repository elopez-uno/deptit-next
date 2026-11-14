"use client";

// Módulo Disposiciones (B13-FIX02, entry l. 67812-68550): las 3 pestañas certificadas en su orden original.
// El documento es un Word (.docx) generado desde la plantilla de la institución; no hay PDF, Excel, edición ni anulación
// posterior. El N° es la posición alfabética del docente desde el número inicial del período (sin reserva).
// La UI solo oculta lo que el rol no puede hacer: FastAPI vuelve a autorizar cada escritura y sirve Word y ZIP.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spinner } from "@/components/brand";
import { Aviso, Caption, DateInput, Tabla, filtrar, hoyIso } from "@/components/designaciones-shared";
import { SoloLectura } from "@/components/investigacion-shared";
import { Check, Details, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea, type Feedback } from "@/components/module-ui";
import {
  type Designacion,
  type Historial,
  type HistorialFila,
  type MasivaResult,
  type Overview,
  type PeriodoData,
  type Vista,
  type VistaPrevia,
  type WriteResult,
  MAX_PLANTILLA_BYTES,
  archivo,
  descargar,
  disposicionesApi,
  leerBase64,
  post,
} from "@/lib/disposiciones";
import { ApiError } from "@/lib/auth";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;
type TabProps = { data: Overview; version: number; onDone: OnDone; onError: OnError };

function feedbackDe(err: ApiError): NonNullable<Feedback> {
  const tone = (err as { tone?: string }).tone;
  return { tone: tone === "warning" ? "warning" : tone === "info" ? "info" : "error", text: err.message };
}

// Consulta POST que se repite cuando cambian sus parámetros o la versión (equivale al rerun certificado).
function useConsulta<T>(path: string, body: unknown, onError: OnError, version = 0, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const seq = useRef(0);
  const key = JSON.stringify(body);
  useEffect(() => {
    if (!enabled) return;
    const n = ++seq.current;
    const t = setTimeout(() => {
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
    }, 150);
    return () => clearTimeout(t);
  }, [path, key, onError, version, enabled]);
  return { data, error };
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

function useDescarga(onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  async function bajar(path: string, body: unknown, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      descargar(await archivo(path, body, fallback));
    } catch (e) {
      setError(feedbackDe(onError(e)));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, bajar };
}

function Subtitulo({ children }: { children: React.ReactNode }) {
  return <h3 className="text-lg font-semibold text-brand-950">{children}</h3>;
}

function Seccion({ children }: { children: React.ReactNode }) {
  return <h4 className="pt-2 text-base font-semibold text-slate-800">{children}</h4>;
}

function SinPermiso({ children }: { children: React.ReactNode }) {
  return <Caption>{children}</Caption>;
}

// ------------------------------------------------------------------ ⚙️ Configuración (l. 67822-67873)
function ConfiguracionTab({ data, onDone, onError }: TabProps) {
  // Tras guardar, el módulo vuelve a montar esta pestaña con la configuración releída (st.rerun).
  const [valores, setValores] = useState<Record<string, string>>(data.configuracion);
  const guardar = useAccion(onDone, onError);
  const plantilla = useAccion(onDone, onError);
  const [archivoSel, setArchivoSel] = useState<File | null>(null);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const izquierda = data.campos.slice(0, 6);
  const derecha = data.campos.slice(6);
  const campo = (c: { clave: string; etiqueta: string }) =>
    c.clave === "genero_director_departamento" ? (
      <Field key={c.clave} label={c.etiqueta} hint={data.textos.genero}>
        <Select
          value={data.opciones_genero.includes(valores[c.clave]) ? valores[c.clave] : data.opciones_genero[0]}
          options={data.opciones_genero}
          onChange={(v) => setValores({ ...valores, [c.clave]: v })}
        />
      </Field>
    ) : (
      <label key={c.clave} className="block">
        <span className="mb-1 block text-xs font-medium text-slate-500">{c.etiqueta}</span>
        <input
          aria-label={c.etiqueta}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={valores[c.clave] ?? ""}
          onChange={(e) => setValores({ ...valores, [c.clave]: e.target.value })}
        />
      </label>
    );

  function elegir(f: File | null) {
    setErrorArchivo(null);
    setArchivoSel(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".docx")) return setErrorArchivo("El archivo debe tener extensión .docx.");
    if (f.size > MAX_PLANTILLA_BYTES) return setErrorArchivo("El documento Word supera el tamaño máximo permitido.");
    setArchivoSel(f);
  }

  async function reemplazar() {
    if (!archivoSel) return;
    const r = await plantilla.run(
      async () =>
        post<WriteResult>("plantilla/reemplazar", { nombre_archivo: archivoSel.name, contenido_base64: await leerBase64(archivoSel) }),
      true
    );
    if (r) {
      setArchivoSel(null);
      setInputKey((k) => k + 1);
    }
  }

  const p = data.plantilla;
  return (
    <div className="space-y-4">
      <Subtitulo>Configuración general para completar disposiciones</Subtitulo>
      <Caption>{data.textos.config}</Caption>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">{izquierda.map(campo)}</div>
        <div className="space-y-3">
          {derecha.map(campo)}
          <Caption>{data.textos.acto}</Caption>
        </div>
      </div>
      {guardar.feedback && <Aviso feedback={guardar.feedback} />}
      {data.permisos.puede_escribir ? (
        <PrimaryButton
          busy={guardar.busy}
          onClick={() => guardar.run(() => post<WriteResult>("configuracion/guardar", { valores, huella: data.huella_configuracion }))}
        >
          💾 Guardar configuración de disposiciones
        </PrimaryButton>
      ) : (
        <SoloLectura />
      )}

      <hr className="border-slate-200" />
      <Subtitulo>Plantilla Word de la institución</Subtitulo>
      {p.status === "OK" ? (
        <Aviso feedback={{ tone: "success", text: `La institución tiene su plantilla configurada (actualizada ${p.actualizada ?? ""}, huella ${p.sha256_12 ?? ""}).` }} />
      ) : (
        <Aviso feedback={{ tone: "warning", text: p.message || "La plantilla institucional no está disponible." }} />
      )}
      {data.permisos.puede_plantilla ? (
        <>
          <Field label="Cargar/reemplazar plantilla Word de la institución">
            <input
              key={inputKey}
              type="file"
              aria-label="Cargar/reemplazar plantilla Word de la institución"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-800"
              onChange={(e) => elegir(e.target.files?.[0] ?? null)}
            />
          </Field>
          {errorArchivo && <Aviso feedback={{ tone: "error", text: errorArchivo }} />}
          {plantilla.feedback && <Aviso feedback={plantilla.feedback} />}
          {archivoSel && (
            <PrimaryButton tone="secondary" busy={plantilla.busy} onClick={reemplazar}>
              💾 Reemplazar plantilla de la institución
            </PrimaryButton>
          )}
        </>
      ) : (
        <SinPermiso>La plantilla institucional la administra un usuario del departamento o el superadmin (con la institución seleccionada).</SinPermiso>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 📝 Nueva disposición (l. 67875-68469)
const HELP_NUMERO = "La primera persona según el orden alfabético recibe este número; las siguientes continúan correlativamente.";

function NuevaTab({ data, version, onDone, onError }: TabProps) {
  const opciones = data.periodos.map((p) => String(p.nombre));
  const defecto = data.periodos.find((p) => p.id === data.periodo_defecto);
  const [periodoNombre, setPeriodoNombre] = useState(defecto ? String(defecto.nombre) : opciones[0] ?? "");
  const periodo = data.periodos.find((p) => String(p.nombre) === periodoNombre) ?? null;
  const pid = periodo?.id ?? null;
  const r = useConsulta<PeriodoData>("periodo", { periodo_id: pid }, onError, version, pid !== null);

  if (!data.periodos.length) return <Aviso feedback={{ tone: "warning", text: "Primero necesitás tener períodos cargados." }} />;
  return (
    <div className="space-y-4">
      <Subtitulo>Generar nueva disposición</Subtitulo>
      <Field label="Período">
        <Select value={periodoNombre} options={opciones} onChange={setPeriodoNombre} />
      </Field>
      {r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data || pid === null ? (
        <Cargando />
      ) : (
        <PeriodoPanel key={`${pid}-${version}`} data={data} pid={pid} periodo={periodoNombre} pd={r.data} onDone={onDone} onError={onError} />
      )}
    </div>
  );
}

function Cargando() {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-500">
      <Spinner className="h-4 w-4 text-brand-600" /> Cargando…
    </div>
  );
}

function PeriodoPanel({
  data,
  pid,
  periodo,
  pd,
  onDone,
  onError,
}: {
  data: Overview;
  pid: number;
  periodo: string;
  pd: PeriodoData;
  onDone: OnDone;
  onError: OnError;
}) {
  const [numero, setNumero] = useState(String(pd.numero_inicial));
  const guardarNumero = useAccion(onDone, onError);
  const [buscar, setBuscar] = useState("");
  const vista = useMemo(
    () => filtrar(pd.habilitados, buscar, ["nombre_completo", "cuil", "legajo", "titulo", "estado", "email"]),
    [pd.habilitados, buscar]
  );
  const [sel, setSel] = useState<string | null>(null);
  const seleccionado = vista.find((f) => f.cuil === sel) ?? vista[0] ?? null; // default_first del certificado
  const numeroValido = /^\d+$/.test(numero.trim()) && Number(numero) >= 1;

  return (
    <div className="space-y-4">
      <div className="grid items-end gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <Field label="Número inicial de la primera disposición del período" hint={HELP_NUMERO}>
            <input
              type="number"
              min={1}
              step={1}
              aria-label="Número inicial de la primera disposición del período"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
            />
          </Field>
        </div>
        <div className="space-y-1">
          <Caption>Numeración correlativa</Caption>
          {data.permisos.puede_escribir && (
            <PrimaryButton
              tone="secondary"
              busy={guardarNumero.busy}
              disabled={!numeroValido}
              onClick={() =>
                guardarNumero.run(() =>
                  post<WriteResult>("numero-inicial/guardar", { periodo_id: pid, numero: Number(numero), huella: pd.numero_inicial })
                )
              }
            >
              💾 Guardar número inicial
            </PrimaryButton>
          )}
        </div>
      </div>
      {guardarNumero.feedback && <Aviso feedback={guardarNumero.feedback} />}

      {pd.habilitados.length === 0 ? (
        <Aviso feedback={{ tone: "warning", text: pd.aviso }} />
      ) : (
        <>
          <Caption>{pd.caption}</Caption>
          <Masiva data={data} pid={pid} periodo={periodo} pd={pd} onError={onError} />
          <Field label="Buscar docente">
            <TextInput value={buscar} onChange={setBuscar} placeholder="Nombre, CUIL, legajo, título, estado..." />
          </Field>
          {vista.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay docentes activos que coincidan con la búsqueda." }} />
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-800">Docentes activos del período</p>
              <Tabla
                rows={vista}
                cols={[
                  { key: "numero_disposicion_auto", label: "N° disposición" },
                  { key: "nombre_completo", label: "Docente" },
                  { key: "cuil", label: "CUIL" },
                  { key: "legajo", label: "Legajo" },
                  { key: "titulo", label: "Título" },
                  { key: "estado", label: "Estado" },
                  { key: "email", label: "Email" },
                ]}
                rowKey={(f) => f.cuil}
                selected={seleccionado?.cuil ?? null}
                onSelect={setSel}
                maxHeight="max-h-72"
              />
              {seleccionado && (
                <DocentePanel key={`${seleccionado.cuil}-${seleccionado.huella}`} data={data} pid={pid} cuil={seleccionado.cuil} onError={onError} />
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// "📦 Generar todas las disposiciones del período" (l. 67923-68076): UNA acción; el backend prepara el lote completo y
// solo si nadie falla genera N disposiciones independientes, en orden.
function Masiva({ data, pid, periodo, pd, onError }: { data: Overview; pid: number; periodo: string; pd: PeriodoData; onError: OnError }) {
  const [fecha, setFecha] = useState(hoyIso());
  const [tipo, setTipo] = useState(data.tipo_defecto);
  const [estado, setEstado] = useState(data.estados[0]);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<MasivaResult | null>(null);
  const [error, setError] = useState<NonNullable<Feedback> | null>(null);
  const zip = useDescarga(onError);
  const n = pd.habilitados.length;

  async function generar() {
    setBusy(true);
    setError(null);
    setRes(null);
    try {
      setRes(await post<MasivaResult>("generar-masiva", { periodo_id: pid, fecha, tipo, estado, huella_padron: pd.huella_padron }));
    } catch (e) {
      setError(feedbackDe(onError(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Details summary="📦 Generar todas las disposiciones del período">
      <Caption>
        Genera un Word por cada docente de la lista habilitada de este período, respetando la numeración alfabética desde{" "}
        {pd.numero_inicial} y continuando correlativamente; registra cada disposición en el historial y prepara un único ZIP para
        descargar todos los Word juntos.
      </Caption>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Fecha de las disposiciones">
          <DateInput label="Fecha de las disposiciones" value={fecha} onChange={setFecha} />
        </Field>
        <Field label="Tipo / asunto para todas">
          <TextInput value={tipo} onChange={setTipo} />
        </Field>
        <Field label="Estado para todas">
          <Select value={estado} options={data.estados} onChange={setEstado} />
        </Field>
      </div>
      <Caption>Se usa la plantilla Word de la institución (Configuración); no se aceptan rutas manuales.</Caption>
      <Caption>{pd.caption_validacion}</Caption>
      {data.permisos.puede_escribir ? (
        <PrimaryButton busy={busy} disabled={!fecha} onClick={generar}>
          📄 Generar las {n} disposiciones y preparar ZIP
        </PrimaryButton>
      ) : (
        <SoloLectura />
      )}
      {busy && <Caption>Generando las disposiciones del período: puede demorar unos minutos.</Caption>}
      {error && <Aviso feedback={error} />}
      {res && (
        <div className="space-y-3">
          {res.mensaje && <Aviso feedback={{ tone: res.tono, text: res.mensaje }} />}
          {res.tabla.length > 0 && <TablaSimple filas={res.tabla} />}
          {res.aviso && <Aviso feedback={{ tone: "warning", text: res.aviso }} />}
          {res.errores.length > 0 && <TablaSimple filas={res.errores} />}
          {res.generadas > 0 && (
            <>
              {zip.error && <Aviso feedback={zip.error} />}
              <PrimaryButton
                tone="secondary"
                busy={zip.busy}
                onClick={() => zip.bajar("zip-lote", { periodo_id: pid, ids: res.ids }, res.zip_nombre ?? `Disposiciones_${periodo}.zip`)}
              >
                ⬇️ Descargar ZIP con todas las disposiciones ({res.generadas})
              </PrimaryButton>
            </>
          )}
        </div>
      )}
    </Details>
  );
}

function TablaSimple({ filas }: { filas: Record<string, string>[] }) {
  const cols = Object.keys(filas[0] ?? {}).map((k) => ({ key: k, label: k }));
  return <Tabla rows={filas} cols={cols} rowKey={(f) => JSON.stringify(f)} maxHeight="max-h-60" />;
}

const TONOS_CONSULTA = { success: "success", warning: "warning", error: "error", info: "info" } as const;

// Vista del docente elegido; "Guardar datos" relee solo esta vista (st.rerun) y conserva la selección de la tabla.
function DocentePanel({ data, pid, cuil, onError }: { data: Overview; pid: number; cuil: string; onError: OnError }) {
  const [version, setVersion] = useState(0);
  const [aviso, setAviso] = useState<Feedback>(null);
  const r = useConsulta<Vista>("docente", { periodo_id: pid, cuil }, onError, version);
  const guardado = useCallback(async (f: Feedback) => {
    setAviso(f);
    setVersion((x) => x + 1);
  }, []);
  if (r.error) return <Aviso feedback={r.error} />;
  if (!r.data) return <Cargando />;
  return (
    <>
      {aviso && <Aviso feedback={aviso} />}
      <DocenteForm key={`${r.data.huella}-${r.data.huella_designaciones}-${version}`} data={data} pid={pid} v={r.data} onError={onError} onGuardado={guardado} />
    </>
  );
}

type Edicion = { designacion_id: number | null; fecha_desde: string; fecha_hasta: string; observaciones: string };

function DocenteForm({ data, pid, v, onError, onGuardado }: { data: Overview; pid: number; v: Vista; onError: OnError; onGuardado: OnDone }) {
  const [fecha, setFecha] = useState(hoyIso());
  const [tipo, setTipo] = useState(data.tipo_defecto);
  const [estado, setEstado] = useState(data.estados[0]);
  const [conc, setConc] = useState(v.tiene_concursado);
  const [inter, setInter] = useState(v.tiene_interino);
  const [inv, setInv] = useState(v.tiene_investigacion_o_extension);
  const [obs, setObs] = useState("");
  const [obsGenerales, setObsGenerales] = useState(v.observaciones_generales);
  const [ediciones, setEdiciones] = useState<Edicion[]>(
    v.designaciones.map((d) => ({ designacion_id: d.designacion_id, fecha_desde: d.fecha_desde, fecha_hasta: d.fecha_hasta, observaciones: d.observaciones }))
  );
  const previa = useConsulta<VistaPrevia>(
    "docente/vista-previa",
    { periodo_id: pid, cuil: v.cuil, incluir_concursado: conc, incluir_interino: inter, designaciones: ediciones },
    onError
  );
  const considerandos = previa.data?.considerandos ?? v.considerandos;
  const avisoIncompletas = previa.data ? previa.data.aviso_incompletas : v.aviso_incompletas;
  const datos = useAccion(onGuardado, onError);
  const generar = useAccion(async () => {}, onError);
  const [generado, setGenerado] = useState<{ id: number; file_name: string } | null>(null);
  const word = useDescarga(onError);
  const consulta = v.estado_consulta;
  const prefijo = "Estado de la consulta antes de generar la disposición";

  async function generarWord() {
    if (v.tiene_no_docente && !v.texto_funcion_no_docente.trim()) {
      generar.setFeedback({
        tone: "error",
        text: "Hay una designación no docente activa sin funciones cargadas. Completalas en el módulo Designaciones antes de generar la disposición.",
      });
      return;
    }
    const res = await generar.run(
      () =>
        post<WriteResult>("generar", {
          periodo_id: pid,
          cuil: v.cuil,
          huella: v.huella,
          fecha,
          tipo,
          estado,
          observaciones: obs,
          incluir_concursado: conc,
          incluir_interino: inter,
          incluir_investigacion: inv,
          designaciones: ediciones,
        }),
      false
    );
    if (res?.id && res.file_name) setGenerado({ id: res.id, file_name: res.file_name });
  }

  const editar = (i: number, campo: keyof Edicion, valor: string) =>
    setEdiciones(ediciones.map((e, j) => (j === i ? { ...e, [campo]: valor } : e)));
  const textoNd = v.texto_funcion_no_docente;

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <Aviso
        feedback={{
          tone: TONOS_CONSULTA[consulta.tono],
          text: consulta.estado ? `${consulta.icono} ${prefijo}: ${consulta.estado}` : `${consulta.icono} ${prefijo}: sin estado registrado`,
        }}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-3">
          <Field label="Fecha disposición">
            <DateInput label="Fecha disposición" value={fecha} onChange={setFecha} />
          </Field>
          <Field label="Número disposición (automático)" hint="Se asigna 1, 2, 3... según el orden alfabético de los docentes activos del período.">
            <TextInput value={v.numero} onChange={() => {}} disabled />
          </Field>
          <Field label="Tipo / asunto">
            <TextInput value={tipo} onChange={setTipo} />
          </Field>
        </div>
        <div className="space-y-3">
          <Check checked={conc} onChange={setConc} label="Incluir párrafo concursado" />
          <Check checked={inter} onChange={setInter} label="Incluir párrafo interino" />
          <Check checked={inv} onChange={setInv} label="Incluir artículo de investigación / extensión" />
          <Check checked={v.tiene_actividades_especiales} onChange={() => {}} disabled label="Incluir artículo de actividades especiales" />
          <Caption>
            Control visual automático: se marca cuando el docente tiene una Actividad Especial activa en el período. La inclusión del
            artículo se resuelve automáticamente con los datos del sistema.
          </Caption>
        </div>
        <div className="space-y-3">
          <Caption>Plantilla: la de la institución (Configuración).</Caption>
          <Field label="Estado">
            <Select value={estado} options={data.estados} onChange={setEstado} />
          </Field>
        </div>
      </div>

      <Seccion>Datos recuperados automáticamente según el docente</Seccion>
      <Caption>
        Estos campos salen del docente seleccionado, sus designaciones, comisiones, investigación y extensión. Se actualizan al cambiar
        docente/período y no se cargan manualmente en cada disposición.
      </Caption>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Docente">
            <TextInput value={v.docente} onChange={() => {}} disabled />
          </Field>
          <Field label="Cargo/s">
            <TextInput value={v.cargo} onChange={() => {}} disabled />
          </Field>
          <Field label="Dedicación/es">
            <TextInput value={v.dedicacion} onChange={() => {}} disabled />
          </Field>
          <Field label="Departamento/s en que revistará">
            <TextInput value={v.departamentos_revistara} onChange={() => {}} disabled />
          </Field>
          <Field label="Asignaturas que dicta con días, horarios, carreras y unidades académicas">
            <Textarea value={v.asignaturas} onChange={() => {}} disabled rows={6} />
          </Field>
        </div>
        <div className="space-y-3">
          <Field
            label="Unidades académicas / dependencias a notificar"
            hint="Incluye las unidades académicas de las materias y, cuando corresponda, las unidades donde radican los proyectos de investigación/extensión. El departamento emisor no se repite."
          >
            <TextInput value={v.escuelas} onChange={() => {}} disabled />
          </Field>
          <p className="text-sm font-semibold text-slate-800">Designaciones detectadas para la disposición</p>
          {v.designaciones.length ? (
            <Tabla
              rows={v.designaciones}
              cols={[
                { key: "departamento", label: "Departamento" },
                { key: "tipo", label: "Tipo" },
                { key: "cargo", label: "Cargo" },
                { key: "dedicacion", label: "Dedicación" },
                { key: "condicion", label: "Condición" },
                { key: "funcion", label: "Función" },
                { key: "funciones_no_docentes", label: "Funciones no docentes" },
                { key: "resolucion", label: "Resolución" },
                { key: "fecha_desde", label: "Desde" },
                { key: "fecha_hasta", label: "Hasta" },
              ]}
              rowKey={(d) => `${d.designacion_id}-${d.tipo}-${d.cargo}`}
              maxHeight="max-h-60"
            />
          ) : (
            <Aviso feedback={{ tone: "info", text: "No se detectaron designaciones concursadas o interinas para este docente y período." }} />
          )}
        </div>
      </div>

      {v.promover_ie_art1 && (
        <Aviso
          feedback={{
            tone: "info",
            text:
              "Este docente tiene designación docente pero no cubre comisiones. La disposición ubicará Investigación/Extensión directamente en el Artículo 1. El Artículo 2 general se conservará igual que en las demás disposiciones, y los artículos siguientes mantendrán su lógica habitual.",
          }}
        />
      )}

      {v.es_no_docente && (
        <>
          <Seccion>Funciones no docentes — tomadas de Designaciones</Seccion>
          {textoNd ? (
            <>
              <Field label="Funciones que se incorporarán al Artículo 1" hint="Este dato se carga y modifica exclusivamente en el módulo Designaciones.">
                <Textarea value={textoNd} onChange={() => {}} disabled rows={3} />
              </Field>
              <Caption>
                {`Vista previa: ARTÍCULO 1º.– Asígnese al/la docente ${v.docente || v.cuil}, CUIL N° ${v.cuil}, el cumplimiento de funciones ${textoNd.replace(/\.+$/, "")}.`}
              </Caption>
            </>
          ) : (
            <Aviso
              feedback={{
                tone: "error",
                text: "La designación está marcada como no docente pero no tiene cargadas sus funciones. Completalas desde Designaciones → Modificar designación antes de generar la disposición.",
              }}
            />
          )}
        </>
      )}
      {!v.es_no_docente && v.es_mixta && (
        <>
          <Seccion>Funciones docentes + no docentes — disposición mixta</Seccion>
          <Aviso
            feedback={{
              tone: "info",
              text: "Esta persona tiene simultáneamente designaciones docentes y no docentes activas. El Artículo 1 conservará las materias, días, horarios, carreras y unidades académicas recuperadas automáticamente y agregará las funciones no docentes cargadas en Designaciones.",
            }}
          />
          {textoNd ? (
            <>
              <Field label="Funciones no docentes que se incorporarán al Artículo 1" hint="Este dato se carga y modifica exclusivamente en el módulo Designaciones.">
                <Textarea value={textoNd} onChange={() => {}} disabled rows={3} />
              </Field>
              <Caption>
                {`Vista previa: ARTÍCULO 1º.– Asígnese al/la docente ${v.docente || v.cuil}, CUIL N° ${v.cuil}, el cumplimiento de funciones de docencia en ${
                  v.asignaturas.trim().replace(/\.+$/, "") || "[funciones docentes recuperadas]"
                } y de funciones ${textoNd.trim().replace(/\.+$/, "")}.`}
              </Caption>
            </>
          ) : (
            <Aviso
              feedback={{
                tone: "error",
                text: "La persona tiene una designación no docente activa pero esa designación no tiene cargadas sus funciones. Completalas desde Designaciones → Modificar designación antes de generar la disposición.",
              }}
            />
          )}
        </>
      )}

      <Details summary="Revisar datos de las designaciones para la disposición">
        <Caption>
          El acto administrativo se toma del repositorio vinculado a cada designación y no se edita acá. Podés mantener fechas/observaciones
          auxiliares del considerando. Si varias designaciones tienen igual tipo, acto y fechas, luego se agrupan en un mismo considerando.
        </Caption>
        {!v.designaciones.length && <Aviso feedback={{ tone: "info", text: "No hay designaciones concursadas o interinas para completar." }} />}
        {v.designaciones.map((d: Designacion, i) => (
          <div key={`${d.designacion_id}-${i}`} className="space-y-2 border-b border-slate-100 pb-3 last:border-0">
            <p className="text-sm font-semibold text-slate-800">{`${d.departamento || "Departamento correspondiente"} — ${d.tipo}`}</p>
            <Caption>{`${d.cargo} — dedicación ${d.dedicacion}${d.horas_texto}`}</Caption>
            {d.funcion === "No docente" && (
              <Aviso feedback={{ tone: "info", text: `Funciones no docentes: ${d.texto_funcion_limpio || "SIN CARGAR EN DESIGNACIONES"}` }} />
            )}
            <div className="grid gap-3 md:grid-cols-2">
              <Field
                label={d.tipo === "Concursado" ? "Acto administrativo · Resolución CS" : "Acto administrativo · Resolución Rectoral"}
                hint="Fuente: acto administrativo del repositorio vinculado a la designación. Para cambiarlo, usá Designaciones → Vincular / cambiar acto administrativo."
              >
                <TextInput value={d.resolucion} onChange={() => {}} disabled />
              </Field>
              <Field label="Fecha hasta">
                <TextInput value={ediciones[i].fecha_hasta} onChange={(x) => editar(i, "fecha_hasta", x)} />
              </Field>
              <Field label="Fecha desde">
                <TextInput value={ediciones[i].fecha_desde} onChange={(x) => editar(i, "fecha_desde", x)} />
              </Field>
              <Field label="Observaciones de esta designación">
                <TextInput value={ediciones[i].observaciones} onChange={(x) => editar(i, "observaciones", x)} />
              </Field>
            </div>
          </div>
        ))}
        <Field label="Observaciones internas generales sobre datos de disposición del docente">
          <Textarea value={obsGenerales} onChange={setObsGenerales} />
        </Field>
        {datos.feedback && <Aviso feedback={datos.feedback} />}
        {data.permisos.puede_escribir && (
          <PrimaryButton
            tone="secondary"
            busy={datos.busy}
            onClick={() =>
              datos.run(() =>
                post<WriteResult>("docente/guardar-datos", {
                  periodo_id: pid,
                  cuil: v.cuil,
                  designaciones: ediciones,
                  observaciones_generales: obsGenerales,
                  huella_designaciones: v.huella_designaciones,
                })
              )
            }
          >
            💾 Guardar datos de disposición para este docente
          </PrimaryButton>
        )}
      </Details>

      <Seccion>Vista previa de los considerandos de designación</Seccion>
      {considerandos.length ? (
        considerandos.map((t, i) => <Aviso key={i} feedback={{ tone: "info", text: t }} />)
      ) : (
        <Caption>No se incluirán considerandos de designación con la selección actual.</Caption>
      )}
      {avisoIncompletas && <Aviso feedback={{ tone: "warning", text: avisoIncompletas }} />}

      <Seccion>Datos de investigación y extensión recuperados</Seccion>
      <Caption>
        {"Si el docente participa en uno o más proyectos de investigación y/o extensión, la disposición los incorpora " +
          (v.promover_ie_art1
            ? "en el Artículo 1 porque no tiene comisiones asignadas; el Artículo 2 general se conserva igual que en las demás disposiciones."
            : "en un único Artículo 2, distinguiendo cada proyecto y su tipo.")}
      </Caption>
      <Field label="Texto de investigación/extensión para la disposición">
        <Textarea value={v.texto_investigacion} onChange={() => {}} disabled rows={4} />
      </Field>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Rol/es en proyecto/s de investigación">
          <TextInput value={v.rol_investigacion} onChange={() => {}} disabled />
        </Field>
        <Field label="Código/s interno/s de investigación">
          <TextInput value={v.codigo_investigacion} onChange={() => {}} disabled />
        </Field>
        <Field label="Proyecto/s de investigación">
          <TextInput value={v.proyecto_investigacion} onChange={() => {}} disabled />
        </Field>
        <Field label="Instituto/Departamento de investigación">
          <TextInput value={v.instituto_investigacion} onChange={() => {}} disabled />
        </Field>
        <Field label="Proyecto/s de extensión">
          <TextInput value={v.proyecto_extension} onChange={() => {}} disabled />
        </Field>
        <Field label="Área/Secretaría de extensión">
          <TextInput value={v.area_extension} onChange={() => {}} disabled />
        </Field>
      </div>

      <Seccion>Actividades Especiales recuperadas</Seccion>
      {v.texto_actividades_especiales ? (
        <Field label="Texto que se incorporará como Artículo 3">
          <Textarea value={v.texto_actividades_especiales} onChange={() => {}} disabled rows={3} />
        </Field>
      ) : (
        <Caption>No se detectaron Actividades Especiales activas del docente dentro del ámbito de esta disposición y período.</Caption>
      )}

      <Field label="Observaciones internas">
        <Textarea value={obs} onChange={setObs} />
      </Field>
      {generar.feedback && <Aviso feedback={generar.feedback} />}
      {data.permisos.puede_escribir ? (
        <PrimaryButton busy={generar.busy} disabled={!fecha} onClick={generarWord}>
          📄 Generar Word de disposición
        </PrimaryButton>
      ) : (
        <SoloLectura />
      )}
      {generado && (
        <>
          {word.error && <Aviso feedback={word.error} />}
          <PrimaryButton tone="secondary" busy={word.busy} onClick={() => word.bajar("descargar", { id: generado.id }, generado.file_name)}>
            ⬇️ Descargar Word generado
          </PrimaryButton>
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ 📚 Historial (l. 68471-68549)
const TODOS = "Todos los períodos";

function HistorialTab({ data, version, onDone, onError }: TabProps) {
  const opciones = [TODOS, ...data.periodos.map((p) => String(p.nombre))];
  const [periodoNombre, setPeriodoNombre] = useState(TODOS);
  const pid = data.periodos.find((p) => String(p.nombre) === periodoNombre)?.id ?? null;
  const r = useConsulta<Historial>("historial", { periodo_id: pid }, onError, version);
  const [buscar, setBuscar] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const eliminar = useAccion(onDone, onError);
  const word = useDescarga(onError);
  const zip = useDescarga(onError);
  const filas = useMemo(() => r.data?.filas ?? [], [r.data]);
  const vista = useMemo(
    () => filtrar(filas, buscar, ["periodo", "numero", "docente", "cuil", "fecha", "tipo", "estado", "observaciones"]),
    [filas, buscar]
  );
  const fila: HistorialFila | null = vista.find((f) => f.id === sel) ?? vista[0] ?? null;

  return (
    <div className="space-y-4">
      <Subtitulo>Historial de disposiciones</Subtitulo>
      {data.periodos.length > 0 && (
        <Field label="Filtrar por período">
          <Select value={periodoNombre} options={opciones} onChange={setPeriodoNombre} />
        </Field>
      )}
      {r.error ? (
        <Aviso feedback={r.error} />
      ) : !r.data ? (
        <Cargando />
      ) : filas.length === 0 ? (
        <Aviso feedback={{ tone: "info", text: "Todavía no hay disposiciones registradas." }} />
      ) : (
        <>
          {r.data.zip.error && <Aviso feedback={{ tone: "error", text: r.data.zip.error }} />}
          {r.data.zip.cantidad > 0 ? (
            <>
              {zip.error && <Aviso feedback={zip.error} />}
              <PrimaryButton
                tone="secondary"
                busy={zip.busy}
                onClick={() => zip.bajar("historial/zip", { periodo_id: pid }, `Disposiciones_${periodoNombre}.zip`)}
              >
                📦 Descargar todas las disposiciones juntas ({r.data.zip.cantidad})
              </PrimaryButton>
              {r.data.zip.detalle && <Caption>{r.data.zip.detalle}</Caption>}
            </>
          ) : (
            <Aviso feedback={{ tone: "warning", text: r.data.zip.aviso || "No hay archivos Word disponibles para descargar en conjunto con este filtro." }} />
          )}
          <Field label="Buscar disposición">
            <TextInput value={buscar} onChange={setBuscar} placeholder="Período, número, docente, CUIL, fecha, tipo, estado..." />
          </Field>
          {vista.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay registros que coincidan con la búsqueda." }} />
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-800">Disposiciones encontradas</p>
              <Tabla
                rows={vista}
                cols={[
                  { key: "periodo", label: "Período" },
                  { key: "numero", label: "Número" },
                  { key: "docente", label: "Docente" },
                  { key: "cuil", label: "CUIL" },
                  { key: "fecha", label: "Fecha" },
                  { key: "tipo", label: "Tipo / asunto" },
                  { key: "estado", label: "Estado" },
                  { key: "observaciones", label: "Observaciones" },
                ]}
                rowKey={(f) => String(f.id)}
                selected={fila ? String(fila.id) : null}
                onSelect={(k) => setSel(Number(k))}
              />
            </>
          )}
          <Caption>{`Resultados: ${vista.length} de ${filas.length} disposiciones`}</Caption>
          {fila && fila.documento.disponible ? (
            <>
              {word.error && <Aviso feedback={word.error} />}
              <PrimaryButton tone="secondary" busy={word.busy} onClick={() => word.bajar("descargar", { id: fila.id }, "disposicion.docx")}>
                ⬇️ Descargar Word del historial
              </PrimaryButton>
            </>
          ) : (
            <Aviso feedback={{ tone: "warning", text: fila ? fila.documento.mensaje : "Seleccioná una disposición para descargar su Word." }} />
          )}
          {data.permisos.puede_borrar ? (
            <>
              <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que quiero eliminar el registro de esta disposición" />
              {eliminar.feedback && <Aviso feedback={eliminar.feedback} />}
              <PrimaryButton
                tone="danger"
                busy={eliminar.busy}
                disabled={fila === null}
                onClick={() =>
                  fila &&
                  (confirmar
                    ? eliminar.run(() => post<WriteResult>("historial/eliminar", { id: fila.id, huella: fila.huella, confirmar }))
                    : eliminar.setFeedback({ tone: "error", text: "Primero confirmá la eliminación." }))
                }
              >
                🗑️ Eliminar registro de disposición
              </PrimaryButton>
            </>
          ) : (
            <Caption>La eliminación de registros está reservada al rol superadmin.</Caption>
          )}
        </>
      )}
    </div>
  );
}

const TABS: { key: string; label: string }[] = [
  { key: "config", label: "⚙️ Configuración" },
  { key: "nueva", label: "📝 Nueva disposición" },
  { key: "historial", label: "📚 Historial" },
];

const PANELS: Record<string, (p: TabProps) => React.ReactElement> = {
  config: ConfiguracionTab,
  nueva: NuevaTab,
  historial: HistorialTab,
};

export function DisposicionesModule({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("config");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [version, setVersion] = useState(0);

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
      setData(await disposicionesApi.overview());
      setLoadError(null);
    } catch (err) {
      setLoadError(handle(err));
    } finally {
      setLoading(false);
    }
  }, [handle]);

  useEffect(() => {
    let cancelled = false;
    disposicionesApi
      .overview()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setLoadError(handle(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [handle]);

  // st.rerun(): después de una escritura se recargan las lecturas de la pestaña actual.
  async function afterWrite(result: Feedback) {
    setFeedback(result);
    await load();
    setVersion((v) => v + 1);
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando disposiciones…
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

  const Panel = PANELS[tab] ?? PANELS.config;

  return (
    <div>
      <div className="mb-5">
        <p className="text-sm text-slate-500">
          {data.contexto.institucion.nombre} · {data.contexto.departamento.nombre}
        </p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-brand-950">📄 Disposiciones</h2>
      </div>
      <FeedbackBox feedback={{ tone: "info", text: data.info }} />

      <div role="tablist" aria-label="Pestañas de Disposiciones" className="mb-6 mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => {
              setTab(t.key);
              setFeedback(null);
            }}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm transition ${
              tab === t.key ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {feedback && (
        <div className="whitespace-pre-line">
          <FeedbackBox feedback={feedback} />
        </div>
      )}
      {loadError && <FeedbackBox feedback={{ tone: "error", text: loadError.message }} />}
      <div role="tabpanel">
        <Panel key={tab === "config" ? `config-${version}` : tab} data={data} version={version} onDone={afterWrite} onError={handle} />
      </div>
    </div>
  );
}
