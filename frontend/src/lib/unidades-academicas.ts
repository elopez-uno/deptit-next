// 6A-B3: una institución puede organizarse en facultades, escuelas, institutos, departamentos, centros...: las
// etiquetas visibles son genéricas ("Unidad académica"); las claves de los datos ("escuela", "escuelas",
// "escuela_oferente"...) son contrato de la API y no cambian. Los valores (nombres reales) se muestran tal cual.
export const ETIQUETAS_UNIDAD_ACADEMICA: Record<string, string> = {
  escuela: "Unidad académica",
  escuelas: "Unidades académicas",
  escuela_oferente: "Unidad académica oferente",
  escuela_oferente_opcion: "Unidad académica oferente",
  escuelas_destino: "Unidades académicas destino",
  escuela_snapshot: "Unidad académica",
};

/** Etiqueta visible de una columna cuya clave es el nombre crudo del dato. */
export const etiquetaColumna = (clave: string): string => ETIQUETAS_UNIDAD_ACADEMICA[clave] ?? clave;
