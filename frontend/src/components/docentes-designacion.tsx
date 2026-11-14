"use client";

// E4-08: registrar una designación desde la pestaña "Registrar docente" (B13-FIX02 entry l. 59947-60392).
// Tres caminos certificados: reincorporar desde la base maestra, CUIL de otro departamento → propio + designación y
// CUIL ya local → nueva designación. El alta la hace Designaciones (owner); esta pantalla solo arma el formulario.
// 6A-B3: acto administrativo opcional con el MISMO control que el alta de Designaciones (ActoContextual: repositorio,
// nuevo acto ahora o pendiente); el vínculo real por documento_id lo escribe FastAPI con los writers ya certificados.
import { useEffect, useMemo, useState } from "react";
import { ActoContextual } from "@/components/designaciones-shared";
import {
  Check,
  type Column,
  DataTable,
  type Feedback,
  FeedbackBox,
  Field,
  PrimaryButton,
  Select,
  Textarea,
  TextInput,
} from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type ActoConfig, horasSegunDedicacion } from "@/lib/designaciones";
import {
  type CatalogosDesignacion,
  type ContextoDesignacion,
  type DesignacionDocenteForm,
  type OtroDepartamento,
  type RegistroDesignacion,
  type Reincorporable,
  docentesApi,
  filtrarPorTexto,
  today,
} from "@/lib/docentes";

type OnDone = (f: Feedback) => Promise<void>;
type OnError = (e: unknown) => ApiError;
type Periodo = NonNullable<ContextoDesignacion["abierto"]>;

const AYUDA_SOLO_LECTURA = "Tu rol permite visualizar, pero no cargar, editar ni generar cambios.";
// Sin elegir nada, el registro sigue como antes (sin acto, pendiente de vincular).
const ACTO_PENDIENTE: ActoConfig = { modo: "pendiente", documento_id: null };
const TITULO_ACTO = "Acto administrativo que aprueba la designación";

// safe_date(periodo["fecha_inicio"|"fecha_fin"], date.today()).
const fechaPeriodo = (valor: string | null | undefined) => (valor && /^\d{4}-\d{2}-\d{2}/.test(valor) ? valor.slice(0, 10) : today());

const formInicial = (c: CatalogosDesignacion, periodo: Periodo): DesignacionDocenteForm => ({
  cargo: c.cargos[0],
  dedicacion: c.dedicaciones[0],
  tipo_designacion: c.tipos[0],
  ad_honorem: c.ad_honorem[0],
  fecha_desde: fechaPeriodo(periodo.fecha_inicio),
  fecha_hasta: fechaPeriodo(periodo.fecha_fin),
  estado: c.estados[0],
  funcion_no_docente: false,
  texto_funcion_no_docente: "",
  observaciones: "",
});

function Negrita({ texto }: { texto: string }) {
  const partes = texto.split("**");
  return <>{partes.map((p, i) => (i % 2 ? <b key={i}>{p}</b> : <span key={i}>{p}</span>))}</>;
}

function Caption({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500">{children}</p>;
}

function useContexto(version: unknown, onError: OnError) {
  const [ctx, setCtx] = useState<ContextoDesignacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    docentesApi
      .designacionContexto()
      .then((r) => {
        if (!cancelled) {
          setCtx(r);
          setError(null);
        }
      })
      .catch((e) => !cancelled && setError(onError(e).message));
    return () => {
      cancelled = true;
    };
  }, [version, onError]);
  return { ctx, error };
}

// Textos que cambian entre el formulario del camino 1 (l. 60036-60083) y formulario_designacion_registro_docente
// (l. 23894-23962, caminos 2 y 3).
const VARIANTES = {
  reincorporar: {
    titulo: "Nueva designación para el período",
    tipo: "Tipo designación",
    ayudaFuncion:
      "Marcá esta opción cuando la designación se utiliza para cumplir funciones distintas de la docencia. " +
      "La descripción se guarda en la designación y luego Disposiciones la recupera automáticamente.",
    captionFuncion:
      "La disposición ya aporta **«…el cumplimiento de funciones»**. " +
      "Completá la continuación, por ejemplo: **«de coordinación administrativa del Departamento»**.",
    ayudaTexto: "Campo obligatorio para una designación no docente.",
    observaciones: "Observaciones",
    placeholderObs: "Dato opcional de la nueva designación.",
  },
  registro: {
    titulo: "Designación en el período actual",
    tipo: "Tipo de designación",
    ayudaFuncion:
      "Marcá esta opción cuando la designación se utiliza para cumplir funciones distintas de la docencia. " +
      "La descripción se guarda en esta designación, se muestra en el Resumen docente y la toma automáticamente Disposiciones.",
    captionFuncion:
      "La disposición ya aporta el inicio **«…el cumplimiento de funciones»**. " +
      "Escribí únicamente la continuación que complete esa frase, incluyendo la preposición o enlace necesario. " +
      "Ejemplo: **«de coordinación administrativa del Departamento»**.",
    ayudaTexto: "Campo obligatorio. El Artículo 1 quedará como: ‘...el cumplimiento de funciones [este texto]’.",
    observaciones: "Observaciones de la designación",
    placeholderObs: undefined,
  },
} as const;

