"use client";

// Pestaña "📥 Carga rápida" (entry l. 70645-70822): Excel integral modelo, Excel completado de cualquier período (sin
// compuerta), y carga desde Excel subido o texto pegado con vista previa OK / ADVERTENCIA / DUPLICADA / ERROR.
// La carga (lote v232, un COMMIT) solo en el período actual abierto; el backend recalcula la vista previa antes de
// escribir y rechaza la carga si cambió.
import { useState } from "react";
import { periodoPorDefecto, SelectorPeriodo } from "@/components/comisiones-periodo";
import { Aviso, Caption, Cargando, Metric, SoloLectura, Tabla, type TabProps, useConsulta } from "@/components/comisiones-shared";
import { useAccion } from "@/components/designaciones-shared";
import { Card, Check, Field, FeedbackBox, PrimaryButton, Textarea } from "@/components/module-ui";
import { type Preview, type WriteResult, archivoBase64, comisionesApi, download, post } from "@/lib/comisiones";

const COLS_PREVIEW = [
  "estado_validacion",
  "motivo",
  "advertencia",
  "clave_generada",
  "codigos_comision",
  "codigo",
  "asignatura",
  "opcion_curricular",
  "comision",
  "turno",
  "resumen_horarios",
  "resumen_docentes",
  "materia_encontrada",
  "modalidad",
  "sede",
  "estado",
].map((k) => ({ key: k, label: k }));

const sinMd = (t: string) => t.replaceAll("**", "");

