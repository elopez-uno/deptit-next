// Respuesta SINTÉTICA de POST /docentes/resumen con la forma exacta del backend (E4-05; consulta E4-06). Compartida por
// los tests de E4-05 y E4-06.
import type { Docente, DocentesOverview, Plantel, Resumen, SeccionTabla } from "@/lib/docentes";

export const docente = (cuil: string, nombre: string, legajo: string): Docente => ({
  cuil, legajo, apellido: nombre, nombres: "", nombre_completo: nombre, titulo: "Lic.", titulo_posgrado: "",
  antiguedad_anios: null, nivel_posgrado_salarial: "", email: null, telefono: null, ref_legajo_fisico: null,
  tipo_docente: "Propio", observaciones: "", estado: "Activo", fecha_alta: "2026-03-01", fecha_finalizacion: "",
  estado_periodo_abierto: "Activo en período actual", huella: cuil });
export const OV = {
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: null, fecha_fin: null, estado: "Abierto" },
  actual: { id: 9, nombre: "2026-2", fecha_inicio: null, fecha_fin: null, estado: "Abierto" },
  historico: false,
  docentes: [docente("20-00000001-1", "Uno, Docente", "L1"), docente("20-00000002-2", "Dos, Docente", "L2")],
  catalogos: { estados: [], estados_baja: [], tipos: [], niveles_posgrado: [], antiguedad_min: 0, antiguedad_max: 60 },
  permisos: { puede_escribir: false, puede_borrar: false, es_superadmin: false },
} as DocentesOverview;
export const PLANTEL: Plantel = { periodos: [], seleccionado: null, sin_periodos: "sin" };
export const tabla = (columnas: string[], ...filas: unknown[][]) => ({ columnas, filas });
export const sec = (titulo: string, t: ReturnType<typeof tabla> | null, vacio = "Sin datos.", caption: string | null = "Caption"): SeccionTabla => ({
  titulo, caption, tabla: t, vacio: t ? null : { tono: "info", texto: vacio } });
export const PERIODOS = [{ id: 9, nombre: "2026-2" }, { id: 5, nombre: "2026-1" }];