function FormularioDesignacion({
  variante,
  catalogos,
  form,
  set,
  disabled,
}: {
  variante: keyof typeof VARIANTES;
  catalogos: CatalogosDesignacion;
  form: DesignacionDocenteForm;
  set: (patch: Partial<DesignacionDocenteForm>) => void;
  disabled: boolean;
}) {
  const t = VARIANTES[variante];
  const horas = horasSegunDedicacion(catalogos.horas_por_dedicacion, form.dedicacion);
  const texto = form.texto_funcion_no_docente.trim();
  return (
    <div className="space-y-4">
      <h4 className={`font-semibold text-brand-950 ${variante === "reincorporar" ? "text-lg" : "text-base"}`}>{t.titulo}</h4>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-4">
          <Field label="Cargo">
            <Select value={form.cargo} options={catalogos.cargos} onChange={(v) => set({ cargo: v })} disabled={disabled} />
          </Field>
          <Field label="Dedicación">
            <Select value={form.dedicacion} options={catalogos.dedicaciones} onChange={(v) => set({ dedicacion: v })} disabled={disabled} />
          </Field>
          <Caption>
            Horas automáticas según dedicación: <b>{horas} hs</b>
          </Caption>
          <Field label={t.tipo}>
            <Select value={form.tipo_designacion} options={catalogos.tipos} onChange={(v) => set({ tipo_designacion: v })} disabled={disabled} />
          </Field>
        </div>
        <div className="space-y-4">
          <Field label="Ad Honorem">
            <Select value={form.ad_honorem} options={catalogos.ad_honorem} onChange={(v) => set({ ad_honorem: v })} disabled={disabled} />
          </Field>
          <Field label="Fecha desde">
            <TextInput type="date" value={form.fecha_desde} onChange={(v) => set({ fecha_desde: v })} disabled={disabled} />
          </Field>
          <Field label="Fecha hasta">
            <TextInput type="date" value={form.fecha_hasta} onChange={(v) => set({ fecha_hasta: v })} disabled={disabled} />
          </Field>
          <Field label="Estado">
            <Select value={form.estado} options={catalogos.estados} onChange={(v) => set({ estado: v })} disabled={disabled} />
          </Field>
        </div>
      </div>
      <div title={t.ayudaFuncion}>
        <Check
          checked={form.funcion_no_docente}
          onChange={(v) => set({ funcion_no_docente: v })}
          disabled={disabled}
          label="Esta designación corresponde a funciones no docentes"
        />
      </div>
      {form.funcion_no_docente && (
        <div className="space-y-2">
          <Caption>
            <Negrita texto={t.captionFuncion} />
          </Caption>
          <Field label="Funciones que cumplirá" hint={t.ayudaTexto}>
            <Textarea
              value={form.texto_funcion_no_docente}
              onChange={(v) => set({ texto_funcion_no_docente: v })}
              disabled={disabled}
              placeholder="Ej.: de coordinación administrativa del Departamento"
            />
          </Field>
          {texto && <Caption>{`Vista previa: «…el cumplimiento de funciones ${texto.replace(/\.+$/, "")}.»`}</Caption>}
        </div>
      )}
      <Field label={t.observaciones}>
        <Textarea
          value={form.observaciones}
          onChange={(v) => set({ observaciones: v })}
          disabled={disabled}
          placeholder={t.placeholderObs}
        />
      </Field>
    </div>
  );
}

