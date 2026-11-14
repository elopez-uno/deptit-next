"use client";

// Módulo Administración SaaS (B13-FIX02 render_admin_saas l. 3339-3693): las 5 pestañas certificadas con los textos que
// envía el backend. Solo superadmin; FastAPI re-autoriza cada request y es la autoridad de toda validación (cupo, último
// superadmin, departamento ∈ institución, eliminación solo de instituciones/departamentos VACÍOS: D-AP1/D-AP2/D-AP4).
// Sin rutas ni archivos (D-AP3), sin columnas técnicas (D-AP6). Las escrituras esperan la respuesta (sin UI optimista) y
// después se relee todo.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Spinner } from "@/components/brand";
import { Check, Details, FeedbackBox, Field, PrimaryButton, Select, TextInput, Textarea, type Feedback } from "@/components/module-ui";
import { ApiError } from "@/lib/auth";
import { type Celda, type Tabla, guardarArchivo } from "@/lib/analisis";
import { type Departamento, type Institucion, type Overview, type Planes, type Usuario, type WriteResult, saasApi } from "@/lib/saas";

type Ctx = {
  data: Overview;
  run: (fn: () => Promise<WriteResult>) => Promise<boolean>;
  excel: (tabla: string, id: number | null) => Promise<void>;
  onError: (e: unknown) => ApiError;
};

function Md({ text }: { text: string }) {
  const partes = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{partes.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}</>;
}

function texto(v: Celda) {
  return v === null || v === undefined ? "" : String(v);
}

