"""SQL de Resoluciones y respaldos sobre una conexion/transaccion ya abierta.  Nunca crea ni altera tablas (D-AK7) y
nunca confirma.

Todo el SQL del repositorio documental corre en el certificado por ``_pg_raw_conn()`` / ``_pg_read_dataframe`` (sin
inyector B12B): cada sentencia lleva su ambito explicito y asi se reproduce, literal, de la rama PostgreSQL:
- listado ``get_documentos_respaldo_v249`` l. 50436; relaciones v251 l. 50964 / 50970; vinculos exactos v266 l. 55671;
- PDF ``obtener_pdf_documento_respaldo_v249`` l. 50484 (solo en la descarga, D-AK12);
- dependencias v262 l. 50224 / 50252-50291 / 50328; alta v249 l. 50384 y docentes v251 l. 50907;
- PDF v272 l. 50523; borrado v251 l. 51483-51498 y v249 l. 50562;
- fuentes del Resumen docente (``get_actos_docente_resumen_v263`` l. 51316 / 51374 / 51407 y v266 l. 55824), que la
  Etapa 4 consumira sin deduplicar aca.
La tabla legacy ``resoluciones`` y ``designaciones.resolucion_id`` no se leen ni se escriben (D-AK14).
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from investigacion.repository import InvestigacionRepository

LISTADO_V249_SQL = """
            SELECT d.id, d.tipo_documento, COALESCE(d.tipo_resolucion,'') AS tipo_resolucion, d.categoria, COALESCE(d.numero,'') AS numero,
                   d.fecha, COALESCE(p.nombre,'') AS periodo,
                   COALESCE(d.docente_nombre,'') AS docente, COALESCE(d.cuil,'') AS cuil,
                   COALESCE(d.proyecto_tipo,'') AS proyecto_tipo, d.proyecto_id,
                   d.dependencia_id,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
                   COALESCE(d.referencia_texto,'') AS referencia,
                   COALESCE(d.titulo,'') AS titulo, COALESCE(d.detalle,'') AS detalle,
                   COALESCE(d.observaciones,'') AS observaciones,
                   d.archivo_nombre, COALESCE(d.archivo_bytes,0) AS archivo_bytes,
                   d.fecha_carga, COALESCE(d.usuario_carga,'') AS usuario_carga
            FROM documentos_respaldo d
            LEFT JOIN periodos p ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id
                                AND p.departamento_id=d.departamento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
            WHERE d.institucion_id=%s AND d.departamento_id=%s
            ORDER BY COALESCE(d.fecha, d.fecha_carga::date) DESC, d.id DESC
        """
REL_DOCENTES_SQL = """
                SELECT documento_id, cuil, COALESCE(docente_nombre,'') AS docente_nombre
                FROM documentos_respaldo_docentes
                WHERE institucion_id=%s AND departamento_id=%s
                ORDER BY docente_nombre, cuil
            """
REL_PROYECTOS_SQL = """
                SELECT documento_id, proyecto_tipo, proyecto_id,
                       COALESCE(proyecto_nombre,'') AS proyecto_nombre,
                       COALESCE(codigo_proyecto,'') AS codigo_proyecto
                FROM documentos_respaldo_proyectos
                WHERE institucion_id=%s AND departamento_id=%s
                ORDER BY proyecto_tipo, proyecto_nombre, codigo_proyecto, proyecto_id
            """
EXACTOS_V266_SQL = """
                SELECT r.documento_id, des.cuil,
                       COALESCE(NULLIF(TRIM(doc.apellido || ', ' || doc.nombres),''), NULLIF(TRIM(doc.nombre),''), des.cuil) AS docente_nombre
                FROM documentos_respaldo_designaciones r
                JOIN designaciones des ON des.id=r.designacion_id
                  AND des.institucion_id=r.institucion_id AND des.departamento_id=r.departamento_id
                LEFT JOIN docentes doc ON doc.cuil=des.cuil
                  AND doc.institucion_id=des.institucion_id AND doc.departamento_id=des.departamento_id
                WHERE r.institucion_id=%s AND r.departamento_id=%s
                UNION
                SELECT r.documento_id, m.cuil, COALESCE(NULLIF(TRIM(m.nombre),''), m.cuil) AS docente_nombre
                FROM documentos_respaldo_movimientos r
                JOIN movimientos m ON m.id=r.movimiento_id
                  AND m.institucion_id=r.institucion_id AND m.departamento_id=r.departamento_id
                WHERE r.institucion_id=%s AND r.departamento_id=%s
            """
PDF_SQL = """
            SELECT archivo_nombre, archivo_mime, archivo_pdf
            FROM documentos_respaldo
            WHERE id=%s AND institucion_id=%s AND departamento_id=%s
            LIMIT 1
        """
# NEXT (D-AK12): misma decision "tiene PDF" del detalle (``bool(pdf and pdf.get("bytes"))``) sin traer el binario.
PDF_BYTES_SQL = """
            SELECT octet_length(archivo_pdf) AS bytes
            FROM documentos_respaldo
            WHERE id=%s AND institucion_id=%s AND departamento_id=%s
            LIMIT 1
        """

DEPENDENCIAS_SQL = """
            SELECT id,nombre,COALESCE(estado,'Activa') AS estado,COALESCE(observaciones,'') AS observaciones,fecha_creacion,fecha_actualizacion
            FROM dependencias_documentales
            WHERE institucion_id=%s {filtro}
            ORDER BY CASE WHEN COALESCE(estado,'Activa')='Activa' THEN 0 ELSE 1 END, nombre
        """
DEPENDENCIA_DUP_SQL = ("SELECT id FROM dependencias_documentales WHERE institucion_id=%s AND "
                       "LOWER(TRIM(nombre))=LOWER(TRIM(%s)) LIMIT 1")
DEPENDENCIA_INSERT_SQL = ("INSERT INTO dependencias_documentales (institucion_id,nombre,estado,observaciones,"
                          "fecha_creacion,fecha_actualizacion) VALUES (%s,%s,'Activa',%s,CURRENT_TIMESTAMP,"
                          "CURRENT_TIMESTAMP)")
DEPENDENCIA_DUP_OTRA_SQL = ("SELECT id FROM dependencias_documentales WHERE institucion_id=%s AND "
                            "LOWER(TRIM(nombre))=LOWER(TRIM(%s)) AND id<>%s LIMIT 1")
DEPENDENCIA_UPDATE_SQL = ("UPDATE dependencias_documentales SET nombre=%s,estado=%s,observaciones=%s,"
                          "fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=%s AND institucion_id=%s")
DEPENDENCIA_PROPAGAR_SQL = "UPDATE documentos_respaldo SET dependencia_nombre=%s WHERE institucion_id=%s AND dependencia_id=%s"
DEPENDENCIA_DOCUMENTO_SQL = ("UPDATE documentos_respaldo SET dependencia_id=%s,dependencia_nombre=%s, tipo_resolucion=CASE "
                             "WHEN tipo_documento='Resolución' THEN %s ELSE COALESCE(tipo_resolucion,'') END WHERE id=%s "
                             "AND institucion_id=%s AND departamento_id=%s")

INSERT_DOCUMENTO_SQL = """
                INSERT INTO documentos_respaldo
                (institucion_id, departamento_id, tipo_documento, tipo_resolucion, categoria, numero, fecha,
                 periodo_id, cuil, docente_nombre, proyecto_tipo, proyecto_id, dependencia_id, dependencia_nombre, referencia_texto,
                 titulo, detalle, observaciones, archivo_nombre, archivo_mime, archivo_pdf,
                 archivo_bytes, fecha_carga, usuario_carga)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """
UPSERT_DOCENTE_SQL = """
                            INSERT INTO documentos_respaldo_docentes
                                (institucion_id, departamento_id, documento_id, cuil, docente_nombre,
                                 tipo_movimiento, detalle_vinculo)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (institucion_id, departamento_id, documento_id, cuil)
                            DO UPDATE SET docente_nombre=EXCLUDED.docente_nombre,
                                          tipo_movimiento=EXCLUDED.tipo_movimiento,
                                          detalle_vinculo=EXCLUDED.detalle_vinculo
                        """
UPDATE_PDF_SQL = """UPDATE documentos_respaldo
                   SET archivo_nombre=%s, archivo_mime=%s, archivo_pdf=%s, archivo_bytes=%s
                   WHERE id=%s AND institucion_id=%s AND departamento_id=%s"""
DELETE_VINCULOS_SQL = tuple(f"""
                DELETE FROM {tabla}
                WHERE documento_id=%s AND institucion_id=%s AND departamento_id=%s
            """ for tabla in ("documentos_respaldo_docentes", "documentos_respaldo_proyectos",
                              "documentos_respaldo_designaciones", "documentos_respaldo_movimientos"))
DELETE_DOCUMENTO_SQL = "DELETE FROM documentos_respaldo WHERE id=%s AND institucion_id=%s AND departamento_id=%s"

# --- fuentes del Resumen docente (Etapa 4: se exponen sin consolidar ni deduplicar) ---------------------------
RESUMEN_REPOSITORIO_SQL = """
                SELECT d.id, COALESCE(d.tipo_documento,'') AS tipo_documento,
                       COALESCE(d.numero,'') AS numero, d.fecha,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                                CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                     WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora,
                       COALESCE(NULLIF(TRIM(rd.tipo_movimiento),''), d.categoria, '') AS tipo_movimiento,
                       COALESCE(NULLIF(TRIM(rd.detalle_vinculo),''), d.detalle, '') AS detalle
                FROM documentos_respaldo_docentes rd
                JOIN documentos_respaldo d
                  ON d.id=rd.documento_id
                 AND d.institucion_id=rd.institucion_id
                 AND d.departamento_id=rd.departamento_id
                LEFT JOIN dependencias_documentales depdoc
                  ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE rd.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(rd.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY d.fecha DESC NULLS LAST, d.id DESC
            """
RESUMEN_DISPOSICIONES_SQL = """
                SELECT d.numero, d.fecha, COALESCE(d.tipo,'') AS tipo,
                       COALESCE(d.detalle,'') AS detalle,
                       COALESCE(dep.nombre,'') AS dependencia_emisora
                FROM disposiciones d
                LEFT JOIN departamentos dep
                  ON dep.id=d.departamento_id AND dep.institucion_id=d.institucion_id
                WHERE d.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY d.fecha DESC, d.id DESC
            """
RESUMEN_PENDIENTES_SQL = """
                SELECT COALESCE(d.numero_resolucion,'') AS numero_resolucion,
                       COALESCE(d.cargo,'') AS cargo, COALESCE(d.dedicacion,'') AS dedicacion,
                       COALESCE(d.tipo_designacion,'') AS tipo_designacion,
                       COALESCE(d.ad_honorem,'No') AS ad_honorem,
                       COALESCE(p.nombre,'') AS periodo, d.fecha_desde
                FROM designaciones d
                LEFT JOIN periodos p
                  ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id AND p.departamento_id=d.departamento_id
                LEFT JOIN documentos_respaldo_designaciones adr
                  ON adr.designacion_id=d.id AND adr.institucion_id=d.institucion_id AND adr.departamento_id=d.departamento_id
                WHERE d.institucion_id=%s
                  AND REGEXP_REPLACE(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
                  AND TRIM(COALESCE(d.numero_resolucion,''))<>''
                  AND adr.id IS NULL
                ORDER BY d.fecha_desde DESC NULLS LAST, d.id DESC
            """
RESUMEN_VINCULOS_V266_SQL = """
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       'Designación docente' AS tipo_movimiento,
                       'Acto administrativo vinculado a designación' AS detalle
                FROM documentos_respaldo_designaciones r
                JOIN documentos_respaldo d ON d.id=r.documento_id AND d.institucion_id=r.institucion_id
                JOIN designaciones des ON des.id=r.designacion_id AND des.institucion_id=r.institucion_id AND des.departamento_id=r.departamento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE r.institucion_id=%s AND regexp_replace(COALESCE(des.cuil,''),'[^0-9]','','g')=%s
                UNION ALL
                SELECT d.tipo_documento, COALESCE(d.numero,'') AS numero,
                       COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,'') AS dependencia_emisora,
                       COALESCE(m.tipo_movimiento,'') AS tipo_movimiento,
                       COALESCE(m.detalle,'') AS detalle
                FROM documentos_respaldo_movimientos r
                JOIN documentos_respaldo d ON d.id=r.documento_id AND d.institucion_id=r.institucion_id
                JOIN movimientos m ON m.id=r.movimiento_id AND m.institucion_id=r.institucion_id AND m.departamento_id=r.departamento_id
                LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
                WHERE r.institucion_id=%s AND regexp_replace(COALESCE(m.cuil,''),'[^0-9]','','g')=%s
            """

DEPENDENCIA_COLUMNAS = ["id", "nombre", "estado", "observaciones", "fecha_creacion", "fecha_actualizacion"]


class DocumentosRepository(InvestigacionRepository):
    """Repositorio documental de la operacion; hereda las lecturas y vinculos ya portados (Designaciones,
    Investigacion) sin modificarlos."""

    # --- lecturas del repositorio
    def documentos_v249(self) -> pd.DataFrame:
        return self.read_raw(LISTADO_V249_SQL, self._scope)

    def relacion_docentes(self) -> pd.DataFrame:
        return self.read_raw(REL_DOCENTES_SQL, self._scope)

    def relacion_proyectos(self) -> pd.DataFrame:
        return self.read_raw(REL_PROYECTOS_SQL, self._scope)

    def vinculos_exactos_v266(self) -> pd.DataFrame:
        return self.read_raw(EXACTOS_V266_SQL, self._scope + self._scope)

    def pdf(self, documento_id: int) -> Optional[dict]:
        return self._first(PDF_SQL, [int(documento_id)] + self._scope)

    def pdf_bytes(self, documento_id: int) -> Optional[int]:
        row = self._first(PDF_BYTES_SQL, [int(documento_id)] + self._scope)
        return None if row is None else int(row.get("bytes") or 0)

    def dependencias(self, solo_activas: bool = False) -> pd.DataFrame:
        filtro = " AND estado='Activa'" if solo_activas else ""
        df = self.read_raw(DEPENDENCIAS_SQL.replace("{filtro}", filtro), [self.inst])
        for col in DEPENDENCIA_COLUMNAS:
            if col not in df.columns:
                df[col] = ""
        return df[DEPENDENCIA_COLUMNAS]

    # --- fuentes del Resumen docente (Etapa 4)
    def resumen_repositorio(self, clave: str) -> list[dict]:
        return self._all(RESUMEN_REPOSITORIO_SQL, [self.inst, clave])

    def resumen_disposiciones(self, clave: str) -> list[dict]:
        return self._all(RESUMEN_DISPOSICIONES_SQL, [self.inst, clave])

    def resumen_pendientes(self, clave: str) -> list[dict]:
        return self._all(RESUMEN_PENDIENTES_SQL, [self.inst, clave])

    def resumen_vinculos_v266(self, clave: str) -> list[dict]:
        return self._all(RESUMEN_VINCULOS_V266_SQL, [self.inst, clave, self.inst, clave])

    # --- escrituras (cada una cuenta como sentencia mutante, deteccion textual B12H)
    def fetch_id(self, sql: str, params: list[Any]) -> Optional[int]:
        row = self._first(sql, params)
        return None if row is None else int(row["id"])

    def insert_documento(self, params: list[Any]) -> int:
        return self._insert_id(INSERT_DOCUMENTO_SQL, [self.inst, self.dep] + params)

    def upsert_docente(self, documento_id: int, item: dict) -> int:
        return self._mutate(UPSERT_DOCENTE_SQL, [self.inst, self.dep, int(documento_id), str(item["cuil"]),
                                                 str(item["nombre"]), str(item.get("tipo_movimiento", "") or ""),
                                                 str(item.get("detalle_vinculo", "") or "")])

    def update_pdf(self, nombre: str, mime: str, contenido: bytes, documento_id: int) -> int:
        return self._mutate(UPDATE_PDF_SQL, [nombre, mime, contenido, len(contenido), int(documento_id)] + self._scope)

    def update_dependencia_documento(self, dependencia_id: int, nombre: str, legacy: str, documento_id: int) -> int:
        return self._mutate(DEPENDENCIA_DOCUMENTO_SQL, [int(dependencia_id), nombre, legacy, int(documento_id)]
                            + self._scope)

    def delete_vinculos(self, documento_id: int) -> None:
        for sql in DELETE_VINCULOS_SQL:
            self._mutate(sql, [int(documento_id)] + self._scope)

    def delete_documento(self, documento_id: int) -> int:
        return self._mutate(DELETE_DOCUMENTO_SQL, [int(documento_id)] + self._scope)
