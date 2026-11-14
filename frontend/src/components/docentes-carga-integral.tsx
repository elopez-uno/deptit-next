"use client";

// E4-09: "Carga rápida integral de docentes y designaciones" (B13-FIX02 entry l. 61278-61652). Un único Excel con las
// hojas Docentes y Designaciones: revisión previa (sin escribir) y carga con confirmación. La lectura y la revisión
// las hace el servidor con el código certificado; la escritura, los owners (Docentes y Designaciones).
import { useEffect, useState } from "react";
import {
  Check,
  type Column,
  DataTable,
  Details,
  type Feedback,
  FeedbackBox,
  Field,
  PrimaryButton,
  TextInput,
} from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import {
  type DocentesOverview,
  type FilaRevision,
  type ResultadoIntegral,
  type RevisionIntegral,
  docentesApi,
} from "@/lib/docentes";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;

const AYUDA_SOLO_LECTURA = "Tu rol permite visualizar, pero no cargar, editar ni generar cambios.";
const COLUMNAS_DOCENTES = ["fila", "cuil", "apellido", "nombres", "legajo", "antiguedad_anios", "nivel_posgrado_salarial",
  "estado", "accion", "motivo"];
const COLUMNAS_DESIGNACIONES = ["fila", "periodo", "docente", "cuil", "cargo", "dedicacion", "horas", "tipo_designacion",
  "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "accion", "motivo"];
const COLUMNAS_RESULTADO = ["Fila", "Docente", "CUIL", "Período", "Resultado", "Detalle"];

const columnas = (filas: FilaRevision[], orden: string[]): Column<FilaRevision>[] =>
  orden.filter((c) => filas.length === 0 || c in filas[0]).map((c) => ({ key: c, label: c }));

function Negrita({ texto }: { texto: string }) {
  const partes = texto.split("**");
  return <>{partes.map((p, i) => (i % 2 ? <b key={i}>{p}</b> : <span key={i}>{p}</span>))}</>;
}

function Caption({ texto }: { texto: string }) {
  return (
    <p className="text-xs text-slate-500">
      <Negrita texto={texto} />
    </p>
  );
}

function Metrica({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-brand-950">{value}</p>
    </div>
  );
}

function entero(v: string, min: number, max: number, fallback: number) {
  const n = Number(v);
  return Number.isInteger(n) && n >= min && n <= max ? n : fallback;
}

export function CargaIntegral({ data, onDone, onError }: { data: DocentesOverview; onDone: OnDone; onError: OnError }) {
  const [filasDoc, setFilasDoc] = useState("1000");
  const [filasDes, setFilasDes] = useState("5000");
  const [descargando, setDescargando] = useState(false);
  const [modeloError, setModeloError] = useState<string | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [revision, setRevision] = useState<RevisionIntegral | null>(null);
  const [lecturaError, setLecturaError] = useState<string | null>(null);
  const [actualizar, setActualizar] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [resultado, setResultado] = useState<ResultadoIntegral | null>(null);
  const [vista, setVista] = useState<"docentes" | "designaciones">("docentes");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const puede = data.permisos.puede_escribir;

  // Cada rerun certificado vuelve a leer y revisar el archivo subido (también después de cargar).
  useEffect(() => {
    let cancelled = false;
    if (!archivo) return;
    docentesApi
      .revisarIntegral(archivo)
      .then((r) => {
        if (!cancelled) {
          setRevision(r);
          setLecturaError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setRevision(null);
          setLecturaError(onError(e).message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [archivo, version, onError]);

  async function descargar() {
    setDescargando(true);
    setModeloError(null);
    try {
      const blob = await docentesApi.modeloIntegral(entero(filasDoc, 20, 1048575, 1000), entero(filasDes, 20, 1048575, 5000));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "modelo_integral_docentes_designaciones.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setModeloError(onError(e).message);
    } finally {
      setDescargando(false);
    }
  }

  async function cargar() {
    setError(null);
    if (!archivo || !revision) return;
    if (!confirmar) {
      setError("Primero confirmá que revisaste el archivo.");
      return;
    }
    setBusy(true);
    try {
      const r = await docentesApi.cargarIntegral(archivo, {
        confirmar: true,
        actualizar_existentes: actualizar,
        huella: revision.huella,
      });
      setResultado(r);
      await onDone(null);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }

  const r = revision;
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-brand-950">Carga rápida integral de docentes y designaciones</h3>
      <Caption texto="Descargá un único Excel, completá las hojas Docentes y Designaciones y subí el archivo completo. El sistema registra primero los docentes y después sus designaciones, vinculándolos por CUIL." />
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "No existe un cupo de docentes ni de designaciones por departamento. La cantidad de filas preformateadas del " +
            "Excel es solo una comodidad de carga y no limita lo que el sistema puede guardar.",
        }}
      />
      <Details summary="⚙️ Tamaño inicial del modelo Excel">
        <Caption texto="Elegí cuántas filas querés que vengan ya preparadas con formato y listas. Si luego agregás más filas al archivo, el importador también las lee. El único límite físico es el propio formato XLSX." />
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Filas preformateadas — Docentes">
            <TextInput type="number" value={filasDoc} onChange={setFilasDoc} />
          </Field>
          <Field label="Filas preformateadas — Designaciones">
            <TextInput type="number" value={filasDes} onChange={setFilasDes} />
          </Field>
        </div>
      </Details>
      <div title="Incluye hojas separadas para docentes y designaciones, períodos, docentes existentes, listas válidas e instrucciones.">
        <PrimaryButton tone="secondary" onClick={descargar} busy={descargando}>
          📥 Descargar Excel integral de docentes y designaciones
        </PrimaryButton>
      </div>
      {modeloError && <FeedbackBox feedback={{ tone: "warning", text: modeloError }} />}
      <Field label="Subir Excel integral completado" hint="El archivo debe conservar las hojas Docentes y Designaciones.">
        <input
          type="file"
          accept=".xlsx"
          aria-label="Subir Excel integral completado"
          className="block text-sm"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setArchivo(f);
            setRevision(null);
            setLecturaError(null);
            setError(null);
          }}
        />
      </Field>

      {resultado && (
        <div className="space-y-3">
          <FeedbackBox feedback={{ tone: resultado.errores > 0 ? "warning" : "success", text: resultado.mensaje }} />
          {resultado.detalle.length > 0 && (
            <>
              <p className="text-sm font-semibold text-slate-700">Verificación contra la base de datos</p>
              <DataTable
                rows={resultado.detalle}
                columns={COLUMNAS_RESULTADO.map((c) => ({ key: c, label: c }))}
                rowKey={(_, i) => String(i)}
                maxHeight="max-h-72"
              />
            </>
          )}
          {resultado.errores_detalle.length > 0 && (
            <Details summary="Ver errores de ejecución">
              <ul className="list-disc pl-5 text-sm text-slate-700">
                {resultado.errores_detalle.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </Details>
          )}
        </div>
      )}

      {archivo && lecturaError && <FeedbackBox feedback={{ tone: "error", text: lecturaError }} />}
      {archivo && r && (
        <div className="space-y-4">
          {r.avisos.map((a) => (
            <FeedbackBox key={a} feedback={{ tone: "info", text: a }} />
          ))}
          <Caption
            texto={`Filas con datos detectadas en el archivo: Docentes **${r.filas_docentes}** | Designaciones **${r.filas_designaciones}**. El importador procesa todas las filas detectadas; no corta por cantidad.`}
          />
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Metrica label="Docentes nuevos" value={r.docentes_nuevos} />
            <Metrica label="Docentes existentes" value={r.docentes_existentes} />
            <Metrica label="Designaciones nuevas" value={r.designaciones_nuevas} />
            <Metrica label="Errores" value={r.errores} />
          </div>
          {r.designaciones_omitidas > 0 && (
            <Caption texto={`Designaciones duplicadas que se omitirán automáticamente: ${r.designaciones_omitidas}.`} />
          )}
          <Caption
            texto={`Control de Designaciones: detectadas ${r.designaciones_detectadas} | nuevas ${r.designaciones_nuevas} | duplicadas ${r.designaciones_omitidas} | errores ${r.errores_designaciones}.`}
          />
          <Caption texto="El Período se detecta automáticamente desde Fecha desde/Fecha hasta y el Estado se deriva de si ese período es el último cronológico. El control de duplicados compara período detectado + CUIL + cargo + dedicación + horas + tipo de designación + N° de resolución + condición Ad Honorem + fechas. El estado Activa/Finalizada no crea una designación distinta. La verificación posterior a la carga se hace directamente contra la base, sin usar caché y sin forzar segundas inserciones." />
          <div role="tablist" aria-label="Revisión del Excel integral" className="flex gap-1 border-b border-slate-200">
            {(
              [
                ["docentes", "👤 Revisión de docentes"],
                ["designaciones", "📋 Revisión de designaciones"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                role="tab"
                aria-selected={vista === k}
                onClick={() => setVista(k)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  vista === k ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {vista === "docentes" ? (
            r.docentes.length === 0 ? (
              <FeedbackBox feedback={{ tone: "info", text: "La hoja Docentes no contiene filas para procesar." }} />
            ) : (
              <DataTable rows={r.docentes} columns={columnas(r.docentes, COLUMNAS_DOCENTES)} rowKey={(_, i) => `d${i}`} maxHeight="max-h-72" />
            )
          ) : r.designaciones.length === 0 ? (
            <FeedbackBox feedback={{ tone: "info", text: "La hoja Designaciones no contiene filas para procesar." }} />
          ) : (
            <DataTable
              rows={r.designaciones}
              columns={columnas(r.designaciones, COLUMNAS_DESIGNACIONES)}
              rowKey={(_, i) => `e${i}`}
              maxHeight="max-h-72"
            />
          )}
          {r.docentes_existentes > 0 && (
            <div
              className="space-y-1"
              title={
                "Desmarcado: los docentes existentes no se modifican, pero sí pueden recibir nuevas designaciones. " +
                "Marcado: solo se actualizan los campos que tengan un valor en la hoja Docentes; las celdas vacías " +
                "conservan el dato que ya existe en el sistema."
              }
            >
              <Check
                checked={actualizar}
                onChange={setActualizar}
                label="Actualizar los datos personales de los docentes que ya existen"
              />
              {actualizar && (
                <Caption texto="Actualización parcial activa: las celdas vacías de docentes existentes no borran información. Solo se reemplazan los campos que tengan un valor en el Excel." />
              )}
            </div>
          )}
          <Check
            checked={confirmar && r.sin_errores}
            onChange={setConfirmar}
            disabled={!r.sin_errores}
            label="Confirmo que revisé el archivo y quiero registrar los datos válidos"
          />
          {!r.sin_errores && (
            <FeedbackBox
              feedback={{
                tone: "error",
                text: "Corregí los errores indicados en el Excel y volvé a subirlo. No se guardó ningún dato.",
              }}
            />
          )}
          <div title={puede ? undefined : AYUDA_SOLO_LECTURA} className="inline-block">
            <PrimaryButton busy={busy} disabled={!r.sin_errores || !puede} onClick={cargar}>
              📥 Cargar docentes y designaciones del Excel
            </PrimaryButton>
          </div>
          {error && <FeedbackBox feedback={{ tone: "error", text: error }} />}
        </div>
      )}
    </div>
  );
}
