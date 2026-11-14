"use client";

// Pestaña 📥 Carga rápida (render_carga_rapida_proyectos_v217 l. 49210): Excel integral (Carga rápida + Asignar docentes),
// vista previa y procesamiento en dos operaciones independientes (proyectos y luego asignaciones). Cualquier error de
// validación de una operación impide toda su escritura; si falla la segunda, los proyectos de la primera quedan.
import { useState } from "react";
import { Card, Check, Field, FeedbackBox, PrimaryButton } from "@/components/module-ui";
import { Aviso, Caption, Cargando, SoloLectura, TablaLibre, type TabProps, feedbackDe } from "@/components/extension-shared";
import { type Fila, type WriteResult, archivoBase64, download, extensionApi, post } from "@/lib/extension";
import { useAccion } from "@/components/extension-shared";

type Preview = { proyectos: Fila[]; asignaciones: Fila[] };

export function CargaTab({ data, onDone, onError }: TabProps) {
  const [aviso, setAviso] = useState<string | null>(null);
  const [bajando, setBajando] = useState(false);
  const [archivo, setArchivo] = useState<{ nombre: string; b64: string } | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<ReturnType<typeof feedbackDe> | null>(null);
  const [leyendo, setLeyendo] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [resultado, setResultado] = useState<WriteResult | null>(null);
  const accion = useAccion(async (f, p) => {
    setArchivo(null);
    setPreview(null);
    setConfirmar(false);
    await onDone(f, p);
  }, onError);

  async function bajar() {
    setBajando(true);
    setAviso(null);
    try {
      download(await extensionApi.modeloExcel());
    } catch (e) {
      setAviso(`No se pudo generar el Excel modelo: ${onError(e).message}`);
    } finally {
      setBajando(false);
    }
  }

  async function elegir(file: File | null) {
    setPreview(null);
    setPreviewError(null);
    setResultado(null);
    setConfirmar(false);
    if (!file) {
      setArchivo(null);
      return;
    }
    const b64 = await archivoBase64(file);
    setArchivo({ nombre: file.name, b64 });
    setLeyendo(true);
    try {
      setPreview(await post<Preview>("carga-rapida/previsualizar", { archivo: b64 }));
    } catch (e) {
      setPreviewError(feedbackDe(onError(e)));
    } finally {
      setLeyendo(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Carga rápida de proyectos de extensión</h3>
        <Caption>
          El mismo archivo permite dos cosas: registrar proyectos nuevos y asignar docentes del período a proyectos. La hoja
          &apos;Carga rápida&apos; administra proyectos y la hoja &apos;Asignar docentes&apos; permite cargar una fila por docente/proyecto.
        </Caption>
      </div>
      {!data.abierto && (
        <Aviso feedback={{ tone: "warning", text: "No hay un período abierto. Podés cargar proyectos, pero para asignar docentes primero debe existir un período abierto." }} />
      )}
      {aviso && <FeedbackBox feedback={{ tone: "warning", text: aviso }} />}
      <Card>
        <PrimaryButton tone="secondary" busy={bajando} onClick={bajar}>
          📥 Descargar Excel integral de proyectos y docentes de extensión
        </PrimaryButton>
        <Field label="Subir Excel completo" hint="Usá preferentemente el modelo integral descargable de esta misma pestaña.">
          <input
            type="file"
            accept=".xlsx"
            className="block text-sm"
            onChange={(e) => elegir(e.target.files?.[0] ?? null)}
          />
        </Field>
        {leyendo && <Cargando text="Leyendo el Excel…" />}
        {previewError && <Aviso feedback={previewError} />}
        {preview && archivo && (
          <div className="space-y-3">
            {preview.proyectos.length > 0 && (
              <>
                <p className="text-sm font-semibold">Vista previa de proyectos nuevos</p>
                <TablaLibre rows={preview.proyectos} />
                <Caption>Proyectos nuevos detectados: {preview.proyectos.length}</Caption>
              </>
            )}
            {preview.asignaciones.length > 0 && (
              <>
                <p className="text-sm font-semibold">Vista previa de asignaciones docentes nuevas</p>
                <TablaLibre rows={preview.asignaciones} />
                <Caption>Asignaciones docentes nuevas detectadas: {preview.asignaciones.length}</Caption>
              </>
            )}
            {!data.permisos.puede_cargar ? (
              <SoloLectura />
            ) : (
              <>
                <Check checked={confirmar} onChange={setConfirmar} label="Confirmo que quiero procesar esta carga de extensión" />
                {accion.feedback && <Aviso feedback={accion.feedback} />}
                <PrimaryButton
                  busy={accion.busy}
                  disabled={!confirmar}
                  onClick={() =>
                    accion.run(
                      () => post<WriteResult>("carga-rapida", { archivo: archivo.b64, confirmar, huella_periodo: data.huella_periodo }),
                      (r) => setResultado(r)
                    )
                  }
                >
                  🚀 Procesar carga rápida
                </PrimaryButton>
              </>
            )}
          </div>
        )}
      </Card>
      {resultado && (resultado.detalle_proyectos?.length || resultado.detalle_asignaciones?.length) ? (
        <Card>
          {!!resultado.detalle_proyectos?.length && (
            <>
              <p className="text-sm font-semibold">Resultado de proyectos</p>
              <TablaLibre rows={resultado.detalle_proyectos} />
            </>
          )}
          {!!resultado.detalle_asignaciones?.length && (
            <>
              <p className="text-sm font-semibold">Resultado de asignaciones docentes</p>
              <TablaLibre rows={resultado.detalle_asignaciones} />
            </>
          )}
        </Card>
      ) : null}
    </section>
  );
}