export function resumen(cuil: string, periodo = PERIODOS[0]): Resumen {
  const nombre = cuil.endsWith("1-1") ? "Uno, Docente" : "Dos, Docente";
  return {
    subtitulo: "Resumen individual del docente",
    info: "Seleccioná un docente y un período…",
    periodos: PERIODOS,
    seleccionado: periodo,
    estimacion: { etiqueta: "ESTIMACIÓN", advertencia: "El sueldo es una estimación: usa la lógica salarial certificada y puede no contemplar todos los conceptos." },
    consulta: {
      titulo: `Mensaje para consultar la designación — ${periodo.nombre}`, caption: "Genera un correo individual…",
      radio: "Estado de la consulta al docente",
      opciones: [
        { etiqueta: "⚪ Sin estado", valor: "", semaforo: { tono: "info", texto: "⚪ Estado seleccionado: **sin estado registrado**" } },
        { etiqueta: "🟢 Designación confirmada", valor: "Designación confirmada", semaforo: { tono: "success", texto: "🟢 Estado seleccionado: **Designación confirmada**" } },
      ],
      seleccion: "⚪ Sin estado", boton_guardar: "💾 Guardar estado de la consulta", boton_mensaje: "✉️ Generar mensaje para el docente",
      asunto_label: "Asunto sugerido", cuerpo_label: "Mensaje listo para copiar y pegar en el correo",
    },
    secciones: {
      datos_generales: {
        nombre, cuil, legajo: "L1", situacion: { texto: `Activo en ${periodo.nombre} - 1 designación/es - 20 hs`, tono: "success" },
        trayectoria: { inicio_historico: "2020-03-01", ultima_alta: "2026-03-01", finalizacion: "2026-12-31" },
        contacto: { mail: "-", telefono: "-" },
        formacion: { grado: "Lic.", posgrado: "-", nivel: "Sin adicional", antiguedad: "**Antigüedad:** no informada · para sueldo se toman 0 años (20%)" },
        observaciones: "Observación sintética",
      },
      tarjeta: {
        aviso_prestado: null, titulo: `Resumen actual del período — ${periodo.nombre}`, estado_designacion: "Estado de la designación: **Suspendida (licenciada)**",
        funciones_no_docentes: null, cargos: { label: "Cargo/s por departamento", lineas: ["Dep A: Titular", "Dep B: JTP"] },
        horas: { label: "Horas actuales totales", valor: "30 hs" },
        variacion: { label: "Aumento / disminución", valor: "+10 hs", tono: "positivo", caption: "Solo cambios reales de dedicación." },
        cambios: { label: "Cambio de cargo", lineas: ["Sin cambios de cargo registrados."] },
        evolucion: { titulo: "Evolución de horas del período", base: { label: "Horas base del período", valor: "20 hs" },
          movimiento: { label: "Aumento / disminución", valor: "+10 hs", tono: "positivo" }, resultado: { label: "Horas actuales", valor: "30 hs" } },
        compartido: "🧩 DOCENTE COMPARTIDO: tiene designaciones en más de un departamento para este período.",
        caption_origen: null, departamentos: tabla(["departamento", "cargo/s en el período", "horas"], ["Dep A", "Titular", 20], ["Dep B", "JTP", 10]),
      },
      designaciones: sec(`Designaciones institucionales del docente — ${periodo.nombre}`, tabla(["cargo", "dedicacion"], ["Titular", "Simple"])),
      actos: sec("📄 Resoluciones, disposiciones y actos administrativos", null, "No hay resoluciones, disposiciones u otros actos administrativos vinculados a este docente."),
      sueldo: { titulo: `💰 Sueldo estimado — ${periodo.nombre}`, vacio: null, caption: "Escala utilizada: **06/2026**", tabla: tabla(["Cargo", "Sueldo estimado"], ["Titular", "$ 584.573,72"]),
        total: { label: "Total estimado mensual del docente", valor: "$ 584.573,72" } },
      investigacion: sec(`Investigación del docente — ${periodo.nombre}`, tabla(["proyecto"], ["P1"])),
      extension: sec(`Extensión del docente — ${periodo.nombre}`, null, "Este docente no tiene horas/proyectos de extensión asignados en el período seleccionado."),
      actividades: sec(`Actividades Especiales del docente — ${periodo.nombre}`, null),
      comisiones: sec(`Comisiones asignadas al docente — ${periodo.nombre}`, tabla(["asignatura"], ["Álgebra"])),
      cronograma: { titulo: `Cronograma semanal — ${periodo.nombre}`, dias: ["Lunes", "Martes"],
        filas: [{ hora: "08:00–09:00", celdas: [{ labels: ["Álgebra"], titulo: "Álgebra · 08:00–10:00 · Dep A" }, null] }],
        caption: "Cronograma compacto de 08:00 a 23:00." },
      superposiciones: { ...sec(`Alertas de superposición — ${periodo.nombre}`, tabla(["día"], ["Lunes"])), aviso: "Este docente tiene superposiciones horarias entre sus comisiones." },
      productividad: { titulo: `Productividad del período — ${periodo.nombre}`, caption: "Vista individual institucional…",
        metricas: [{ label: "Hs contratadas", valor: "20.0" }, { label: "Productividad", valor: "75%" }, { label: "Disponibles", valor: "5.0" }],
        detalle_no_lectivas: { titulo: "Ver cálculo de horas no lectivas por comisión / departamento", tabla: tabla(["comision"], ["1"]) },
        torta: null, sin_torta: "No hay horas contratadas ni horas asignadas para graficar productividad." },
      materias_historicas: sec("Materias históricas del docente", tabla(["asignatura"], ["Álgebra"]), "", "Esta sección no depende del período seleccionado: acumula todos los períodos cargados."),
    },
  };
}

