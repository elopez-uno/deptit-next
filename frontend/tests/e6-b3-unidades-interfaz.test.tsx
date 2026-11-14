// 6A-B3 (unidades académicas en toda la interfaz): una sola tabla de etiquetas para las claves crudas "escuela*";
// las tablas genéricas de Comisiones la usan; los valores (nombres reales) se muestran tal cual.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { TablaLibre } from "@/components/comisiones-shared";
import { ETIQUETAS_UNIDAD_ACADEMICA, etiquetaColumna } from "@/lib/unidades-academicas";

afterEach(() => cleanup());

test("etiquetas genéricas para las claves de unidad académica; el resto de las claves no cambia", () => {
  expect(etiquetaColumna("escuela")).toBe("Unidad académica");
  expect(etiquetaColumna("escuelas")).toBe("Unidades académicas");
  expect(etiquetaColumna("escuela_oferente")).toBe("Unidad académica oferente");
  expect(etiquetaColumna("escuelas_destino")).toBe("Unidades académicas destino");
  expect(etiquetaColumna("carrera")).toBe("carrera");
  expect(Object.values(ETIQUETAS_UNIDAD_ACADEMICA).every((v) => !/Escuela/.test(v))).toBe(true);
});

test("TablaLibre rotula la columna escuela como Unidad académica y muestra los nombres reales", () => {
  render(
    <TablaLibre
      rows={[
        { carrera: "Ingeniería en Inutilidad", escuela: "Facultad de Pelotudismo" },
        { carrera: "Analista", escuela: "Escuela de Ciencias Tecnológicas" },
        { carrera: "Tecnicatura", escuela: "Instituto de Tecnología" },
      ]}
    />,
  );
  const encabezados = screen.getAllByRole("columnheader").map((h) => h.textContent?.trim());
  expect(encabezados).toEqual(["carrera", "Unidad académica"]);
  for (const v of ["Facultad de Pelotudismo", "Escuela de Ciencias Tecnológicas", "Instituto de Tecnología"]) {
    expect(screen.getByText(v)).toBeTruthy();
  }
});

test("renombres explícitos siguen teniendo prioridad", () => {
  render(<TablaLibre rows={[{ escuela: "Facultad de Pelotudismo" }]} renombres={{ escuela: "Otra" }} />);
  expect(screen.getAllByRole("columnheader").map((h) => h.textContent?.trim())).toEqual(["Otra"]);
});
