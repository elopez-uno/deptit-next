"use client";

// Pestaña "🏫 Sedes institucionales" (entry l. 72226-72300): catálogo de la institución, compartido por todos sus
// departamentos. Agregar, editar/activar/desactivar y eliminar (con confirmación). Sin compuerta de período.
import { useState } from "react";
import { Aviso, Caption, Cargando, Metric, SoloLectura, Tabla, type TabProps, useConsulta } from "@/components/comisiones-shared";
import { useAccion } from "@/components/designaciones-shared";
import { Card, Check, Field, FeedbackBox, PrimaryButton, Select, TextInput, Textarea } from "@/components/module-ui";
import { type Sede, type SedesData, type WriteResult, post } from "@/lib/comisiones";

export function SedesTab({ data, version, onDone, onError }: TabProps) {
  const q = useConsulta<SedesData>("sedes", {}, onError, version);
  const puede = data.permisos.puede_escribir_sedes;
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-brand-950">Sedes institucionales</h3>
        <Caption>
          Este catálogo pertenece a la universidad y se comparte automáticamente entre todos sus departamentos. Las opciones Sin
          especificar y Campus Virtual siempre están disponibles y no se guardan como sedes físicas.
        </Caption>
      </div>
      {q.error && <FeedbackBox feedback={q.error} />}
      {q.loading && !q.data && <Cargando />}
      {q.data && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Metric label="Sedes activas" value={q.data.activas} />
            <Metric label="Opciones disponibles en comisiones" value={q.data.opciones} />
          </div>
          {q.data.sedes.length === 0 ? (
            <Aviso feedback={{ tone: "info", text: "No hay sedes físicas cargadas. En las comisiones se podrá elegir Sin especificar o Campus Virtual." }} />
          ) : (
            <Tabla
              rows={q.data.sedes}
              cols={[
                { key: "nombre", label: "nombre" },
                { key: "direccion", label: "direccion" },
                { key: "localidad", label: "localidad" },
                { key: "estado", label: "estado" },
                { key: "observaciones", label: "observaciones" },
              ]}
              rowKey={(r) => String(r.id)}
              maxHeight="max-h-72"
            />
          )}
          {!puede && <SoloLectura />}
          <Agregar key={`agregar-${version}`} puede={puede} onDone={onDone} onError={onError} />
          {q.data.sedes.length > 0 && (
            <Editar key={`editar-${version}`} sedes={q.data.sedes} estados={data.catalogos.estados_sede} puede={puede} puedeBorrar={data.permisos.puede_borrar_sedes} onDone={onDone} onError={onError} />
          )}
        </>
      )}
    </section>
  );
}

function Agregar({ puede, onDone, onError }: { puede: boolean; onDone: TabProps["onDone"]; onError: TabProps["onError"] }) {
  const [nombre, setNombre] = useState("");
  const [direccion, setDireccion] = useState("");
  const [localidad, setLocalidad] = useState("");
  const [obs, setObs] = useState("");
  const accion = useAccion(onDone, onError);
  return (
    <Card>
      <h4 className="text-base font-semibold text-brand-950">Agregar sede</h4>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Nombre de la sede">
          <TextInput value={nombre} onChange={setNombre} placeholder="Ej.: Sede Centro" disabled={!puede} />
        </Field>
        <Field label="Calle y número">
          <TextInput value={direccion} onChange={setDireccion} placeholder="Ej.: Belgrano 369" disabled={!puede} />
        </Field>
        <Field label="Localidad">
          <TextInput value={localidad} onChange={setLocalidad} placeholder="Ej.: Merlo" disabled={!puede} />
        </Field>
      </div>
      <Field label="Observaciones de la sede">
        <Textarea value={obs} onChange={setObs} rows={3} disabled={!puede} />
      </Field>
      {accion.feedback && <Aviso feedback={accion.feedback} />}
      {puede && (
        <PrimaryButton
          busy={accion.busy}
          onClick={() => accion.run(() => post<WriteResult>("sedes/agregar", { nombre, direccion, localidad, observaciones: obs }))}
        >
          ➕ Agregar sede institucional
        </PrimaryButton>
      )}
    </Card>
  );
}

