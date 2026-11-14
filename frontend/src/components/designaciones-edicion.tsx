"use client";

// Pestañas "➕ Nueva designación" (entry l. 63617-63801) y "✏️ Modificar / finalizar designación" (l. 63803-64295).
// Ambas operan siempre sobre el período abierto (aunque sea un histórico abierto por excepción).
import { useEffect, useMemo, useState } from "react";
import { Check, Field, FeedbackBox, PrimaryButton, Select, Textarea, TextInput } from "@/components/module-ui";
import {
  ACTO_INICIAL,
  ActoContextual,
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
  type ActoConfig,
  type Designacion,
  type Docente,
  type Overview,
  type Periodo,
  esNoDocente,
  horasSegunDedicacion,
  pick,
  guardarConActo,
  post,
  textoLimpio,
} from "@/lib/designaciones";

const AYUDA_NO_DOCENTE =
  "La designación se conserva administrativamente y puede usarse en disposiciones, pero no integra el plantel docente, " +
  "no suma horas contratadas docentes y no entra en los indicadores de productividad.";

// _estado_designacion_visible_v162
export const estadoVisible = (v: string | null | undefined) => {
  const t = String(v ?? "").trim();
  return t.toLocaleLowerCase() === "suspendida" ? "Suspendida (licenciada)" : t;
};

function Dos({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-5 md:grid-cols-2">{children}</div>;
}

function Col1({ children }: { children: React.ReactNode }) {
  return <div className="space-y-3">{children}</div>;
}

// ------------------------------------------------------------------ Pestaña 2: Nueva designación
const COLS_DOCENTES: Col<Docente>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "legajo", label: "Legajo" },
  { key: "titulo", label: "Título" },
  { key: "tipo_docente", label: "Tipo" },
  { key: "estado", label: "Estado" },
];