function BotonEscritura({
  children,
  puede,
  busy,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  puede: boolean;
  busy: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  // button_con_permisos (l. 2792): sin permiso de escritura el botón queda deshabilitado con la ayuda certificada.
  return (
    <div title={puede ? undefined : AYUDA_SOLO_LECTURA} className="inline-block">
      <PrimaryButton busy={busy} disabled={disabled || !puede} onClick={onClick}>
        {children}
      </PrimaryButton>
    </div>
  );
}

function useGuardar(onDone: OnDone, onError: OnError) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acto, setActo] = useState<ActoConfig>(ACTO_PENDIENTE);
  const [versionActos, setVersionActos] = useState(0);
  async function guardar(body: RegistroDesignacion) {
    setBusy(true);
    setError(null);
    try {
      const r = await docentesApi.registrarDesignacion(body, acto);
      const avisos = r.avisos ?? [];
      setActo(ACTO_PENDIENTE);
      setVersionActos((v) => v + 1);
      await onDone({ tone: r.tono, text: [r.mensaje, ...avisos].join(" ") });
    } catch (e) {
      setError(onError(e).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, guardar, acto, setActo, versionActos };
}

function ActoDeLaDesignacion({
  g,
  nombre,
  periodo,
  form,
  horas,
}: {
  g: ReturnType<typeof useGuardar>;
  nombre: string;
  periodo: string;
  form: DesignacionDocenteForm;
  horas: number | string;
}) {
  const funcion = form.funcion_no_docente ? "No docente" : "Docencia";
  return (
    <ActoContextual
      titulo={TITULO_ACTO}
      version={g.versionActos}
      value={g.acto}
      onChange={g.setActo}
      categoria={(ctx) => ctx.categoria_alta}
      tituloSugerido={nombre ? `Designación — ${nombre}` : ""}
      detalleSugerido={`${periodo} - ${nombre} - ${form.cargo} - ${form.dedicacion} - ${horas} hs - ${form.tipo_designacion} - Función: ${funcion}`}
    />
  );
}

// ---------------------------------------------------------------------------------------------- camino 1
const REINCORPORABLES_COLUMNS: Column<Reincorporable>[] = [
  { key: "nombre_completo", label: "Docente" },
  { key: "cuil", label: "CUIL" },
  { key: "legajo", label: "Legajo" },
  { key: "titulo", label: "Título" },
  { key: "estado", label: "Estado" },
];

function Metrica({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-semibold text-brand-950">{value}</p>
    </div>
  );
}

export function Reincorporar({ version, onDone, onError }: { version: unknown; onDone: OnDone; onError: OnError }) {
  const { ctx, error: ctxError } = useContexto(version, onError);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [form, setForm] = useState<DesignacionDocenteForm | null>(null);
  const [duplicada, setDuplicada] = useState(false);
  const g = useGuardar(onDone, onError);
  const { busy, error, guardar } = g;

  const filas = useMemo(
    () => filtrarPorTexto(ctx?.reincorporables ?? [], q, ["nombre_completo", "cuil", "legajo", "titulo"]),
    [ctx, q]
  );
  const elegido = filas.find((f) => f.cuil === sel) ?? filas[0] ?? null;
  const abierto = ctx?.abierto ?? null;
  const inicial = useMemo(() => (ctx && ctx.abierto ? formInicial(ctx.catalogos, ctx.abierto) : null), [ctx]);
  const valores = form ?? inicial;

  // existe_designacion_duplicada en cada rerun (l. 60085-60097): aviso antes de guardar.
  useEffect(() => {
    let cancelled = false;
    if (!elegido || !valores) return;
    const t = setTimeout(() => {
      docentesApi
        .designacionDuplicado({ ...valores, cuil: elegido.cuil })
        .then((r) => !cancelled && setDuplicada(r.duplicada))
        .catch(() => !cancelled && setDuplicada(false));
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [elegido, valores]);

  const info = (
    <FeedbackBox
      feedback={{
        tone: "info",
        text:
          "Esta opción recupera un docente propio que ya existe en la base maestra, pero todavía no tiene ninguna " +
          "designación en el período abierto. Al guardar, se registra directamente su designación y pasa a integrar " +
          "el plantel del período.",
      }}
    />
  );
  if (ctxError) return <div className="space-y-4">{info}<p className="text-sm text-red-600">{ctxError}</p></div>;
  if (!ctx) return info;
  if (!abierto) {
    return (
      <div className="space-y-4">
        {info}
        <FeedbackBox
          feedback={{ tone: "warning", text: "No hay un período abierto. Abrí o creá el período actual antes de reincorporar docentes." }}
        />
      </div>
    );
  }
  if (ctx.reincorporables.length === 0) {
    return (
      <div className="space-y-4">
        {info}
        <FeedbackBox
          feedback={{
            tone: "success",
            text:
              "No hay docentes propios pendientes de reincorporación: todos los docentes disponibles de la base " +
              "maestra ya tienen alguna designación en el período abierto.",
          }}
        />
      </div>
    );
  }
  const set = (patch: Partial<DesignacionDocenteForm>) => setForm({ ...(valores as DesignacionDocenteForm), ...patch });
  return (
    <div className="space-y-4">
      {info}
      <Field label="Buscar en la base maestra">
        <TextInput value={q} onChange={setQ} placeholder="Nombre, apellido, CUIL, legajo o título" />
      </Field>
      {filas.length === 0 || !elegido || !valores ? (
        <FeedbackBox
          feedback={{
            tone: "warning",
            text: "No hay docentes de la base maestra que coincidan con la búsqueda y estén fuera del período actual.",
          }}
        />
      ) : (
        <>
          <p className="text-sm font-medium text-slate-700">Docentes encontrados</p>
          <DataTable
            rows={filas}
            columns={REINCORPORABLES_COLUMNS}
            rowKey={(r) => r.cuil}
            selected={elegido.cuil}
            onSelect={setSel}
            maxHeight="max-h-72"
          />
          <div className="grid grid-cols-3 gap-4">
            <Metrica label="Docente" value={elegido.nombre_completo || "-"} />
            <Metrica label="CUIL" value={elegido.cuil || "-"} />
            <Metrica label="Período" value={abierto.nombre || "-"} />
          </div>
          <Caption>
            {`Legajo: ${elegido.legajo || "-"} · Título: ${elegido.titulo || "-"} · Estado en base maestra: ${elegido.estado || "-"}`}
          </Caption>
          <FormularioDesignacion variante="reincorporar" catalogos={ctx.catalogos} form={valores} set={set} disabled={busy} />
          <ActoDeLaDesignacion
            g={g}
            nombre={elegido.nombre_completo ?? ""}
            periodo={abierto.nombre}
            form={valores}
            horas={horasSegunDedicacion(ctx.catalogos.horas_por_dedicacion, valores.dedicacion)}
          />
          {duplicada && (
            <FeedbackBox
              feedback={{
                tone: "warning",
                text:
                  "Mientras completabas el formulario se registró una designación exactamente igual. Revisá el plantel " +
                  "antes de continuar.",
              }}
            />
          )}
          <BotonEscritura
            puede={ctx.puede_escribir}
            busy={busy}
            onClick={() =>
              guardar({
                ...valores,
                abierto_huella: ctx.abierto_huella,
                camino: "reincorporar",
                cuil: elegido.cuil,
                huella: elegido.huella,
              })
            }
          >
            💾 Registrar designación y reincorporar al período
          </BotonEscritura>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- caminos 2 y 3
export function DesignacionDesdeRegistro({
  version,
  camino,
  elegido,
  cuilAlta,
  nombre,
  onDone,
  onError,
}: {
  version: unknown;
  camino: "cuil_existente" | "cuil_local";
  elegido?: OtroDepartamento | null;
  cuilAlta: string;
  nombre?: string;
  onDone: OnDone;
  onError: OnError;
}) {
  const { ctx, error: ctxError } = useContexto(version, onError);
  const [form, setForm] = useState<DesignacionDocenteForm | null>(null);
  const g = useGuardar(onDone, onError);
  const { busy, error, guardar } = g;
  if (ctxError) return <p className="text-sm text-red-600">{ctxError}</p>;
  if (!ctx) return null;
  const abierto = ctx.abierto;
  const valores = form ?? (abierto ? formInicial(ctx.catalogos, abierto) : null);
  const set = (patch: Partial<DesignacionDocenteForm>) => setForm({ ...(valores as DesignacionDocenteForm), ...patch });
  const etiqueta =
    camino === "cuil_existente" ? "💾 Registrar como propio y guardar designación" : "💾 Registrar una nueva designación para este docente";
  return (
    <div className="space-y-4">
      {!abierto || !valores ? (
        <FeedbackBox feedback={{ tone: "warning", text: "No hay un período abierto para registrar la designación." }} />
      ) : (
        <>
          <FormularioDesignacion variante="registro" catalogos={ctx.catalogos} form={valores} set={set} disabled={busy} />
          <ActoDeLaDesignacion
            g={g}
            nombre={(camino === "cuil_existente" ? elegido?.nombre_completo : nombre) ?? ""}
            periodo={abierto.nombre}
            form={valores}
            horas={horasSegunDedicacion(ctx.catalogos.horas_por_dedicacion, valores.dedicacion)}
          />
        </>
      )}
      <BotonEscritura
        puede={ctx.puede_escribir}
        busy={busy}
        disabled={!valores || (camino === "cuil_existente" && !elegido)}
        onClick={() => {
          if (!valores) return;
          const base = { ...valores, abierto_huella: ctx.abierto_huella };
          if (camino === "cuil_existente" && elegido) {
            void guardar({ ...base, camino, cuil: elegido.cuil, departamento_origen: elegido.departamento_origen, cuil_alta: cuilAlta });
          } else if (camino === "cuil_local") {
            void guardar({ ...base, camino, cuil_alta: cuilAlta });
          }
        }}
      >
        {etiqueta}
      </BotonEscritura>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