const etiquetaSede = (s: Sede) => `${s.nombre} — ${s.direccion ?? ""}, ${s.localidad ?? ""} [${s.estado ?? "Activa"}]`;

function Editar({
  sedes,
  estados,
  puede,
  puedeBorrar,
  onDone,
  onError,
}: {
  sedes: Sede[];
  estados: string[];
  puede: boolean;
  puedeBorrar: boolean;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const [sid, setSid] = useState<number>(sedes[0].id);
  const sede = sedes.find((s) => s.id === sid) ?? sedes[0];
  return (
    <Card>
      <h4 className="text-base font-semibold text-brand-950">Editar, activar o desactivar sede</h4>
      <Field label="Seleccioná una sede">
        <Select value={String(sede.id)} options={sedes.map((s) => String(s.id))} label={(v) => etiquetaSede(sedes.find((s) => String(s.id) === v)!)} onChange={(v) => setSid(Number(v))} />
      </Field>
      <EditarForm key={sede.id} sede={sede} estados={estados} puede={puede} puedeBorrar={puedeBorrar} onDone={onDone} onError={onError} />
    </Card>
  );
}

function EditarForm({
  sede,
  estados,
  puede,
  puedeBorrar,
  onDone,
  onError,
}: {
  sede: Sede;
  estados: string[];
  puede: boolean;
  puedeBorrar: boolean;
  onDone: TabProps["onDone"];
  onError: TabProps["onError"];
}) {
  const [nombre, setNombre] = useState(String(sede.nombre ?? ""));
  const [direccion, setDireccion] = useState(String(sede.direccion ?? ""));
  const [localidad, setLocalidad] = useState(String(sede.localidad ?? ""));
  const [estado, setEstado] = useState(estados.includes(String(sede.estado ?? "Activa")) ? String(sede.estado ?? "Activa") : estados[0]);
  const [obs, setObs] = useState(String(sede.observaciones ?? ""));
  const [confirmar, setConfirmar] = useState(false);
  const guardar = useAccion(onDone, onError);
  const borrar = useAccion(onDone, onError);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Nombre">
          <TextInput value={nombre} onChange={setNombre} disabled={!puede} />
        </Field>
        <Field label="Calle y número">
          <TextInput value={direccion} onChange={setDireccion} disabled={!puede} />
        </Field>
        <Field label="Localidad">
          <TextInput value={localidad} onChange={setLocalidad} disabled={!puede} />
        </Field>
      </div>
      <div className="max-w-xs">
        <Field label="Estado">
          <Select value={estado} options={estados} onChange={setEstado} disabled={!puede} />
        </Field>
      </div>
      <Field label="Observaciones">
        <Textarea value={obs} onChange={setObs} rows={3} disabled={!puede} />
      </Field>
      {guardar.feedback && <Aviso feedback={guardar.feedback} />}
      {puede && (
        <PrimaryButton
          tone="secondary"
          busy={guardar.busy}
          onClick={() =>
            guardar.run(() =>
              post<WriteResult>("sedes/editar", { id: sede.id, nombre, direccion, localidad, estado, observaciones: obs, huella: sede.huella })
            )
          }
        >
          💾 Guardar cambios de la sede
        </PrimaryButton>
      )}
      <h5 className="pt-2 text-sm font-semibold text-brand-950">Eliminar una sede cargada por error</h5>
      <Aviso feedback={{ tone: "warning", text: "La eliminación quita la sede del catálogo. Las comisiones históricas conservan el texto que ya tenían guardado." }} />
      <Check checked={confirmar} onChange={setConfirmar} disabled={!puedeBorrar} label="Confirmo la eliminación definitiva de esta sede" />
      {borrar.feedback && <Aviso feedback={borrar.feedback} />}
      {puedeBorrar ? (
        <PrimaryButton
          tone="danger"
          busy={borrar.busy}
          onClick={() => borrar.run(() => post<WriteResult>("sedes/eliminar", { id: sede.id, confirmar, huella: sede.huella }))}
        >
          🗑️ Eliminar sede definitivamente
        </PrimaryButton>
      ) : (
        <Caption>Tu rol no puede eliminar sedes.</Caption>
      )}
    </div>
  );
}