export function AltaTab({ data, version, onDone, onError }: TabProps) {
  const abierto = data.abierto;
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Registrar nueva designación</h3>
      {!abierto ? (
        <FeedbackBox feedback={{ tone: "warning", text: "Primero tenés que crear un período abierto." }} />
      ) : data.docentes.length === 0 ? (
        <FeedbackBox feedback={{ tone: "warning", text: "Primero tenés que registrar docentes." }} />
      ) : (
        <AltaForm data={data} abierto={abierto} version={version} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

function AltaForm({
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
  const c = data.catalogos;
  const hoy = hoyIso();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [cargo, setCargo] = useState(c.cargos[0]);
  const [dedicacion, setDedicacion] = useState(c.dedicaciones[0]);
  const [tipo, setTipo] = useState(c.tipos[0]);
  const [adh, setAdh] = useState(c.ad_honorem[0]);
  const [desde, setDesde] = useState(safeDate(abierto.fecha_inicio, hoy));
  const [hasta, setHasta] = useState(safeDate(abierto.fecha_fin, hoy));
  const [estado, setEstado] = useState(c.estados[0]);
  const [funcion, setFuncion] = useState(false);
  const [texto, setTexto] = useState("");
  const [obs, setObs] = useState("");
  const [acto, setActo] = useState<ActoConfig>(ACTO_INICIAL);
  const [dup, setDup] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const accion = useAccion(onDone, onError);

  const filtrados = useMemo(
    () => filtrar(data.docentes, q, ["nombre_completo", "cuil", "legajo", "titulo"]),
    [data.docentes, q]
  );
  const fila = filtrados.find((d) => d.cuil === sel) ?? filtrados[0] ?? null;
  const horas = horasSegunDedicacion(c.horas_por_dedicacion, dedicacion);
  const cuil = fila?.cuil ?? "";

  // existe_designacion_duplicada con los valores actuales del formulario (el certificado la evalúa en cada rerun).
  useEffect(() => {
    if (!cuil) return;
    let cancel = false;
    const t = setTimeout(() => {
      post<{ duplicada: boolean }>("duplicado", {
        cuil,
        cargo,
        dedicacion,
        tipo_designacion: tipo,
        ad_honorem: adh,
        estado,
        fecha_desde: desde,
        fecha_hasta: hasta,
        funcion_no_docente: funcion,
      })
        .then((r) => !cancel && setDup(r.duplicada))
        .catch(() => !cancel && setDup(false));
    }, 250);
    return () => {
      cancel = true;
      clearTimeout(t);
    };
  }, [cuil, cargo, dedicacion, tipo, adh, estado, desde, hasta, funcion, version]);

  function guardar() {
    if (funcion && !textoLimpio(texto)) {
      accion.setFeedback({ tone: "error", text: "Completá las funciones no docentes antes de guardar la designación." });
      return;
    }
    if (dup && !confirmar) {
      accion.setFeedback({
        tone: "error",
        text: "La designación exactamente igual ya existe. Marcá la confirmación si corresponde a otro acto administrativo u otra alta intencional.",
      });
      return;
    }
    accion.run(() =>
      guardarConActo("alta", {
        cuil,
        cargo,
        dedicacion,
        tipo_designacion: tipo,
        ad_honorem: adh,
        fecha_desde: desde,
        fecha_hasta: hasta,
        estado,
        funcion_no_docente: funcion,
        texto_funcion_no_docente: funcion ? texto : "",
        observaciones: obs,
        confirmar_duplicada: dup && confirmar,
        abierto_huella: data.abierto_huella,
      }, acto)
    );
  }

  return (
    <div className="space-y-5">
      <Field label="Buscar docente">
        <TextInput value={q} onChange={setQ} placeholder="Nombre, CUIL, legajo o título" />
      </Field>
      {!fila ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay docentes que coincidan con la búsqueda." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Docentes encontrados</p>
          <Tabla rows={filtrados} cols={COLS_DOCENTES} rowKey={(d) => d.cuil} selected={fila.cuil} onSelect={setSel} maxHeight="max-h-72" />
          <Dos>
            <Col1>
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
            </Col1>
            <Col1>
              <p className="text-sm font-semibold text-slate-800">Acto administrativo</p>
              <Caption>Se vincula desde el repositorio; ya no se escribe un número de resolución manualmente.</Caption>
              <Field label="Ad Honorem">
                <Select value={adh} options={c.ad_honorem} onChange={setAdh} />
              </Field>
              <Field label="Fecha desde">
                <DateInput value={desde} onChange={setDesde} />
              </Field>
              <Field label="Fecha hasta">
                <DateInput value={hasta} onChange={setHasta} />
              </Field>
              <Field label="Estado">
                <Select value={estado} options={c.estados} onChange={setEstado} />
              </Field>
            </Col1>
          </Dos>
          <div title={AYUDA_NO_DOCENTE}>
            <Check checked={funcion} onChange={setFuncion} label="Esta designación corresponde a funciones no docentes" />
          </div>
          {funcion && (
            <div className="space-y-2">
              <h4 className="text-base font-semibold text-slate-800">Funciones que cumplirá</h4>
              <FuncionNoDocenteTexto
                label="Texto para funciones no docentes"
                value={texto}
                onChange={setTexto}
                ayuda={
                  <>
                    La disposición ya aporta el texto fijo{" "}
                    <b>«ARTÍCULO 1º.– Asígnese al/la docente [nombre], CUIL N° [CUIL], el cumplimiento de funciones»</b>.
                    Completá solo la continuación, incluyendo la preposición o enlace necesario. Ejemplo:{" "}
                    <b>«de coordinación administrativa del Departamento»</b>.
                  </>
                }
                preview={(t) => `Vista previa: ARTÍCULO 1º.– Asígnese al/la docente [nombre], CUIL N° [CUIL], el cumplimiento de funciones ${t}.`}
              />
            </div>
          )}
          <Field label="Observaciones">
            <Textarea value={obs} onChange={setObs} />
          </Field>
          <ActoContextual
            titulo="Acto administrativo que aprueba la designación"
            version={version}
            value={acto}
            onChange={setActo}
            categoria={(ctx) => ctx.categoria_alta}
            tituloSugerido={`Designación — ${fila.nombre_completo}`}
            detalleSugerido={`${abierto.nombre} - ${fila.nombre_completo} - ${cargo} - ${dedicacion} - ${horas} hs - ${tipo} - Función: ${funcion ? "No docente" : "Docencia"}`}
          />
          {dup && (
            <>
              <FeedbackBox
                feedback={{
                  tone: "warning",
                  text:
                    "Ya existe una designación exactamente igual para este docente. Se permiten varias designaciones interinas " +
                    "cuando cambia la dedicación, las horas, la condición Ad Honorem, las fechas o el estado. Si esta alta " +
                    "corresponde a otra alta administrativa aunque los datos coincidan, confirmala abajo.",
                }}
              />
              <Check
                checked={confirmar}
                onChange={setConfirmar}
                label="Confirmo que corresponde registrar otra designación aunque los datos sean iguales (por ejemplo, otro acto administrativo)"
              />
            </>
          )}
          {accion.feedback && <Aviso feedback={accion.feedback} />}
          {data.permisos.puede_escribir && (
            <PrimaryButton onClick={guardar} busy={accion.busy}>
              💾 Guardar designación
            </PrimaryButton>
          )}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Pestaña 3: Modificar / finalizar
const COLS_MODIFICAR: Col<Designacion>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "cargo", label: "Cargo" },
  { key: "dedicacion", label: "Dedicación" },
  { key: "horas", label: "Hs." },
  { key: "tipo_designacion", label: "Tipo" },
  { key: "acto_administrativo", label: "Acto administrativo" },
  { key: "ad_honorem", label: "Ad Honorem" },
  { key: "funcion_no_docente", label: "Función no docente" },
  { key: "texto_funcion_no_docente", label: "Funciones no docentes" },
  { key: "estado", label: "Estado" },
  { key: "fecha_desde", label: "Desde" },
  { key: "fecha_hasta", label: "Hasta" },
];

export function ModificarTab({ data, version, onDone, onError }: TabProps) {
  const abierto = data.abierto;
  return (
    <section className="space-y-5">
      <h3 className="text-lg font-semibold text-brand-950">Modificar / finalizar designación</h3>
      <FeedbackBox
        feedback={{
          tone: "info",
          text:
            "Usá esta pestaña para cambios reales de la designación durante el período. Todo lo que guardes acá queda " +
            "registrado en Movimientos y en el Resumen docente.",
        }}
      />
      {!abierto ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay período abierto." }} />
      ) : (
        <ModificarLista data={data} abierto={abierto} version={version} onDone={onDone} onError={onError} />
      )}
    </section>
  );
}

function ModificarLista({
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
  const [sel, setSel] = useState<string | null>(null);
  const modificables = useMemo(
    () => (pd?.designaciones ?? []).filter((d) => String(d.estado ?? "").trim().toLocaleLowerCase() !== "finalizada"),
    [pd]
  );
  const filtradas = useMemo(
    () =>
      filtrar(modificables, q, ["nombre_completo", "cuil", "cargo", "dedicacion", "tipo_designacion", "acto_administrativo", "estado"]),
    [modificables, q]
  );
  if (error) return <FeedbackBox feedback={{ tone: "error", text: error }} />;
  if (!pd) return <Caption>Cargando designaciones del período abierto…</Caption>;
  if (modificables.length === 0) {
    return (
      <FeedbackBox
        feedback={{
          tone: "info",
          text: "No hay designaciones activas o modificables en el período abierto. Las finalizadas se conservan únicamente en el historial.",
        }}
      />
    );
  }
  const fila = filtradas.find((d) => String(d.id) === sel) ?? filtradas[0] ?? null;
  return (
    <div className="space-y-5">
      <Field label="Buscar designación">
        <TextInput value={q} onChange={setQ} placeholder="Docente, CUIL, cargo, dedicación o tipo" />
      </Field>
      {!fila ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay designaciones que coincidan con la búsqueda." }} />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Designaciones encontradas</p>
          <Tabla rows={filtradas} cols={COLS_MODIFICAR} rowKey={(d) => String(d.id)} selected={String(fila.id)} onSelect={setSel} maxHeight="max-h-72" />
          <FeedbackBox
            feedback={{
              tone: "info",
              text:
                `Designación actual: ${fila.cargo} - ${fila.dedicacion} - ${fila.horas ?? ""} hs - ${fila.tipo_designacion} - ` +
                `Acto administrativo: ${fila.acto_administrativo || "Pendiente de vincular"} - Ad Honorem: ${fila.ad_honorem} - ` +
                `Función: ${esNoDocente(fila.funcion_no_docente) ? "No docente" : "Docencia"} - Estado: ${estadoVisible(fila.estado)}`,
            }}
          />
          <ModificarForm key={fila.id} data={data} abierto={abierto} fila={fila} version={version} onDone={onDone} onError={onError} />
        </>
      )}
    </div>
  );
}

function ModificarForm({
  data,
  abierto,
  fila,
  version,
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
  const [tipoCambio, setTipoCambio] = useState(data.catalogos.tipos_cambio[0]);
  const [obs, setObs] = useState(fila.observaciones ?? "");
  return (
    <div className="space-y-5">
      <div className="max-w-md">
        <Field label="Tipo de modificación">
          <Select value={tipoCambio} options={data.catalogos.tipos_cambio} onChange={setTipoCambio} />
        </Field>
      </div>
      {/* Cada tipo conserva sus propios valores (las claves de widget certificadas son por tipo). */}
      <CamposTipo
        key={tipoCambio}
        data={data}
        abierto={abierto}
        fila={fila}
        tipoCambio={tipoCambio}
        obs={obs}
        setObs={setObs}
        version={version}
        onDone={onDone}
        onError={onError}
      />
    </div>
  );
}

function Dato({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <p className="text-sm text-slate-700">
      {label}: <b>{value}</b>
    </p>
  );
}

function CamposTipo({
  data,
  abierto,
  fila,
  tipoCambio,
  obs,
  setObs,
  version,
  onDone,
  onError,
}: {
  data: Overview;
  abierto: Periodo;
  fila: Designacion;
  tipoCambio: string;
  obs: string;
  setObs: (v: string) => void;
  version: number;
  onDone: OnDone;
  onError: OnError;
}) {
  const c = data.catalogos;
  const hoy = hoyIso();
  const funcionActual = esNoDocente(fila.funcion_no_docente);
  const prevista = safeDate(fila.fecha_hasta_prevista || fila.fecha_hasta, safeDate(abierto.fecha_fin, hoy));
  const [cargo, setCargo] = useState(pick(c.cargos, fila.cargo));
  const [dedicacion, setDedicacion] = useState(pick(c.dedicaciones, fila.dedicacion));
  const [tipo, setTipo] = useState(pick(c.tipos, fila.tipo_designacion));
  const [adh, setAdh] = useState(pick(c.ad_honorem, fila.ad_honorem || "No"));
  const [funcion, setFuncion] = useState(funcionActual);
  const [texto, setTexto] = useState(textoLimpio(fila.texto_funcion_no_docente));
  const [desde, setDesde] = useState(safeDate(fila.fecha_desde, safeDate(abierto.fecha_inicio, hoy)));
  const [hasta, setHasta] = useState(safeDate(fila.fecha_hasta, safeDate(abierto.fecha_fin, hoy)));
  const [estado, setEstado] = useState(pick(c.estados, fila.estado || "Activa"));
  const [fechaBaja, setFechaBaja] = useState(prevista && prevista < hoy ? prevista : hoy);
  const [motivoBaja, setMotivoBaja] = useState("");
  const [acto, setActo] = useState<ActoConfig>(ACTO_INICIAL);
  const accion = useAccion(onDone, onError);

  const esBaja = tipoCambio === "Finalizar / baja de designación";
  const cambiaFuncion = tipoCambio === "Cambio de función docente / no docente" || tipoCambio === "Modificación general";
  const nuevaFuncion = cambiaFuncion ? funcion : funcionActual;
  const horasActuales = fila.horas ?? 0;
  const nuevasHoras = horasSegunDedicacion(c.horas_por_dedicacion, dedicacion, fila.horas ?? 0);

  function guardar() {
    accion.run(() =>
      guardarConActo("modificar", {
        id: fila.id,
        huella: fila.huella,
        tipo_cambio: tipoCambio,
        cargo,
        dedicacion,
        tipo_designacion: tipo,
        ad_honorem: adh,
        funcion_no_docente: funcion,
        texto_funcion_no_docente: nuevaFuncion ? texto : "",
        fecha_desde: desde,
        fecha_hasta: hasta,
        estado,
        fecha_baja: fechaBaja,
        motivo_baja: motivoBaja,
        observaciones: obs,
      }, acto)
    );
  }

  let campos: React.ReactNode = null;
  if (tipoCambio === "Cambio de cargo") {
    campos = (
      <Dos>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Datos actuales</p>
          <Dato label="Cargo actual" value={fila.cargo} />
          <Dato label="Dedicación actual" value={fila.dedicacion} />
          <Dato label="Horas actuales" value={`${fila.horas ?? ""} hs`} />
        </Col1>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Nuevo dato</p>
          <Field label="Nuevo cargo">
            <Select value={cargo} options={c.cargos} onChange={setCargo} />
          </Field>
        </Col1>
      </Dos>
    );
  } else if (tipoCambio === "Aumento de dedicación" || tipoCambio === "Disminución de dedicación") {
    campos = (
      <>
        <Dos>
          <Col1>
            <p className="text-sm font-semibold text-slate-800">Dedicación actual</p>
            <Dato label="Dedicación" value={fila.dedicacion} />
            <Dato label="Horas" value={`${fila.horas ?? ""} hs`} />
          </Col1>
          <Col1>
            <p className="text-sm font-semibold text-slate-800">Nueva dedicación</p>
            <Field label="Nueva dedicación">
              <Select value={dedicacion} options={c.dedicaciones} onChange={setDedicacion} />
            </Field>
            <FeedbackBox feedback={{ tone: "info", text: `Horas automáticas con la nueva dedicación: ${nuevasHoras} hs` }} />
          </Col1>
        </Dos>
        {tipoCambio === "Aumento de dedicación" && nuevasHoras <= horasActuales && (
          <FeedbackBox
            feedback={{ tone: "warning", text: "Elegiste aumento de dedicación, pero las nuevas horas no son mayores que las actuales." }}
          />
        )}
        {tipoCambio === "Disminución de dedicación" && nuevasHoras >= horasActuales && (
          <FeedbackBox
            feedback={{ tone: "warning", text: "Elegiste disminución de dedicación, pero las nuevas horas no son menores que las actuales." }}
          />
        )}
      </>
    );
  } else if (tipoCambio === "Cambio de tipo de designación") {
    campos = (
      <Dos>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Dato actual</p>
          <Dato label="Tipo actual" value={fila.tipo_designacion} />
        </Col1>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Nuevo dato</p>
          <Field label="Nuevo tipo de designación">
            <Select value={tipo} options={c.tipos} onChange={setTipo} />
          </Field>
        </Col1>
      </Dos>
    );
  } else if (tipoCambio === "Cambio de condición Ad Honorem") {
    campos = (
      <Dos>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Dato actual</p>
          <Dato label="Ad Honorem actual" value={fila.ad_honorem} />
        </Col1>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Nuevo dato</p>
          <Field label="Nueva condición Ad Honorem">
            <Select value={adh} options={c.ad_honorem} onChange={setAdh} />
          </Field>
        </Col1>
      </Dos>
    );
  } else if (tipoCambio === "Cambio de función docente / no docente") {
    campos = (
      <Dos>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Dato actual</p>
          <Dato label="Función actual" value={funcionActual ? "No docente" : "Docencia"} />
        </Col1>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Nuevo dato</p>
          <div title="Al marcarla queda fuera del plantel y de la productividad docente.">
            <Check checked={funcion} onChange={setFuncion} label="Designación para funciones no docentes" />
          </div>
        </Col1>
      </Dos>
    );
  } else if (esBaja) {
    campos = (
      <Dos>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Designación a finalizar</p>
          <Dato label="Cargo" value={fila.cargo} />
          <Dato label="Dedicación" value={fila.dedicacion} />
          <Dato label="Horas" value={`${fila.horas ?? ""} hs`} />
          <Dato label="Tipo" value={fila.tipo_designacion} />
          <Dato label="Vencimiento previsto" value={prevista} />
        </Col1>
        <Col1>
          <p className="text-sm font-semibold text-slate-800">Datos de baja efectiva</p>
          <Field label="Fecha efectiva de finalización">
            <DateInput value={fechaBaja} onChange={setFechaBaja} />
          </Field>
          <Field label="Motivo / observación de la baja (opcional)">
            <Textarea value={motivoBaja} onChange={setMotivoBaja} />
          </Field>
          <Caption>
            El vencimiento previsto no se modifica. La aplicación guarda por separado la fecha efectiva de baja y la
            fecha/hora en que registraste la operación.
          </Caption>
        </Col1>
      </Dos>
    );
  } else if (tipoCambio === "Modificación general") {
    campos = (
      <Dos>
        <Col1>
          <Field label="Cargo">
            <Select value={cargo} options={c.cargos} onChange={setCargo} />
          </Field>
          <Field label="Dedicación">
            <Select value={dedicacion} options={c.dedicaciones} onChange={setDedicacion} />
          </Field>
          <Caption>
            Horas automáticas según dedicación: <b>{nuevasHoras} hs</b>
          </Caption>
          <Field label="Tipo designación">
            <Select value={tipo} options={c.tipos} onChange={setTipo} />
          </Field>
        </Col1>
        <Col1>
          <Caption>El acto administrativo de esta modificación se vincula desde el repositorio más abajo.</Caption>
          <Field label="Ad Honorem">
            <Select value={adh} options={c.ad_honorem} onChange={setAdh} />
          </Field>
          <Field label="Fecha desde">
            <DateInput value={desde} onChange={setDesde} />
          </Field>
          <Field label="Fecha hasta">
            <DateInput value={hasta} onChange={setHasta} />
          </Field>
          <Field label="Estado">
            <Select value={estado} options={c.estados} onChange={setEstado} />
          </Field>
          <div title="Se excluye del plantel y de la productividad docente, pero conserva su existencia administrativa.">
            <Check checked={funcion} onChange={setFuncion} label="Designación para funciones no docentes" />
          </div>
        </Col1>
      </Dos>
    );
  }

  return (
    <div className="space-y-5">
      {campos}
      {nuevaFuncion && !esBaja && (
        <div className="space-y-2">
          <h4 className="text-base font-semibold text-slate-800">Funciones no docentes de esta designación</h4>
          <FuncionNoDocenteTexto
            label="Funciones que cumplirá"
            value={texto}
            onChange={setTexto}
            ayuda={
              <>
                La disposición ya aporta <b>«…el cumplimiento de funciones»</b>. Completá la continuación, por ejemplo:{" "}
                <b>«de coordinación administrativa del Departamento»</b>.
              </>
            }
            preview={(t) => `Vista previa: «…el cumplimiento de funciones ${t}.»`}
          />
        </div>
      )}
      <Field label="Observaciones / motivo de la modificación">
        <Textarea value={obs} onChange={setObs} />
      </Field>
      {c.movimientos_con_acto.includes(tipoCambio) && (
        <ActoContextual
          titulo="Acto administrativo que aprueba esta modificación"
          version={version}
          value={acto}
          onChange={setActo}
          categoria={(ctx) => ctx.categorias[tipoCambio] ?? "Designación docente"}
          tituloSugerido={`${tipoCambio} — ${fila.nombre_completo}`}
        />
      )}
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {data.permisos.puede_escribir && (
        <PrimaryButton onClick={guardar} busy={accion.busy}>
          ✏️ Guardar modificación registrada
        </PrimaryButton>
      )}
    </div>
  );
}
