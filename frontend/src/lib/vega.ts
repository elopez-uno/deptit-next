// Carga diferida de vega-embed (solo en el navegador). Aislada para poder sustituirla en los tests.
export const cargarEmbed = () => import("vega-embed").then((m) => m.default);