export function CargaRapidaTab({ data, version, onDone, onError }: TabProps) {
  const [error, setError] = useState<string | null>(null);
  const [bajando, setBajando] = useState<string | null>(null);
  const [nombreExport, setNombreExport] = useState(() => periodoPorDefecto(data));
  const periodoExport = data.periodos.find((p) => String(p.nombre) === nombreExport);

  async function bajar(tipo: "modelo" | "completado") {
    setBajando(tipo);
    setError(null);
    try {
      download(tipo === "modelo" ? await comisionesApi.modeloExcel() : await comisionesApi.periodoExcel(periodoExport!.id));
    } catch (e) {
      setError(
        (tipo === "modelo" ? "No se pudo generar el Excel modelo: " : "No se pudo preparar el Excel completado del período seleccionado: ") +
          onError(e).message
      );
    } finally {
      setBajando(null);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Carga rápida de comisiones</h3>
        <Caption>
          Podés subir el Excel integral completo o usar el método manual de copiar y pegar. Se ignoran Cupo Total y Clave
          Comisión. Para Optativas/Electivas, completá también Opción Curricular con la materia concreta ofrecida.
        </Caption>
      </div>
      {error && <FeedbackBox feedback={{ tone: "warning", text: error }} />}
      <Card>
        <PrimaryButton tone="secondary" onClick={() => bajar("modelo")} busy={bajando === "modelo"}>
          📥 Descargar Excel integral de comisiones
        </PrimaryButton>
        <Caption>
          En la hoja Carga rápida, cada Carrera / plan está ubicada inmediatamente después de su Asignatura y su desplegable
          muestra solamente las alternativas compatibles con esa materia. Si hay una sola posibilidad, se completa
          automáticamente; si hay varias, elegís el grupo correcto y el Código se completa con esa combinación. Asignatura 2/3
          siguen permitiendo comisiones multicódigo. Para cada Docente 1 a 5, cada uno de los hasta 5 horarios generales
          existentes queda automáticamente con Cubre Horario = Sí y el Día Docente correspondiente. Si no cubre uno de esos
          horarios, cambiá ese selector a No. Si queda en Sí y dejás Inicio/Fin Docente vacíos, cubre el horario completo; si
          informás Inicio/Fin, cubre solo esa subfranja. Todas las horas usan listas cada 30 minutos. Los Excel anteriores
          siguen siendo compatibles. Guardá el libro y subilo completo acá; si preferís, también podés copiar y pegar la hoja
          Carga rápida.
        </Caption>
        {data.periodos.length > 0 && (
          <>
            <h4 className="text-base font-semibold text-brand-950">Exportar comisiones ya cargadas</h4>
            <SelectorPeriodo data={data} value={nombreExport} onChange={setNombreExport} label="Período a exportar" />
            <PrimaryButton tone="secondary" onClick={() => bajar("completado")} busy={bajando === "completado"} disabled={!periodoExport}>
              📥 Descargar Excel integral completado · período seleccionado
            </PrimaryButton>
            <Caption>
              Esta exportación no modifica datos: sirve como copia integral del período elegido y conserva el formato del Excel de
              Carga rápida.
            </Caption>
          </>
        )}
      </Card>
      {!data.puede_operar ? (
        <Aviso feedback={{ tone: "warning", text: "Solo podés hacer carga rápida de comisiones en el período actual abierto." }} />
      ) : !data.actual ? (
        <Aviso feedback={{ tone: "warning", text: "No hay período actual para cargar comisiones." }} />
      ) : (
        <Carga data={data} version={version} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

function Carga({ data, version, onDone, onError }: TabProps) {
  const puede = data.permisos.puede_escribir;
  const [texto, setTexto] = useState("");
  const [archivo, setArchivo] = useState<{ nombre: string; b64: string } | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);
  const hayFuente = !!archivo || !!texto.trim();
  const prev = useConsulta<Preview>(
    "carga-rapida/previsualizar",
    { texto, excel: archivo?.b64 ?? null },
    onError,
    version,
    hayFuente
  );
  const p = hayFuente ? prev.data : null;

  async function elegir(file: File | null) {
    if (!file) {
      setArchivo(null);
      return;
    }
    setArchivo({ nombre: file.name, b64: await archivoBase64(file) });
  }

  async function cargar() {
    await accion.run(
      () =>
        post<WriteResult>("carga-rapida", {
          texto,
          excel: archivo?.b64 ?? null,
          confirmar,
          huella: p?.huella ?? null,
        }),
      () => {
        setConfirmar(false);
      }
    );
  }

  return (
    <div className="space-y-4">
      <Aviso
        feedback={{
          tone: "info",
          text: sinMd(
            "Formato recomendado: **Código | Asignatura | Carrera / plan** para cada materia de la comisión. El modelo trae tres bloques de materia; al pegar siguen aceptándose Código/Asignatura/Carrera-plan 4, 5, etc. Carrera / plan sirve únicamente para desambiguar grupos conceptuales y en el Excel ya queda filtrada según la Asignatura elegida. Para Optativas/Electivas usá **Opción Curricular**; para materias comunes dejala vacía. Los horarios generales se cargan con Día N / Hora Inicio N / Hora Fin N, con hasta 5 horarios/días por comisión. Además, cada **Docente N** trae **Cubre Horario M - Docente N (Sí/No)** junto con las columnas históricas **Día Docente N Horario M / Hora Inicio Docente N Horario M / Hora Fin Docente N Horario M**. Por defecto, al elegir docente, cada horario general existente queda en Sí. **No** excluye ese horario; Sí con horas propias vacías cubre el horario completo; Sí con Inicio/Fin cubre solo esa subfranja. Los archivos anteriores sin la columna Cubre Horario conservan la lógica previa. El cargo se obtiene automáticamente desde la designación activa de mayor jerarquía. Turnos válidos: mañana, tarde y noche. Modalidades: Presencial, Virtual e Híbrida."
          ),
        }}
      />
      {!puede && <SoloLectura />}
      <Field label="Subir Excel integral de comisiones completado" hint="Usá el modelo descargado en esta misma pestaña y conservá la hoja 'Carga rápida'.">
        <input
          key={archivo ? "con-archivo" : "sin-archivo"}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="block w-full text-sm text-slate-600"
          onChange={(e) => elegir(e.target.files?.[0] ?? null)}
        />
      </Field>
      {archivo && (
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <span>Archivo: {archivo.nombre}</span>
          <button type="button" className="text-brand-700 underline" onClick={() => setArchivo(null)}>
            Quitar archivo
          </button>
        </div>
      )}
      <p className="text-sm font-semibold text-slate-700">O, si preferís el método manual:</p>
      <Field label="Pegá acá las comisiones con horarios">
        <Textarea
          value={texto}
          onChange={setTexto}
          rows={9}
          placeholder={"Código\tAsignatura\tComisión\tTurno\tDía 1\tHora Inicio 1\tHora Fin 1\t...\tDía 5\tHora Inicio 5\tHora Fin 5\tModalidad\tSede"}
        />
      </Field>
      {hayFuente && prev.loading && <Cargando text="Preparando vista previa…" />}
      {hayFuente && prev.error && <FeedbackBox feedback={prev.error} />}
      {p?.mensajes.map((m, i) => (
        <Aviso key={i} feedback={{ tone: m.tono, text: sinMd(m.texto) }} />
      ))}
      {p && p.filas.length > 0 && p.totales && (
        <>
          <h4 className="text-base font-semibold text-brand-950">Vista previa</h4>
          <Tabla rows={p.filas} cols={COLS_PREVIEW} rowKey={(r) => JSON.stringify(r)} maxHeight="max-h-96" />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric label="Listas" value={p.totales.ok} />
            <Metric label="Con advertencia" value={p.totales.advertencia} />
            <Metric label="Duplicadas" value={p.totales.duplicada} />
            <Metric label="Con error" value={p.totales.error} />
          </div>
          {p.totales.advertencia > 0 && (
            <Aviso feedback={{ tone: "warning", text: "Hay filas con advertencia: se pueden cargar, pero revisá la materia encontrada antes de confirmar." }} />
          )}
          {p.totales.duplicada > 0 && (
            <Aviso feedback={{ tone: "warning", text: "Hay comisiones duplicadas. No se van a cargar para evitar repetir datos." }} />
          )}
          {p.totales.error > 0 && (
            <Aviso feedback={{ tone: "error", text: "Hay filas con errores. No se cargan hasta corregir código/asignatura u horarios." }} />
          )}
          <Check
            checked={confirmar}
            onChange={setConfirmar}
            disabled={!puede}
            label="Confirmo que quiero cargar solamente las comisiones válidas o con advertencia y omitir duplicadas/errores"
          />
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {puede && (
            <PrimaryButton onClick={cargar} busy={accion.busy}>
              📥 Cargar comisiones válidas
            </PrimaryButton>
          )}
        </>
      )}
    </div>
  );
}