function Grilla({ tabla, label }: { tabla: Tabla; label: string }) {
  return (
    <div className="max-h-[28rem] overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table aria-label={label} className="min-w-full text-left text-sm">
        <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
          <tr>{tabla.columnas.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tabla.filas.map((f, i) => (
            <tr key={i}>{f.map((v, j) => <td key={j} className="whitespace-nowrap px-3 py-1.5 text-slate-700">{texto(v)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BotonExcel({ ctx, tabla, id }: { ctx: Ctx; tabla: string; id?: number | null }) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <button
      type="button"
      disabled={ocupado}
      onClick={async () => {
        setOcupado(true);
        try {
          await ctx.excel(tabla, id ?? null);
        } finally {
          setOcupado(false);
        }
      }}
      className="flex w-fit items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
    >
      {ocupado && <Spinner />}
      {ctx.data.ui.excel}
    </button>
  );
}

function TablaExcel({ ctx, tabla, clave, label, id }: { ctx: Ctx; tabla: Tabla; clave: string; label: string; id?: number | null }) {
  return (
    <div className="space-y-2">
      <Grilla tabla={tabla} label={label} />
      {tabla.filas.length > 0 && <BotonExcel ctx={ctx} tabla={clave} id={id} />}
    </div>
  );
}

function Ficha({ ctx, titulo, tabla, clave, id }: { ctx: Ctx; titulo: string; tabla: Tabla; clave: string; id: number }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-slate-800">{titulo}</p>
      <TablaExcel ctx={ctx} tabla={tabla} clave={clave} label={titulo} id={id} />
    </div>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="text-lg font-semibold text-slate-900">{children}</h3>;
}

function Grid({ children, cols = 3 }: { children: React.ReactNode; cols?: 2 | 3 }) {
  return <div className={`grid gap-4 ${cols === 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>{children}</div>;
}

function Numero({ value, onChange, min, max }: { value: number; onChange: (v: number) => void; min: number; max: number }) {
  return (
    <input
      type="number"
      min={min}
      max={max}
      step={1}
      value={value}
      onChange={(e) => onChange(Number.parseInt(e.target.value || "0", 10))}
      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
    />
  );
}

function Fecha({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <input type="date" value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />;
}

function Info({ text, tone = "info" }: { text: string; tone?: "info" | "warning" | "error" }) {
  return <FeedbackBox feedback={{ tone, text }} />;
}

function etiquetaInst(i: Institucion) {
  return `${i.nombre} — ${i.estado ?? "Activa"}`;
}

function detalleDatos(d: { usuarios: number; departamentos: number; registros: number; tablas: number }) {
  const partes = [];
  if (d.usuarios) partes.push(`${d.usuarios} usuario(s)`);
  if (d.departamentos) partes.push(`${d.departamentos} departamento(s)`);
  if (d.registros) partes.push(`${d.registros} registro(s) en ${d.tablas} tabla(s)`);
  return partes.join(", ");
}

// ------------------------------------------------------------------------------------------ 1. Instituciones
function Instituciones({ ctx }: { ctx: Ctx }) {
  const { data } = ctx;
  const ui = data.ui.instituciones;
  const cat = data.catalogos;
  const [n, setN] = useState({ nombre: "", cupo: cat.cupo.default, plan: "Institucional", venc: "", pago: cat.pagos[0], susc: cat.suscripciones[0], acceso: cat.accesos[0], obs: "" });
  const [cupoSel, setCupoSel] = useState(data.instituciones[0]?.id ?? 0);
  const [cupo, setCupo] = useState(cat.cupo.default);
  const [delSel, setDelSel] = useState(data.instituciones[0]?.id ?? 0);
  const [confirmado, setConfirmado] = useState(false);
  const [palabra, setPalabra] = useState("");
  const del = data.instituciones.find((i) => i.id === delSel);

  return (
    <div className="space-y-4">
      <H3>{ui.subtitulo}</H3>
      <TablaExcel ctx={ctx} tabla={data.tablas.instituciones} clave="instituciones" label={ui.subtitulo} />
      <Details summary={ui.crear.titulo}>
        <Grid>
          <div className="space-y-3">
            <Field label={ui.crear.nombre}><TextInput value={n.nombre} onChange={(v) => setN({ ...n, nombre: v })} /></Field>
            <Field label={ui.crear.cupo}><Numero value={n.cupo} min={cat.cupo.min} max={cat.cupo.max} onChange={(v) => setN({ ...n, cupo: v })} /></Field>
          </div>
          <div className="space-y-3">
            <Field label={ui.crear.plan}><Select value={n.plan} options={cat.planes} onChange={(v) => setN({ ...n, plan: v })} /></Field>
            <Field label={ui.crear.vencimiento}><Fecha value={n.venc} onChange={(v) => setN({ ...n, venc: v })} /></Field>
          </div>
          <div className="space-y-3">
            <Field label={ui.crear.pago}><Select value={n.pago} options={cat.pagos} onChange={(v) => setN({ ...n, pago: v })} /></Field>
            <Field label={ui.crear.suscripcion}><Select value={n.susc} options={cat.suscripciones} onChange={(v) => setN({ ...n, susc: v })} /></Field>
            <Field label={ui.crear.acceso}><Select value={n.acceso} options={cat.accesos} onChange={(v) => setN({ ...n, acceso: v })} /></Field>
          </div>
        </Grid>
        <Field label={ui.crear.observaciones}><Textarea value={n.obs} onChange={(v) => setN({ ...n, obs: v })} /></Field>
        <AccionBoton ctx={ctx} label={ui.crear.boton} fn={() => saasApi.crearInstitucion({ nombre: n.nombre, max_usuarios: n.cupo, plan: n.plan, fecha_vencimiento: n.venc || null, estado_pago: n.pago, suscripcion: n.susc, estado: n.acceso, observaciones: n.obs })} />
      </Details>
      <Details summary={ui.cupo.titulo}>
        {data.instituciones.length > 0 && (
          <>
            <Field label={ui.cupo.institucion}>
              <Select value={String(cupoSel)} options={data.instituciones.map((i) => String(i.id))} onChange={(v) => setCupoSel(Number(v))} label={(id) => { const i = data.instituciones.find((x) => String(x.id) === id); return i ? `${i.nombre} (actual: ${i.max_usuarios})` : id; }} />
            </Field>
            <Field label={ui.cupo.nuevo}><Numero value={cupo} min={cat.cupo.min} max={cat.cupo.max} onChange={setCupo} /></Field>
            <AccionBoton ctx={ctx} label={ui.cupo.boton} fn={() => saasApi.cupo(cupoSel, cupo)} />
          </>
        )}
      </Details>
      <Details summary={ui.eliminar.titulo}>
        {data.instituciones.length === 0 ? (
          <Info text={ui.eliminar.vacio} />
        ) : (
          <>
            <Info tone="warning" text={ui.eliminar.aviso} />
            <Field label={ui.eliminar.selector}>
              <Select value={String(delSel)} options={data.instituciones.map((i) => String(i.id))} onChange={(v) => { setDelSel(Number(v)); setConfirmado(false); setPalabra(""); }} label={(id) => { const i = data.instituciones.find((x) => String(x.id) === id); return i ? etiquetaInst(i) : id; }} />
            </Field>
            {del && <Ficha ctx={ctx} titulo={ui.eliminar.datos} tabla={del.ficha} clave="institucion" id={del.id} />}
            {del && !del.eliminable ? (
              <Info tone="error" text={`La institución contiene datos y no puede eliminarse (${detalleDatos(del.dependencias)}). Para darla de baja cambiá su acceso a "Bloqueada" o "Suspendida" en Suscripción / Comercial.`} />
            ) : (
              <>
                <Check checked={confirmado} onChange={setConfirmado} label={ui.eliminar.confirmar} />
                <Field label={ui.eliminar.texto}><TextInput value={palabra} onChange={setPalabra} /></Field>
              </>
            )}
            <AccionBoton ctx={ctx} label={ui.eliminar.boton} tone="danger" disabled={!del?.eliminable || !confirmado || palabra.trim().toUpperCase() !== "ELIMINAR"} fn={() => saasApi.eliminarInstitucion(delSel, confirmado, palabra)} />
          </>
        )}
      </Details>
    </div>
  );
}

function AccionBoton({ ctx, label, fn, tone = "primary", disabled }: { ctx: Ctx; label: string; fn: () => Promise<WriteResult>; tone?: "primary" | "danger" | "secondary"; disabled?: boolean }) {
  const [busy, setBusy] = useState(false);
  return (
    <PrimaryButton
      tone={tone}
      busy={busy}
      disabled={disabled}
      onClick={async () => {
        setBusy(true);
        try {
          await ctx.run(fn);
        } finally {
          setBusy(false);
        }
      }}
    >
      {label}
    </PrimaryButton>
  );
}

// ------------------------------------------------------------------------------------------ 2. Departamentos
function Departamentos({ ctx }: { ctx: Ctx }) {
  const { data } = ctx;
  const ui = data.ui.departamentos;
  const activas = data.instituciones.filter((i) => i.estado === "Activa");
  const [inst, setInst] = useState(activas[0]?.id ?? 0);
  const deps = data.departamentos.filter((d) => d.institucion_id === inst);
  const [planes, setPlanes] = useState<Planes | null>(null);
  const [nuevo, setNuevo] = useState({ nombre: "", obs: "" });
  const [editSel, setEditSel] = useState(0);
  const [delSel, setDelSel] = useState(0);
  const [confirmado, setConfirmado] = useState(false);
  const edit = deps.find((d) => d.id === editSel) ?? deps[0];
  const del = deps.find((d) => d.id === delSel) ?? deps[0];
  const { onError } = ctx;

  useEffect(() => {
    if (!inst) return;
    let cancel = false;
    saasApi
      .planes(inst)
      .then((p) => !cancel && setPlanes(p))
      .catch((e) => !cancel && onError(e));
    return () => {
      cancel = true;
    };
  }, [inst, onError]);

  return (
    <div className="space-y-4">
      <H3>{ui.subtitulo}</H3>
      <TablaExcel ctx={ctx} tabla={data.tablas.departamentos} clave="departamentos" label={ui.subtitulo} />
      {activas.length > 0 && (
        <>
          <Field label={ui.institucion}>
            <Select value={String(inst)} options={activas.map((i) => String(i.id))} onChange={(v) => { setInst(Number(v)); setEditSel(0); setDelSel(0); setConfirmado(false); }} label={(id) => activas.find((i) => String(i.id) === id)?.nombre ?? id} />
          </Field>
          <H3>{ui.planes.titulo}</H3>
          {planes && (
            <div className="space-y-3">
              {planes.aviso && <Info tone="warning" text={planes.aviso} />}
              <div className="grid grid-cols-3 gap-3">
                {planes.metricas.map((m) => (
                  <div key={m.label} className="rounded-xl bg-white px-4 py-3" data-testid="metrica">
                    <p className="text-xs text-slate-500">{m.label}</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-900">{m.valor}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          <Details summary={ui.crear.titulo}>
            <Field label={ui.crear.nombre}><TextInput value={nuevo.nombre} onChange={(v) => setNuevo({ ...nuevo, nombre: v })} /></Field>
            <Field label={ui.crear.observaciones}><Textarea value={nuevo.obs} onChange={(v) => setNuevo({ ...nuevo, obs: v })} /></Field>
            <AccionBoton ctx={ctx} label={ui.crear.boton} fn={() => saasApi.crearDepartamento(inst, nuevo.nombre, nuevo.obs)} />
          </Details>
          <Details summary={ui.editar.titulo}>
            {!edit ? <Info text={ui.editar.vacio} /> : <EditarDepartamento key={edit.id} ctx={ctx} deps={deps} dep={edit} onSelect={setEditSel} />}
          </Details>
          <Details summary={ui.eliminar.titulo}>
            {!del ? (
              <Info text={ui.eliminar.vacio} />
            ) : (
              <>
                <Field label={ui.eliminar.selector}>
                  <Select value={String(del.id)} options={deps.map((d) => String(d.id))} onChange={(v) => { setDelSel(Number(v)); setConfirmado(false); }} label={(id) => { const d = deps.find((x) => String(x.id) === id); return d ? `${d.nombre} — ${d.estado}` : id; }} />
                </Field>
                <Info tone="warning" text={ui.eliminar.aviso} />
                <p className="text-xs text-slate-500">{ui.eliminar.usuarios.replace("{n}", String(del.usuarios))}</p>
                <Check checked={confirmado} onChange={setConfirmado} label={ui.eliminar.confirmar} />
                {del.usuarios > 0 ? (
                  <Info tone="error" text={ui.eliminar.con_usuarios} />
                ) : (
                  !del.eliminable && <Info tone="error" text={`El departamento contiene datos y no puede eliminarse (${detalleDatos(del.dependencias)}). Para darlo de baja cambiá su estado a "Inactivo" en Editar departamento.`} />
                )}
                <AccionBoton ctx={ctx} label={ui.eliminar.boton} tone="danger" disabled={!del.eliminable || !confirmado} fn={() => saasApi.eliminarDepartamento(del.id, confirmado)} />
              </>
            )}
          </Details>
        </>
      )}
    </div>
  );
}

function EditarDepartamento({ ctx, deps, dep, onSelect }: { ctx: Ctx; deps: Departamento[]; dep: Departamento; onSelect: (id: number) => void }) {
  const ui = ctx.data.ui.departamentos.editar;
  const [f, setF] = useState({ nombre: dep.nombre ?? "", estado: dep.estado === "Inactivo" ? "Inactivo" : "Activo", obs: dep.observaciones ?? "" });
  return (
    <>
      <Field label={ui.selector}>
        <Select value={String(dep.id)} options={deps.map((d) => String(d.id))} onChange={(v) => onSelect(Number(v))} label={(id) => { const d = deps.find((x) => String(x.id) === id); return d ? `${d.nombre} — ${d.estado}` : id; }} />
      </Field>
      <Ficha ctx={ctx} titulo={ui.datos} tabla={dep.ficha} clave="departamento" id={dep.id} />
      <Field label={ui.nombre}><TextInput value={f.nombre} onChange={(v) => setF({ ...f, nombre: v })} /></Field>
      <Field label={ui.estado}><Select value={f.estado} options={ctx.data.catalogos.estados_departamento} onChange={(v) => setF({ ...f, estado: v })} /></Field>
      <Field label={ui.observaciones}><Textarea value={f.obs} onChange={(v) => setF({ ...f, obs: v })} /></Field>
      <AccionBoton ctx={ctx} label={ui.boton} fn={() => saasApi.editarDepartamento(dep.id, f.nombre, f.estado, f.obs)} />
    </>
  );
}

// ------------------------------------------------------------------------------------------ 3. Usuarios
function opcionesDep(data: Overview, inst: number | null, actual?: number | null) {
  return data.departamentos.filter((d) => d.institucion_id === inst && (d.estado === "Activo" || d.id === actual));
}

function Usuarios({ ctx }: { ctx: Ctx }) {
  const { data } = ctx;
  const ui = data.ui.usuarios;
  const cat = data.catalogos;
  const activas = data.instituciones.filter((i) => i.estado === "Activa");
  const [c, setC] = useState({ inst: activas[0]?.id ?? 0, dep: 0, nombre: "", email: "", rol: "usuario_departamento", pwd: "", pwd2: "", estado: "Activo", obs: "" });
  const inst = activas.find((i) => i.id === c.inst);
  const deps = opcionesDep(data, c.inst);
  const [estSel, setEstSel] = useState(data.usuarios[0]?.id ?? 0);
  const [estado, setEstado] = useState("Activo");
  const [editSel, setEditSel] = useState(data.usuarios[0]?.id ?? 0);
  const [delSel, setDelSel] = useState(data.usuarios[0]?.id ?? 0);
  const [confirmado, setConfirmado] = useState(false);
  const edit = data.usuarios.find((u) => u.id === editSel);
  const ids = data.usuarios.map((u) => String(u.id));
  const etiqueta = (id: string) => data.usuarios.find((u) => String(u.id) === id)?.etiqueta ?? id;

  return (
    <div className="space-y-4">
      <H3>{ui.subtitulo}</H3>
      <TablaExcel ctx={ctx} tabla={data.tablas.usuarios} clave="usuarios" label={ui.subtitulo} />
      <Details summary={ui.crear.titulo}>
        {activas.length === 0 ? (
          <Info tone="warning" text={ui.crear.sin_instituciones} />
        ) : (
          <>
            <Field label={ui.crear.institucion}>
              <Select value={String(c.inst)} options={activas.map((i) => String(i.id))} onChange={(v) => setC({ ...c, inst: Number(v), dep: 0 })} label={(id) => activas.find((i) => String(i.id) === id)?.nombre ?? id} />
            </Field>
            <Grid cols={2}>
              <div className="space-y-3">
                <Field label={ui.crear.nombre}><TextInput value={c.nombre} onChange={(v) => setC({ ...c, nombre: v })} /></Field>
                <Field label={ui.crear.mail}><TextInput value={c.email} onChange={(v) => setC({ ...c, email: v })} /></Field>
                <Field label={ui.crear.rol}><Select value={c.rol} options={cat.roles} onChange={(v) => setC({ ...c, rol: v })} /></Field>
              </div>
              <div className="space-y-3">
                <Field label={ui.crear.departamento}>
                  <Select value={String(c.dep)} options={["0", ...deps.map((d) => String(d.id))]} onChange={(v) => setC({ ...c, dep: Number(v) })} label={(id) => (id === "0" ? cat.sin_departamento : deps.find((d) => String(d.id) === id)?.nombre ?? id)} />
                </Field>
                <Field label={ui.crear.password}><TextInput type="password" value={c.pwd} onChange={(v) => setC({ ...c, pwd: v })} /></Field>
                <Field label={ui.crear.confirmar}><TextInput type="password" value={c.pwd2} onChange={(v) => setC({ ...c, pwd2: v })} /></Field>
                <Field label={ui.crear.estado}><Select value={c.estado} options={cat.estados_usuario} onChange={(v) => setC({ ...c, estado: v })} /></Field>
              </div>
            </Grid>
            <Field label={ui.crear.observaciones}><Textarea value={c.obs} onChange={(v) => setC({ ...c, obs: v })} /></Field>
            {inst && <p className="text-xs text-slate-500">{ui.crear.cupo.replace("{activos}", String(inst.activos)).replace("{max}", String(inst.max_usuarios))}</p>}
            <AccionBoton ctx={ctx} label={ui.crear.boton} fn={() => saasApi.crearUsuario({ institucion_id: c.inst, departamento_id: c.dep || null, nombre: c.nombre, email: c.email, rol: c.rol, password: c.pwd, password_confirmacion: c.pwd2, estado: c.estado, observaciones: c.obs })} />
          </>
        )}
      </Details>
      <Details summary={ui.estado.titulo}>
        {data.usuarios.length > 0 && (
          <>
            <Field label={ui.estado.usuario}><Select value={String(estSel)} options={ids} onChange={(v) => setEstSel(Number(v))} label={etiqueta} /></Field>
            <Field label={ui.estado.nuevo}><Select value={estado} options={cat.estados_usuario} onChange={setEstado} /></Field>
            <AccionBoton ctx={ctx} label={ui.estado.boton} fn={() => saasApi.estadoUsuario(estSel, estado)} />
          </>
        )}
      </Details>
      <Details summary={ui.editar.titulo}>
        {edit && (
          <>
            <Field label={ui.editar.selector}><Select value={String(edit.id)} options={ids} onChange={(v) => setEditSel(Number(v))} label={etiqueta} /></Field>
            <EditarUsuario key={edit.id} ctx={ctx} usuario={edit} />
          </>
        )}
      </Details>
      <Details summary={ui.eliminar.titulo}>
        {data.usuarios.length > 0 && (
          <>
            <Field label={ui.eliminar.selector}><Select value={String(delSel)} options={ids} onChange={(v) => { setDelSel(Number(v)); setConfirmado(false); }} label={etiqueta} /></Field>
            <Check checked={confirmado} onChange={setConfirmado} label={ui.eliminar.confirmar} />
            <AccionBoton ctx={ctx} label={ui.eliminar.boton} tone="danger" disabled={!confirmado} fn={() => saasApi.eliminarUsuario(delSel, confirmado)} />
          </>
        )}
      </Details>
    </div>
  );
}

function EditarUsuario({ ctx, usuario }: { ctx: Ctx; usuario: Usuario }) {
  const { data } = ctx;
  const ui = data.ui.usuarios.editar;
  const cat = data.catalogos;
  // Institución: activas + la actual del usuario (aunque no esté Activa); sin institución -> la primera activa.
  const insts = data.instituciones.filter((i) => i.estado === "Activa" || i.id === usuario.institucion_id);
  const [f, setF] = useState({
    nombre: usuario.nombre ?? "",
    email: usuario.email,
    rol: usuario.rol,
    estado: usuario.estado === "Inactivo" ? "Inactivo" : "Activo",
    inst: usuario.institucion_id ?? insts[0]?.id ?? 0,
    dep: usuario.departamento_id ?? 0,
    pwd: "",
    obs: usuario.observaciones ?? "",
  });
  const deps = opcionesDep(data, f.inst, usuario.departamento_id);
  return (
    <>
      <Ficha ctx={ctx} titulo={ui.datos} tabla={usuario.ficha} clave="usuario" id={usuario.id} />
      <Grid cols={2}>
        <div className="space-y-3">
          <Field label={ui.nombre}><TextInput value={f.nombre} onChange={(v) => setF({ ...f, nombre: v })} /></Field>
          <Field label={ui.mail}><TextInput value={f.email} onChange={(v) => setF({ ...f, email: v })} /></Field>
          <Field label={ui.rol}><Select value={f.rol} options={cat.roles} onChange={(v) => setF({ ...f, rol: v })} /></Field>
          <Field label={ui.estado}><Select value={f.estado} options={cat.estados_usuario} onChange={(v) => setF({ ...f, estado: v })} /></Field>
        </div>
        <div className="space-y-3">
          {insts.length > 0 && (
            <Field label={ui.institucion}>
              <Select value={String(f.inst)} options={insts.map((i) => String(i.id))} onChange={(v) => setF({ ...f, inst: Number(v), dep: 0 })} label={(id) => insts.find((i) => String(i.id) === id)?.nombre ?? id} />
            </Field>
          )}
          <Field label={ui.departamento}>
            <Select value={String(deps.some((d) => d.id === f.dep) ? f.dep : 0)} options={["0", ...deps.map((d) => String(d.id))]} onChange={(v) => setF({ ...f, dep: Number(v) })} label={(id) => (id === "0" ? cat.sin_departamento : deps.find((d) => String(d.id) === id)?.nombre ?? id)} />
          </Field>
          <Field label={ui.password}><TextInput type="password" value={f.pwd} onChange={(v) => setF({ ...f, pwd: v })} /></Field>
          <Field label={ui.observaciones}><Textarea value={f.obs} onChange={(v) => setF({ ...f, obs: v })} /></Field>
        </div>
      </Grid>
      <AccionBoton
        ctx={ctx}
        label={ui.boton}
        fn={() => saasApi.editarUsuario({ usuario_id: usuario.id, institucion_id: f.inst || null, departamento_id: deps.some((d) => d.id === f.dep) ? f.dep : null, nombre: f.nombre, email: f.email, rol: f.rol, estado: f.estado, observaciones: f.obs, password: f.pwd })}
      />
    </>
  );
}

// ------------------------------------------------------------------------------------------ 4. Suscripción / Comercial
function Comercial({ ctx }: { ctx: Ctx }) {
  const { data } = ctx;
  const ui = data.ui.comercial;
  const [sel, setSel] = useState(data.instituciones[0]?.id ?? 0);
  const inst = data.instituciones.find((i) => i.id === sel);
  return (
    <div className="space-y-4">
      <H3>{ui.subtitulo}</H3>
      {data.tablas.uso.filas.length === 0 ? <Info text={ui.vacio} /> : <TablaExcel ctx={ctx} tabla={data.tablas.uso} clave="uso" label={ui.subtitulo} />}
      <Details summary={ui.editar.titulo}>
        {!inst ? (
          <Info text={ui.editar.vacio} />
        ) : (
          <>
            <Field label={ui.editar.institucion}>
              <Select value={String(inst.id)} options={data.instituciones.map((i) => String(i.id))} onChange={(v) => setSel(Number(v))} label={(id) => { const i = data.instituciones.find((x) => String(x.id) === id); return i ? etiquetaInst(i) : id; }} />
            </Field>
            <EditarComercial key={inst.id} ctx={ctx} inst={inst} />
          </>
        )}
      </Details>
      <Details summary={ui.criterio.titulo}>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          {ui.criterio.texto.map((t) => <li key={t}><Md text={t} /></li>)}
        </ul>
      </Details>
    </div>
  );
}

function EditarComercial({ ctx, inst }: { ctx: Ctx; inst: Institucion }) {
  const ui = ctx.data.ui.comercial.editar;
  const cat = ctx.data.catalogos;
  const valor = (v: string | null, opciones: string[], defecto: string) => (v && opciones.includes(v) ? v : defecto);
  const [f, setF] = useState({
    plan: valor(inst.plan, cat.planes, "Institucional"),
    cupo: inst.max_usuarios || cat.cupo.default,
    venc: (inst.fecha_vencimiento ?? "").slice(0, 10),
    pago: valor(inst.estado_pago, cat.pagos, cat.pagos[0]),
    susc: valor(inst.suscripcion, cat.suscripciones, cat.suscripciones[0]),
    acceso: valor(inst.estado, cat.accesos, cat.accesos[0]),
    obs: inst.observaciones ?? "",
  });
  return (
    <>
      <Ficha ctx={ctx} titulo={ui.datos} tabla={inst.ficha} clave="comercial" id={inst.id} />
      <Grid>
        <div className="space-y-3">
          <Field label={ui.plan}><Select value={f.plan} options={cat.planes} onChange={(v) => setF({ ...f, plan: v })} /></Field>
          <Field label={ui.cupo}><Numero value={f.cupo} min={cat.cupo.min} max={cat.cupo.max} onChange={(v) => setF({ ...f, cupo: v })} /></Field>
        </div>
        <div className="space-y-3">
          <Field label={ui.vencimiento}><Fecha value={f.venc} onChange={(v) => setF({ ...f, venc: v })} /></Field>
          <Field label={ui.pago}><Select value={f.pago} options={cat.pagos} onChange={(v) => setF({ ...f, pago: v })} /></Field>
        </div>
        <div className="space-y-3">
          <Field label={ui.suscripcion}><Select value={f.susc} options={cat.suscripciones} onChange={(v) => setF({ ...f, susc: v })} /></Field>
          <Field label={ui.acceso}><Select value={f.acceso} options={cat.accesos} onChange={(v) => setF({ ...f, acceso: v })} /></Field>
        </div>
      </Grid>
      <Field label={ui.observaciones}><Textarea value={f.obs} onChange={(v) => setF({ ...f, obs: v })} /></Field>
      <div className="flex flex-wrap gap-3">
        <AccionBoton ctx={ctx} label={ui.guardar} fn={() => saasApi.comercial({ institucion_id: inst.id, plan: f.plan, max_usuarios: f.cupo, fecha_vencimiento: f.venc || null, estado_pago: f.pago, suscripcion: f.susc, estado: f.acceso, observaciones: f.obs })} />
        <AccionBoton ctx={ctx} tone="secondary" label={ui.bloquear} fn={() => saasApi.bloquear(inst.id)} />
        <AccionBoton ctx={ctx} tone="secondary" label={ui.desbloquear} fn={() => saasApi.desbloquear(inst.id)} />
      </div>
    </>
  );
}

// ------------------------------------------------------------------------------------------ 5. Credenciales iniciales
function Credenciales({ ctx }: { ctx: Ctx }) {
  const ui = ctx.data.ui.credenciales;
  return (
    <div className="space-y-3">
      <Info text={ui.info} />
      <pre className="rounded-xl bg-slate-900 px-4 py-3 text-sm text-slate-100">{ui.cuentas.join("\n")}</pre>
    </div>
  );
}

const PANELES = [Instituciones, Departamentos, Usuarios, Comercial, Credenciales];

export function SaasModule({ onAuthError }: { onAuthError: (e: ApiError) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [tab, setTab] = useState(0);
  const [version, setVersion] = useState(0);
  const [cargando, setCargando] = useState(true);

  const handle = useCallback(
    (err: unknown): ApiError => {
      const e = err instanceof ApiError ? err : new ApiError(0, "ERROR", "No se pudo completar la operación.");
      if (e.status === 401) onAuthError(e);
      return e;
    },
    [onAuthError]
  );

  const cargar = useCallback(async () => {
    try {
      setData(await saasApi.overview());
      setError(null);
    } catch (e) {
      setError(handle(e));
    }
  }, [handle]);

  useEffect(() => {
    let cancel = false;
    saasApi
      .overview()
      .then((d) => !cancel && setData(d))
      .catch((e) => !cancel && setError(handle(e)))
      .finally(() => !cancel && setCargando(false));
    return () => {
      cancel = true;
    };
  }, [handle]);

  const ctx = useMemo<Ctx | null>(() => {
    if (!data) return null;
    return {
      data,
      onError: handle,
      async run(fn) {
        setFeedback(null);
        try {
          const r = await fn();
          setFeedback({ tone: r.tono, text: r.mensaje });
          await cargar();
          setVersion((v) => v + 1);
          return true;
        } catch (e) {
          setFeedback({ tone: "error", text: handle(e).message });
          return false;
        }
      },
      async excel(tabla, id) {
        setFeedback(null);
        try {
          guardarArchivo(await saasApi.excel(tabla, id));
        } catch (e) {
          setFeedback({ tone: "error", text: handle(e).message });
        }
      },
    };
  }, [data, handle, cargar]);

  if (cargando) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-10 text-sm text-slate-500">
        <Spinner className="h-5 w-5 text-brand-600" />
        Cargando la Administración SaaS…
      </div>
    );
  }
  if (!ctx) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-6 py-8 text-sm text-red-700">
        <p>{error?.message ?? "No se pudo completar la operación."}</p>
      </div>
    );
  }
  const Panel = PANELES[tab] ?? Instituciones;
  return (
    <div>
      <h2 className="mb-4 text-2xl font-semibold tracking-tight text-brand-950">{ctx.data.ui.titulo}</h2>
      <div role="tablist" aria-label="Pestañas de Administración SaaS" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {ctx.data.ui.pestanas.map((t, i) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === i}
            onClick={() => {
              setTab(i);
              setFeedback(null);
            }}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm transition ${tab === i ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"}`}
          >
            {t}
          </button>
        ))}
      </div>
      {feedback && <FeedbackBox feedback={feedback} />}
      {error && <FeedbackBox feedback={{ tone: "error", text: error.message }} />}
      <div role="tabpanel" key={version}>
        <Panel ctx={ctx} />
      </div>
    </div>
  );
}
