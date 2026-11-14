"""GENERADO por tools_generar_motor_ciclo_periodos.py -- NO EDITAR A MANO.

Texto literal del entry certificado B13-FIX02 (app_postgresql_refactor_b13fix02_uat_fixes.py, sha256 95691fdf48c1edd393daf60bf435d6452b2fa8e95f6dcb7a2254cea8138d3363): definiciones
anteriores a la pagina Periodos (l. 61933) que usan Crear periodo (B12C), Revertir ultimo cierre,
los contadores del periodo vacio y Reparar finalizaciones automaticas (P-12b), 94 bloques en el orden del entry (incluye writers de negocio
y tareas de sistema).  Se ejecuta en el entorno de escritura de ``integraciones.ciclo_periodos`` dentro de
UNA transaccion por operacion; nunca a nivel modulo.
"""
# flake8: noqa
# fmt: off

# --- entry (literal)
DB_PATH = "C:/Users/augus/app_uoeste/designaciones.db"

# --- entry l. 537-538
class PeriodoDuplicadoError(ValueError):
    """Se lanza cuando se intenta crear nuevamente un período ya registrado."""


# --- entry l. 550-559
def _valor_configuracion(nombre, default=""):
    valor_entorno = os.environ.get(nombre)
    if valor_entorno is not None and str(valor_entorno).strip() != "":
        return valor_entorno
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass
    return default


# --- entry l. 1657-1665
def add_column_if_not_exists(cursor, table, column, definition):
    if USE_POSTGRESQL:
        # El esquema PostgreSQL se creó con el script de migración. Se deja no-op
        # para evitar ejecutar PRAGMA/ALTER de SQLite sobre PostgreSQL.
        return
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# --- entry l. 4339-4341
def safe_date(value, fallback):
    from analisis.motor.ref.extracted_batch04.fechas import safe_date as _b04_core_safe_date
    return _b04_core_safe_date(value, fallback)


# --- entry l. 4344-4346
def nombre_completo(apellido, nombres):
    from analisis.motor.ref.extracted_batch04.identidad import nombre_completo as _b04_core_nombre_completo
    return _b04_core_nombre_completo(apellido, nombres)


# --- entry l. 4349-4351
def nombre_periodo(anio, semestre):
    from analisis.motor.ref.extracted_batch01.periodos import nombre_periodo as _b01_core_nombre_periodo
    return _b01_core_nombre_periodo(anio, semestre)


# --- entry l. 4354-4356
def fechas_periodo(anio, semestre):
    from analisis.motor.ref.extracted_batch04.fechas import fechas_periodo as _b04_core_fechas_periodo
    return _b04_core_fechas_periodo(anio, semestre)


# --- entry l. 4424-4459
def registrar_movimiento(tipo, cuil, nombre, detalle, observaciones="", periodo_id=None, horas_variacion=0, fecha_movimiento=None):
    """Registra un movimiento permitiendo conservar su fecha efectiva real.

    v207: ``fecha_movimiento`` es opcional para mantener compatibilidad con todas
    las llamadas existentes. Si se informa (por ejemplo, una baja histórica), el
    movimiento queda fechado en el día en que ocurrió y no en el día de carga.
    """
    conn = get_conn()
    c = conn.cursor()
    add_column_if_not_exists(c, "movimientos", "horas_variacion", "REAL DEFAULT 0")
    try:
        horas_variacion = float(horas_variacion or 0)
    except Exception:
        horas_variacion = 0
    fecha_mov = ""
    if fecha_movimiento is not None:
        try:
            _fm = safe_date(fecha_movimiento, None)
            fecha_mov = _fm.isoformat() if _fm is not None else ""
        except Exception:
            fecha_mov = ""
    if not fecha_mov:
        fecha_mov = str(date.today())
    c.execute("""
        INSERT INTO movimientos
        (periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, horas_variacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (periodo_id, fecha_mov, tipo, cuil, nombre, detalle, observaciones, horas_variacion))
    movimiento_id = int(c.lastrowid) if getattr(c, "lastrowid", None) not in [None, ""] else None
    conn.commit()
    conn.close()
    try:
        invalidar_cache_rendimiento_v191(f"movimiento registrado: {tipo}")
    except Exception:
        pass
    return movimiento_id


# --- entry l. 4713-4721
def get_periodos():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        ORDER BY anio DESC, semestre DESC, id DESC
    """, conn)
    conn.close()
    return df


# --- entry l. 4724-4736
def get_periodo_abierto():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        WHERE estado = 'Abierto'
        ORDER BY id DESC
        LIMIT 1
    """, conn)
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# --- entry l. 4739-4741
def get_ultimo_periodo():
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_ultimo_periodo as _b03_core_get_ultimo_periodo
    return _b03_core_get_ultimo_periodo(get_conn=get_conn, pd=pd)


# --- entry l. 4742-4789
def get_designaciones(periodo_id=None):
    conn = get_conn()
    filtro = ""
    params = []
    if periodo_id is not None:
        filtro = "WHERE d.periodo_id = ?"
        params = [periodo_id]
    df = pd.read_sql(f"""
        SELECT
            d.id,
            d.periodo_id,
            p.nombre AS periodo,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo,
            d.cuil,
            d.cargo,
            d.dedicacion,
            d.horas,
            d.tipo_designacion,
            d.ad_honorem,
            d.fecha_desde,
            d.fecha_hasta,
            CASE
                -- v229: una designación solo puede ser Activa si pertenece al
                -- último período cronológico del departamento. Abrir un período
                -- histórico por excepción NO reactiva sus designaciones.
                WHEN d.estado = 'Activa'
                     AND d.periodo_id <> (
                         SELECT pult.id
                         FROM periodos pult
                         ORDER BY pult.anio DESC, pult.semestre DESC, pult.id DESC
                         LIMIT 1
                     )
                    THEN 'Finalizada'
                ELSE d.estado
            END AS estado,
            d.observaciones
        FROM designaciones d
        LEFT JOIN docentes doc ON d.cuil = doc.cuil
        LEFT JOIN periodos p ON d.periodo_id = p.id
        {filtro}
        ORDER BY p.anio DESC, p.semestre DESC, doc.apellido, doc.nombres
    """, conn, params=params)
    conn.close()
    return df


# --- entry l. 6336-6339
def _condicion_periodo_equivalente_sql(alias_periodo="p", alias_ref="pr"):
    'Condición SQL para comparar períodos equivalentes entre departamentos.'
    from analisis.motor.ref.extracted_batch01.periodos import _condicion_periodo_equivalente_sql as _b01_core__condicion_periodo_equivalente_sql
    return _b01_core__condicion_periodo_equivalente_sql(alias_periodo, alias_ref)


# --- entry l. 6616-6633
def _departamento_actual_operativo_nombre():
    """Departamento del usuario/ámbito actual, usado solo como respaldo."""
    dep_actual = ""
    try:
        dep_actual = (current_user() or {}).get("departamento_nombre") or ""
    except Exception:
        dep_actual = ""
    if not dep_actual and USE_POSTGRESQL:
        try:
            dep_id = _pg_current_dep_id()
            if dep_id:
                df_dep = _pg_read_dataframe("SELECT nombre FROM departamentos WHERE id = %s LIMIT 1", [int(dep_id)])
                if not df_dep.empty:
                    dep_actual = str(df_dep.iloc[0].get("nombre") or "")
        except Exception:
            dep_actual = ""
    dep_actual = " ".join(str(dep_actual or "").strip().split())
    return dep_actual or "Departamento correspondiente"


# --- entry l. 7735-7737
def normalizar_clave(valor):
    from analisis.motor.ref.extracted_batch04.texto import normalizar_clave as _b04_core_normalizar_clave
    return _b04_core_normalizar_clave(valor)


# --- entry l. 7784-7786
def _clave_cuil(valor):
    from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil as _b04_core__clave_cuil
    return _b04_core__clave_cuil(valor)


# --- entry l. 9576-9703
def sincronizar_vencimientos_concursados_v268(periodo_id):
    """Materializa como baja el vencimiento natural de concursadas dentro del período.

    La fecha contractual manda. No usa el estado físico como fuente de verdad porque una
    normalización técnica puede haber marcado la fila como Finalizada antes de que se
    registrara el movimiento. Es idempotente: identifica cada baja por designacion_id.
    """
    try:
        pid = int(periodo_id)
    except Exception:
        return 0
    conn = get_conn()
    try:
        dfp = pd.read_sql(
            "SELECT id,nombre,fecha_inicio,fecha_fin FROM periodos WHERE id=? LIMIT 1",
            conn, params=[pid],
        )
        if dfp.empty:
            return 0
        per = dfp.iloc[0].to_dict()
        inicio = safe_date(per.get("fecha_inicio"), None)
        fin = safe_date(per.get("fecha_fin"), None)
        hoy = date.today()
        df = pd.read_sql("""
            SELECT d.id,d.cuil,d.cargo,d.dedicacion,d.horas,d.tipo_designacion,
                   d.fecha_desde,d.fecha_hasta,d.fecha_hasta_prevista,
                   d.fecha_finalizacion_efectiva,d.estado,
                   CASE
                     WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre
                     ELSE d.cuil
                   END AS nombre_completo
            FROM designaciones d
            LEFT JOIN docentes doc ON doc.cuil=d.cuil
            WHERE d.periodo_id=?
              AND UPPER(TRIM(COALESCE(d.tipo_designacion,'')))='CONCURSADO'
        """, conn, params=[pid])
    finally:
        conn.close()
    if df.empty:
        return 0

    pendientes=[]
    for _,r in df.iterrows():
        desde=safe_date(r.get("fecha_desde"), None)
        # Una fecha_finalizacion_efectiva indica una baja anticipada real, no un
        # vencimiento natural. Esa baja ya se gestiona por la lógica canónica existente.
        if safe_date(r.get("fecha_finalizacion_efectiva"), None) is not None:
            continue
        hasta=safe_date(r.get("fecha_hasta_prevista"), None)
        if hasta is None:
            hasta=safe_date(r.get("fecha_hasta"), None)
        # El vencimiento se materializa a partir del día siguiente a fecha_hasta.
        # En períodos históricos, además, debe caer dentro de ese período.
        if hasta is None or hasta >= hoy:
            continue
        if fin is not None and hasta > fin:
            continue
        if inicio is not None and hasta < inicio:
            continue
        if desde is not None and hasta < desde:
            continue
        pendientes.append((r.to_dict(), hasta))

    creados=0
    for r,hasta in pendientes:
        did=int(r.get("id"))
        conn_u=get_conn(); c=conn_u.cursor()
        try:
            c.execute(
                "UPDATE designaciones SET estado='Finalizada' WHERE id=? AND UPPER(TRIM(COALESCE(estado,'Activa')))='ACTIVA'",
                (did,),
            )
            conn_u.commit()
        finally:
            conn_u.close()

        # Si al vencer esta concursada el docente quedó sin otra designación docente
        # vigente, aplica la misma baja automática de comisiones que una finalización real.
        try:
            _finalizar_comisiones_si_sin_designacion_docente_v214(
                str(r.get("cuil") or ""), pid, hasta, did
            )
        except Exception:
            pass
        try:
            sincronizar_cargos_asignaciones_docente_periodo(str(r.get("cuil") or ""), pid)
        except Exception:
            pass

        marcador=f"[designacion_id={did}]"
        conn_chk=get_conn()
        try:
            ex=pd.read_sql("""
                SELECT id FROM movimientos
                WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
                  AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))=LOWER(TRIM(?))
                  AND (COALESCE(observaciones,'') LIKE ? OR COALESCE(detalle,'') LIKE ?)
                LIMIT 1
            """,conn_chk,params=[
                pid,str(r.get("cuil") or ""),"Finalización automática por vencimiento de designación",
                f"%{marcador}%",f"%{marcador}%",
            ])
        finally:
            conn_chk.close()
        if not ex.empty:
            continue
        horas=float(pd.to_numeric(r.get("horas"),errors="coerce") or 0)
        detalle=(
            f"Vencimiento natural de designación concursada: {r.get('cargo','')} - "
            f"{r.get('dedicacion','')} - {horas:g} hs - Concursado. "
            f"Fecha de vencimiento: {hasta.isoformat()}. {marcador}"
        )
        registrar_movimiento(
            "Finalización automática por vencimiento de designación",
            str(r.get("cuil") or ""), str(r.get("nombre_completo") or ""),
            detalle,
            f"Baja automática por vencimiento contractual de la designación concursada. {marcador}",
            pid, horas_variacion=-abs(horas), fecha_movimiento=hasta,
        )
        creados += 1
    if pendientes:
        try:
            invalidar_cache_rendimiento_v191("vencimientos concursados v268")
            limpiar_cache_comisiones_operativas()
        except Exception:
            pass
    return creados


# --- entry l. 9706-9741
def _renovacion_concursada_legacy_valida_v268(cuil, periodo_id):
    """Valida una vieja 'Renovación automática' que fue rotulada como Concursado."""
    try:
        pid=int(periodo_id)
    except Exception:
        return False
    conn=get_conn()
    try:
        dfp=pd.read_sql("SELECT fecha_inicio,fecha_fin FROM periodos WHERE id=? LIMIT 1",conn,params=[pid])
        if dfp.empty:
            return False
        ini=safe_date(dfp.iloc[0].get("fecha_inicio"),None)
        fin=safe_date(dfp.iloc[0].get("fecha_fin"),None)
        dfd=pd.read_sql("""
            SELECT fecha_desde,fecha_hasta,fecha_hasta_prevista,fecha_finalizacion_efectiva
            FROM designaciones
            WHERE TRIM(COALESCE(cuil,''))=TRIM(?)
              AND UPPER(TRIM(COALESCE(tipo_designacion,'')))='CONCURSADO'
        """,conn,params=[str(cuil or "")])
    finally:
        conn.close()
    if dfd.empty:
        return False
    for _,r in dfd.iterrows():
        desde=safe_date(r.get("fecha_desde"),None)
        hasta=safe_date(r.get("fecha_finalizacion_efectiva"),None)
        if hasta is None:
            hasta=safe_date(r.get("fecha_hasta_prevista"),None)
        if hasta is None:
            hasta=safe_date(r.get("fecha_hasta"),None)
        if ini is not None and hasta is not None and hasta < ini:
            continue
        if fin is not None and desde is not None and desde > fin:
            continue
        return True
    return False


# --- entry l. 9750-9775
def _periodos_contexto_v269(periodo_id):
    """Devuelve período seleccionado, primero cronológico e inmediatamente anterior."""
    try:
        pid = int(periodo_id)
    except Exception:
        return None, None, None
    conn = get_conn()
    try:
        df = pd.read_sql("""
            SELECT id,nombre,anio,semestre,fecha_inicio,fecha_fin,estado
            FROM periodos
            ORDER BY COALESCE(anio,0), COALESCE(semestre,0), COALESCE(fecha_inicio,''), id
        """, conn)
    finally:
        conn.close()
    if df.empty:
        return None, None, None
    ids = pd.to_numeric(df["id"], errors="coerce")
    pos = df.index[ids.eq(pid)].tolist()
    if not pos:
        return None, df.iloc[0].to_dict(), None
    idx = df.index.get_loc(pos[0])
    actual = df.iloc[idx].to_dict()
    primero = df.iloc[0].to_dict()
    anterior = df.iloc[idx - 1].to_dict() if idx > 0 else None
    return actual, primero, anterior


# --- entry l. 9783-9785
def _vigente_al_cierre_v269(row, fecha_cierre):
    from analisis.motor.ref.domain.designaciones import _vigente_al_cierre_v269 as _b05_core__vigente_al_cierre_v269
    return _b05_core__vigente_al_cierre_v269(row, fecha_cierre)


# --- entry l. 9793-9795
def _detalle_coincide_designacion_v269(detalle, row):
    from analisis.motor.ref.domain.designaciones import _detalle_coincide_designacion_v269 as _b05_core__detalle_coincide_designacion_v269
    return _b05_core__detalle_coincide_designacion_v269(detalle, row)


# --- entry l. 9809-9812
def _depurar_bajas_movimientos_v269(df):
    """Eliminación = corrección de carga, no baja real; además quita duplicados/no-op."""
    from analisis.motor.ref.domain.catalog_unlocked.movimientos import _depurar_bajas_movimientos_v269 as _b08_core__depurar_bajas_movimientos_v269
    return _b08_core__depurar_bajas_movimientos_v269(df)


# --- entry l. 9815-9946
def _canonizar_movimientos_designaciones_v269(df_mov, periodo_id, preservar_no_designacion=True):
    """Reconstruye la lectura administrativa sin reescribir la auditoría de la base.

    - Primer período cronológico: una Alta por cada designación física real del período.
    - Períodos posteriores: un Alta legacy se muestra como Renovación/Continuidad si
      coincide con una designación vigente al cierre del período inmediatamente anterior.
    - Eliminaciones por corrección y bajas sin cambio real no integran indicadores.
    """
    if df_mov is None:
        return pd.DataFrame()
    base = df_mov.copy()
    actual, primero, anterior = _periodos_contexto_v269(periodo_id)
    if actual is None:
        return _depurar_bajas_movimientos_v269(base)
    pid = int(actual.get("id"))
    es_primero = primero is not None and int(primero.get("id")) == pid

    tipos_designacion = set(_TIPOS_INICIO_DESIGNACION_V269) | set(_TIPOS_BAJA_REAL_DESIGNACION_V269) | {
        "Eliminación de designación", "Eliminacion de designacion",
        "Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo",
        "Cambio de tipo de designación", "Cambio de número de resolución",
        "Cambio de condición Ad Honorem", "Pase a Ad Honorem", "Pase a Rentado",
        "Cambio de función docente / no docente", "Cambio de funciones no docentes",
        "Modificación general", "Finalización automática por cierre de período",
    }

    if preservar_no_designacion:
        no_des = base[~base.get("tipo_movimiento", pd.Series(index=base.index,dtype=str)).fillna("").astype(str).isin(tipos_designacion)].copy()
        des_mov = base[base.get("tipo_movimiento", pd.Series(index=base.index,dtype=str)).fillna("").astype(str).isin(tipos_designacion)].copy()
    else:
        no_des = pd.DataFrame(columns=base.columns)
        des_mov = base.copy()

    des_mov = _depurar_bajas_movimientos_v269(des_mov)

    try:
        actuales = get_designaciones(pid)
        if actuales is None:
            actuales = pd.DataFrame()
    except Exception:
        actuales = pd.DataFrame()

    if es_primero:
        # El primer período es la línea de base institucional. Los viejos movimientos
        # de alta estaban incompletos porque la carga inicial precede al historial actual.
        if not des_mov.empty:
            des_mov = des_mov[~des_mov["tipo_movimiento"].fillna("").astype(str).isin(_TIPOS_INICIO_DESIGNACION_V269)].copy()
        sinteticas = []
        inicio_per = safe_date(actual.get("fecha_inicio"), None)
        fin_per = safe_date(actual.get("fecha_fin"), None)
        nombre_per = str(actual.get("nombre") or "")
        for _, d in actuales.iterrows():
            did = int(pd.to_numeric(d.get("id"), errors="coerce") or 0)
            fdesde = safe_date(d.get("fecha_desde"), None)
            fecha_mov = fdesde if (fdesde is not None and (inicio_per is None or fdesde >= inicio_per) and (fin_per is None or fdesde <= fin_per)) else inicio_per
            hs = float(pd.to_numeric(d.get("horas"), errors="coerce") or 0)
            detalle = (
                f"{nombre_per} - {d.get('cargo','')} - {d.get('dedicacion','')} - {hs:g} hs - "
                f"{d.get('tipo_designacion','')}"
            )
            fila = {c: pd.NA for c in base.columns}
            fila.update({
                "id": -900000000 - did,
                "periodo_id": pid,
                "periodo": nombre_per,
                "fecha": fecha_mov.isoformat() if fecha_mov is not None else str(actual.get("fecha_inicio") or ""),
                "tipo_movimiento": "Alta de designación",
                "cuil": d.get("cuil", ""),
                "nombre": d.get("nombre_completo", d.get("nombre", d.get("cuil", ""))),
                "detalle": detalle,
                "observaciones": "Base inicial del sistema: la designación real del primer período se considera alta para el análisis histórico.",
                "horas_variacion": abs(hs),
            })
            if "acto_documento_id" in base.columns:
                fila["acto_documento_id"] = d.get("acto_documento_id", pd.NA)
            if "acto_administrativo" in base.columns:
                fila["acto_administrativo"] = d.get("acto_administrativo", "Pendiente de vincular")
            sinteticas.append(fila)
        if sinteticas:
            des_mov = pd.concat([des_mov, pd.DataFrame(sinteticas)], ignore_index=True, sort=False)
    elif anterior is not None and not des_mov.empty:
        try:
            prev = get_designaciones(int(anterior.get("id")))
            if prev is None:
                prev = pd.DataFrame()
        except Exception:
            prev = pd.DataFrame()
        cierre_prev = safe_date(anterior.get("fecha_fin"), None)
        if not prev.empty:
            prev = prev[prev.apply(lambda r: _vigente_al_cierre_v269(r, cierre_prev), axis=1)].copy()
        for idx, mov in des_mov.iterrows():
            if str(mov.get("tipo_movimiento") or "").strip() != "Alta de designación":
                continue
            clave = _clave_cuil(mov.get("cuil")) or str(mov.get("cuil") or "").strip()
            candidatos = prev[prev.get("cuil", pd.Series(index=prev.index,dtype=str)).fillna("").astype(str).map(lambda x: _clave_cuil(x) or str(x).strip()).eq(clave)].copy() if not prev.empty else pd.DataFrame()
            if candidatos.empty:
                continue
            coinciden = candidatos[candidatos.apply(lambda r: _detalle_coincide_designacion_v269(mov.get("detalle", ""), r), axis=1)].copy()
            if coinciden.empty and len(candidatos) == 1:
                coinciden = candidatos.copy()
            if coinciden.empty:
                continue
            # Si varias coinciden por un legacy poco específico, solo se reclasifica si todas
            # llevan al mismo tipo administrativo.
            tipos_prev = {normalizar_clave(x) for x in coinciden.get("tipo_designacion", pd.Series(dtype=str)).fillna("").astype(str)}
            if tipos_prev == {"CONCURSADO"}:
                nuevo_tipo = "Continuidad automática de designación concursada"
                nota = "Reclasificado desde un Alta legacy: la concursada ya estaba vigente al cierre del período anterior."
            elif "CONCURSADO" not in tipos_prev:
                nuevo_tipo = "Renovación automática de designación"
                nota = "Reclasificado desde un Alta legacy: la designación ya estaba vigente al cierre del período anterior."
            else:
                continue
            des_mov.at[idx, "tipo_movimiento"] = nuevo_tipo
            obs = str(des_mov.at[idx, "observaciones"] or "").strip() if "observaciones" in des_mov.columns else ""
            if "observaciones" in des_mov.columns:
                des_mov.at[idx, "observaciones"] = (obs + " | " if obs else "") + nota
            if "horas_variacion" in des_mov.columns:
                des_mov.at[idx, "horas_variacion"] = 0

    out = pd.concat([no_des, des_mov], ignore_index=True, sort=False) if preservar_no_designacion else des_mov
    if out.empty:
        return out
    # Orden estable: movimientos más recientes primero, como las vistas administrativas.
    orden_cols = [c for c in ["fecha", "id"] if c in out.columns]
    if orden_cols:
        asc = [False] * len(orden_cols)
        try:
            out = out.sort_values(orden_cols, ascending=asc, kind="stable", na_position="last")
        except Exception:
            pass
    return out.reset_index(drop=True)


# --- entry l. 9949-10231
def copiar_designaciones_periodo(periodo_origen_id, periodo_destino_id, nombre_destino, copiar_no_concursadas=True):
    """Incorpora designaciones al nuevo período respetando su naturaleza.

    Reglas:
    - Las designaciones concursadas no son cuatrimestrales. Se buscan en todo el
      historial del departamento y se trasladan al nuevo período solo cuando su
      rango real de vigencia se superpone con el período de destino. Sus fechas
      originales se conservan sin reemplazarlas por las fechas del período.
    - Las designaciones no concursadas se renuevan únicamente si estaban vigentes
      en la fecha de cierre del período anterior. El estado físico no alcanza: se
      comprueban sus fechas contractuales y cualquier baja efectiva.
    """
    conn = get_conn()
    df_destino = pd.read_sql("""
        SELECT id, nombre, anio, fecha_inicio, fecha_fin
        FROM periodos
        WHERE id = ?
        LIMIT 1
    """, conn, params=[periodo_destino_id])

    if df_destino.empty:
        conn.close()
        return 0

    periodo_destino = df_destino.iloc[0].to_dict()
    fecha_inicio_destino = pd.to_datetime(periodo_destino.get("fecha_inicio"), errors="coerce")
    fecha_fin_destino = pd.to_datetime(periodo_destino.get("fecha_fin"), errors="coerce")

    periodo_origen = None
    fecha_cierre_origen = pd.NaT
    if periodo_origen_id is not None:
        df_origen = pd.read_sql("SELECT id,nombre,fecha_inicio,fecha_fin FROM periodos WHERE id=? LIMIT 1", conn, params=[periodo_origen_id])
        if not df_origen.empty:
            periodo_origen = df_origen.iloc[0].to_dict()
            fecha_cierre_origen = pd.to_datetime(periodo_origen.get("fecha_fin"), errors="coerce")

    def _fecha_ts(valor):
        try:
            if valor is None or pd.isna(valor) or str(valor).strip() == "":
                return pd.NaT
            return pd.to_datetime(str(valor).strip(), errors="coerce", dayfirst=False)
        except Exception:
            return pd.NaT

    def _fin_real_fila(fila):
        for campo in ["fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"]:
            v = _fecha_ts(fila.get(campo))
            if not pd.isna(v):
                return v
        return pd.NaT

    def _vigente_en_cierre_origen(fila):
        if pd.isna(fecha_cierre_origen):
            return True
        desde = _fecha_ts(fila.get("fecha_desde"))
        hasta = _fin_real_fila(fila)
        if not pd.isna(desde) and desde > fecha_cierre_origen:
            return False
        if not pd.isna(hasta) and hasta < fecha_cierre_origen:
            return False
        return True

    def _vigente_en_destino(fila):
        desde = _fecha_ts(fila.get("fecha_desde"))
        hasta = _fin_real_fila(fila)
        if not pd.isna(fecha_fin_destino) and not pd.isna(desde) and desde > fecha_fin_destino:
            return False
        if not pd.isna(fecha_inicio_destino) and not pd.isna(hasta) and hasta < fecha_inicio_destino:
            return False
        return True

    # Las concursadas se recuperan desde todo el historial, porque una misma
    # designación puede abarcar varios años y haber quedado técnicamente
    # finalizada al cerrar períodos anteriores.
    df_concursadas = pd.read_sql("""
        SELECT
            d.id, d.cuil, d.cargo, d.dedicacion, d.horas,
            d.tipo_designacion, COALESCE(d.numero_resolucion, '') AS numero_resolucion,
            d.ad_honorem, d.fecha_desde, d.fecha_hasta,
            d.fecha_hasta_prevista, d.fecha_finalizacion_efectiva,
            d.estado, d.observaciones,
            COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
            COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo
        FROM designaciones d
        LEFT JOIN docentes doc ON d.cuil = doc.cuil
        WHERE UPPER(TRIM(COALESCE(d.tipo_designacion, ''))) = 'CONCURSADO'
          AND UPPER(TRIM(COALESCE(d.estado, ''))) <> 'SUSPENDIDA'
        ORDER BY d.id DESC
    """, conn)

    if not df_concursadas.empty:
        df_concursadas = df_concursadas[
            df_concursadas.apply(_vigente_en_cierre_origen, axis=1)
            & df_concursadas.apply(_vigente_en_destino, axis=1)
        ].copy()

        # El mismo cargo concursado puede aparecer repetido en varios períodos.
        # Se elimina únicamente la repetición exacta de la misma designación,
        # conservando distintas designaciones aunque pertenezcan al mismo docente.
        vistos = set()
        indices = []
        for idx, row in df_concursadas.iterrows():
            clave = (
                str(row.get("cuil") or "").strip(),
                str(row.get("cargo") or "").strip().lower(),
                str(row.get("dedicacion") or "").strip().lower(),
                int(float(row.get("horas") or 0)),
                str(row.get("ad_honorem") or "No").strip().lower(),
                str(row.get("numero_resolucion") or "").strip().lower(),
                str(row.get("fecha_desde") or "").strip(),
                str(row.get("fecha_hasta") or "").strip(),
                1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
                _texto_funcion_no_docente_limpio_v164(row.get("texto_funcion_no_docente", "")),
            )
            if clave in vistos:
                continue
            vistos.add(clave)
            indices.append(idx)
        df_concursadas = df_concursadas.loc[indices].copy()

    # Las no concursadas sí se renuevan desde el período inmediatamente anterior.
    if copiar_no_concursadas and periodo_origen_id is not None:
        df_no_concursadas = pd.read_sql("""
            SELECT
                d.cuil, d.cargo, d.dedicacion, d.horas,
                d.tipo_designacion, COALESCE(d.numero_resolucion, '') AS numero_resolucion,
                d.ad_honorem, d.observaciones, d.estado, d.fecha_desde, d.fecha_hasta,
                d.fecha_hasta_prevista, d.fecha_finalizacion_efectiva,
                COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente,
                COALESCE(d.texto_funcion_no_docente, '') AS texto_funcion_no_docente,
                p.anio AS anio_origen,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE ''
                END AS nombre_completo
            FROM designaciones d
            LEFT JOIN docentes doc ON d.cuil = doc.cuil
            LEFT JOIN periodos p ON p.id = d.periodo_id
            WHERE d.periodo_id = ?
              AND UPPER(TRIM(COALESCE(d.estado, ''))) <> 'SUSPENDIDA'
              AND UPPER(TRIM(COALESCE(d.tipo_designacion, ''))) <> 'CONCURSADO'
        """, conn, params=[periodo_origen_id])
        if not df_no_concursadas.empty:
            df_no_concursadas = df_no_concursadas[
                df_no_concursadas.apply(_vigente_en_cierre_origen, axis=1)
            ].copy()
    else:
        df_no_concursadas = pd.DataFrame()

    c = conn.cursor()
    movimientos = []
    copiados = 0

    # Continuidad de concursadas vigentes: conserva fechas reales.
    for _, row in df_concursadas.iterrows():
        fecha_desde = "" if pd.isna(row.get("fecha_desde")) else str(row.get("fecha_desde"))
        fecha_hasta = "" if pd.isna(row.get("fecha_hasta")) else str(row.get("fecha_hasta"))
        horas = int(float(row.get("horas") or 0))

        c.execute("""
            SELECT id
            FROM designaciones
            WHERE periodo_id = ?
              AND cuil = ?
              AND UPPER(TRIM(COALESCE(cargo, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(dedicacion, ''))) = UPPER(TRIM(?))
              AND COALESCE(horas, 0) = ?
              AND UPPER(TRIM(COALESCE(tipo_designacion, ''))) = 'CONCURSADO'
              AND UPPER(TRIM(COALESCE(ad_honorem, 'No'))) = UPPER(TRIM(?))
              AND TRIM(COALESCE(numero_resolucion, '')) = TRIM(?)
              AND COALESCE(fecha_desde, '') = ?
              AND COALESCE(fecha_hasta, '') = ?
              AND COALESCE(funcion_no_docente, 0) = ?
            LIMIT 1
        """, (
            periodo_destino_id, row.get("cuil"), row.get("cargo", ""),
            row.get("dedicacion", ""), horas, row.get("ad_honorem", "No"),
            str(row.get("numero_resolucion") or "").strip(), fecha_desde, fecha_hasta,
            1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
        ))
        if c.fetchone():
            continue

        c.execute("""
            INSERT INTO designaciones
            (periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, numero_resolucion,
             ad_honorem, fecha_desde, fecha_hasta, estado, observaciones,
             funcion_no_docente, texto_funcion_no_docente)
            VALUES (?, ?, ?, ?, ?, 'Concursado', ?, ?, ?, ?, 'Activa', ?, ?, ?)
        """, (
            periodo_destino_id, row.get("cuil"), row.get("cargo", ""),
            row.get("dedicacion", ""), horas, str(row.get("numero_resolucion") or "").strip(),
            row.get("ad_honorem", "No"), fecha_desde, fecha_hasta, row.get("observaciones", ""),
            1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
            _texto_funcion_no_docente_limpio_v164(row.get("texto_funcion_no_docente", "")),
        ))
        copiados += 1
        movimientos.append((
            "Continuidad automática de designación concursada",
            row.get("cuil", ""),
            row.get("nombre_completo", ""),
            f"Se incorporó en {nombre_destino} la designación concursada vigente: "
            f"{row.get('cargo', '')} - {row.get('dedicacion', '')} - {horas} hs "
            f"({fecha_desde or 'sin fecha de inicio'} al {fecha_hasta or 'sin fecha de fin'}).",
            "La designación conserva sus fechas originales porque su vigencia excede el período académico."
        ))

    # Renovación de interinas, locaciones y otras no concursadas: usa las fechas
    # del nuevo período, igual que la lógica cuatrimestral existente.
    for _, row in df_no_concursadas.iterrows():
        horas = int(float(row.get("horas") or 0))
        fecha_desde = str(periodo_destino.get("fecha_inicio") or "")
        fecha_hasta = str(periodo_destino.get("fecha_fin") or "")
        # v156: Interinos, Loc. Serv. y cualquier otra designación no concursada
        # tienen una resolución propia de CADA período académico. Al renovar/copiar
        # la designación al período siguiente nunca se arrastra el número anterior:
        # queda vacío para obligar a cargar la nueva resolución de ese período.
        # Solo las designaciones concursadas (manejadas en el bloque anterior)
        # conservan la misma resolución mientras continúen vigentes.
        numero_resolucion_nueva = ""
        c.execute("""
            SELECT id
            FROM designaciones
            WHERE periodo_id = ?
              AND cuil = ?
              AND UPPER(TRIM(COALESCE(cargo, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(dedicacion, ''))) = UPPER(TRIM(?))
              AND COALESCE(horas, 0) = ?
              AND UPPER(TRIM(COALESCE(tipo_designacion, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(ad_honorem, 'No'))) = UPPER(TRIM(?))
              AND TRIM(COALESCE(numero_resolucion, '')) = TRIM(?)
              AND COALESCE(fecha_desde, '') = ?
              AND COALESCE(fecha_hasta, '') = ?
              AND COALESCE(funcion_no_docente, 0) = ?
            LIMIT 1
        """, (
            periodo_destino_id, row.get("cuil"), row.get("cargo", ""),
            row.get("dedicacion", ""), horas, row.get("tipo_designacion", ""),
            row.get("ad_honorem", "No"), numero_resolucion_nueva, fecha_desde, fecha_hasta,
            1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
        ))
        if c.fetchone():
            continue

        c.execute("""
            INSERT INTO designaciones
            (periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, numero_resolucion,
             ad_honorem, fecha_desde, fecha_hasta, estado, observaciones,
             funcion_no_docente, texto_funcion_no_docente)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activa', ?, ?, ?)
        """, (
            periodo_destino_id, row.get("cuil"), row.get("cargo", ""),
            row.get("dedicacion", ""), horas, row.get("tipo_designacion", ""), numero_resolucion_nueva,
            row.get("ad_honorem", "No"), fecha_desde, fecha_hasta,
            row.get("observaciones", ""),
            1 if _es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
            _texto_funcion_no_docente_limpio_v164(row.get("texto_funcion_no_docente", "")),
        ))
        copiados += 1
        movimientos.append((
            "Renovación automática de designación",
            row.get("cuil", ""),
            row.get("nombre_completo", ""),
            f"Se renovó en {nombre_destino}: {row.get('cargo', '')} - "
            f"{row.get('dedicacion', '')} - {horas} hs - {row.get('tipo_designacion', '')}",
            "Generado al crear un nuevo período copiando el anterior."
        ))

    conn.commit()
    conn.close()

    for tipo_mov, cuil, nombre, detalle, observacion in movimientos:
        registrar_movimiento(
            tipo_mov, cuil, nombre, detalle, observacion, periodo_destino_id
        )

    return copiados


# --- entry l. 10497-10559
def finalizar_designaciones_activas_periodo(periodo_id, registrar=True, observaciones=""):
    """Finaliza las designaciones activas de un período cerrado o que está por cerrarse."""
    conn = get_conn()

    df_periodo = pd.read_sql("""
        SELECT id, nombre, fecha_inicio, fecha_fin, estado
        FROM periodos
        WHERE id = ?
        LIMIT 1
    """, conn, params=[periodo_id])

    if df_periodo.empty:
        conn.close()
        return 0

    periodo = df_periodo.iloc[0].to_dict()

    df_activas = pd.read_sql("""
        SELECT
            d.id,
            d.cuil,
            d.cargo,
            d.dedicacion,
            d.horas,
            d.tipo_designacion,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo
        FROM designaciones d
        LEFT JOIN docentes doc ON d.cuil = doc.cuil
        WHERE d.periodo_id = ?
          AND d.estado = 'Activa'
    """, conn, params=[periodo_id])

    if df_activas.empty:
        conn.close()
        return 0

    c = conn.cursor()
    c.execute("""
        UPDATE designaciones
        SET estado = 'Finalizada',
            fecha_hasta = COALESCE(NULLIF(fecha_hasta, ''), ?)
        WHERE periodo_id = ?
          AND estado = 'Activa'
    """, (periodo["fecha_fin"], periodo_id))
    conn.commit()
    conn.close()

    if registrar:
        for _, row in df_activas.iterrows():
            registrar_movimiento(
                "Finalización automática por cierre de período",
                row["cuil"],
                row["nombre_completo"],
                f"Al cerrar {periodo['nombre']}, se finalizó: {row['cargo']} - {row['dedicacion']} - {row['horas']} hs - {row['tipo_designacion']}",
                observaciones or "Generado automáticamente al cerrar el período.",
                periodo_id
            )

    return len(df_activas)


# --- entry l. 10743-10745
def _fecha_proyecto(valor):
    from analisis.motor.ref.extracted_batch04.fechas import _fecha_proyecto as _b04_core__fecha_proyecto
    return _b04_core__fecha_proyecto(valor)


# --- entry l. 10748-10750
def _fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado=None):
    from analisis.motor.ref.domain.proyectos import _fechas_desde_periodo_legacy as _b05_core__fechas_desde_periodo_legacy
    return _b05_core__fechas_desde_periodo_legacy(periodo_ejecucion, anio_llamado)


# --- entry l. 10753-10755
def _texto_periodo_proyecto(fecha_inicio, fecha_fin):
    from analisis.motor.ref.domain.proyectos import _texto_periodo_proyecto as _b05_core__texto_periodo_proyecto
    return _b05_core__texto_periodo_proyecto(fecha_inicio, fecha_fin)


# --- entry l. 10774-10776
def proyecto_vigente_en_periodo(proyecto, periodo):
    from analisis.motor.ref.domain.proyectos import proyecto_vigente_en_periodo as _b05_core_proyecto_vigente_en_periodo
    return _b05_core_proyecto_vigente_en_periodo(proyecto, periodo)


# --- entry l. 10780-11164
def asegurar_esquema_investigacion_separado():
    """Prepara el catálogo institucional de proyectos y las asignaciones departamentales.

    En PostgreSQL existe un único registro de cada proyecto por institución. El
    campo ``departamento_id`` conserva el departamento creador, pero no limita la
    visibilidad: todos los departamentos de la institución pueden usar el proyecto.
    Las filas de ``investigacion_docente`` continúan perteneciendo al departamento
    que realizó cada asignación.
    """
    if st.session_state.get("_esquema_investigacion_institucional_v4_ok"):
        return

    if USE_POSTGRESQL:
        try:
            import psycopg2
            conn = _pg_raw_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proyectos_investigacion (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    nombre_proyecto TEXT NOT NULL,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    anio_llamado INTEGER,
                    fecha_inicio DATE,
                    fecha_fin DATE,
                    periodo_ejecucion TEXT,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Activo',
                    fecha_carga TEXT,
                    fecha_suspension DATE,
                    motivo_suspension TEXT
                )
            """)
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_inicio DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_fin DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS fecha_suspension DATE")
            cur.execute("ALTER TABLE proyectos_investigacion ADD COLUMN IF NOT EXISTS motivo_suspension TEXT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS proyecto_id BIGINT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS estado_asignacion TEXT DEFAULT 'Activa'")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS fecha_baja TEXT")
            cur.execute("ALTER TABLE investigacion_docente ADD COLUMN IF NOT EXISTS motivo_baja TEXT")
            cur.execute("""
                UPDATE investigacion_docente
                SET estado_asignacion = 'Activa'
                WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
            """)

            # Vincula registros históricos todavía sueltos con un proyecto
            # institucional. El departamento del primer registro queda como creador.
            cur.execute("""
                SELECT DISTINCT institucion_id, departamento_id,
                    COALESCE(nombre_proyecto, ''), COALESCE(codigo_proyecto, ''),
                    COALESCE(instituto_proyecto, ''), anio_llamado,
                    COALESCE(periodo_ejecucion, '')
                FROM investigacion_docente
                WHERE proyecto_id IS NULL
                  AND TRIM(COALESCE(nombre_proyecto, '')) <> ''
                ORDER BY institucion_id, departamento_id
            """)
            for inst_id, dep_id, nombre, codigo, instituto, anio, ejecucion in cur.fetchall():
                if str(codigo or "").strip():
                    cur.execute("""
                        SELECT id
                        FROM proyectos_investigacion
                        WHERE institucion_id = %s
                          AND UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = UPPER(TRIM(%s))
                        ORDER BY id
                        LIMIT 1
                    """, [inst_id, codigo])
                else:
                    fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                    cur.execute("""
                        SELECT id
                        FROM proyectos_investigacion
                        WHERE institucion_id = %s
                          AND UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = UPPER(TRIM(%s))
                          AND COALESCE(anio_llamado, -1) = COALESCE(%s, -1)
                          AND fecha_inicio IS NOT DISTINCT FROM %s
                          AND fecha_fin IS NOT DISTINCT FROM %s
                        ORDER BY id
                        LIMIT 1
                    """, [inst_id, nombre, anio, fecha_inicio, fecha_fin])
                fila = cur.fetchone()
                if fila:
                    proyecto_id = int(fila[0])
                else:
                    fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                    cur.execute("""
                        INSERT INTO proyectos_investigacion
                        (institucion_id, departamento_id, nombre_proyecto, codigo_proyecto,
                         instituto_proyecto, anio_llamado, fecha_inicio, fecha_fin,
                         periodo_ejecucion, observaciones, estado, fecha_carga)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '', 'Activo', %s)
                        RETURNING id
                    """, [inst_id, dep_id, nombre, codigo, instituto, anio,
                          fecha_inicio, fecha_fin, ejecucion, str(date.today())])
                    proyecto_id = int(cur.fetchone()[0])

                if str(codigo or "").strip():
                    cur.execute("""
                        UPDATE investigacion_docente
                        SET proyecto_id = %s
                        WHERE proyecto_id IS NULL
                          AND institucion_id = %s
                          AND departamento_id IS NOT DISTINCT FROM %s
                          AND UPPER(TRIM(COALESCE(codigo_proyecto, ''))) = UPPER(TRIM(%s))
                    """, [proyecto_id, inst_id, dep_id, codigo])
                else:
                    cur.execute("""
                        UPDATE investigacion_docente
                        SET proyecto_id = %s
                        WHERE proyecto_id IS NULL
                          AND institucion_id = %s
                          AND departamento_id IS NOT DISTINCT FROM %s
                          AND UPPER(TRIM(COALESCE(nombre_proyecto, ''))) = UPPER(TRIM(%s))
                          AND COALESCE(anio_llamado, -1) = COALESCE(%s, -1)
                          AND UPPER(TRIM(COALESCE(periodo_ejecucion, ''))) = UPPER(TRIM(%s))
                    """, [proyecto_id, inst_id, dep_id, nombre, anio, ejecucion])

            # Migra períodos antiguos escritos como texto a fechas reales.
            cur.execute("""
                SELECT id, periodo_ejecucion, anio_llamado
                FROM proyectos_investigacion
                WHERE fecha_inicio IS NULL OR fecha_fin IS NULL
            """)
            for proyecto_id, ejecucion, anio in cur.fetchall():
                fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                if fecha_inicio or fecha_fin:
                    cur.execute("""
                        UPDATE proyectos_investigacion
                        SET fecha_inicio = COALESCE(fecha_inicio, %s),
                            fecha_fin = COALESCE(fecha_fin, %s),
                            periodo_ejecucion = %s
                        WHERE id = %s
                    """, [fecha_inicio, fecha_fin,
                          _texto_periodo_proyecto(fecha_inicio, fecha_fin) or ejecucion,
                          proyecto_id])

            # Unifica las copias departamentales existentes. Primero se redirigen
            # todas las asignaciones al id canónico y después se borran duplicados.
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(codigo_proyecto, '')))
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
                )
                UPDATE investigacion_docente i
                SET proyecto_id = r.canonico
                FROM ranked r
                WHERE i.proyecto_id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(codigo_proyecto, '')))
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
                )
                DELETE FROM proyectos_investigacion p
                USING ranked r
                WHERE p.id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(nombre_proyecto, ''))),
                                            COALESCE(anio_llamado, -1),
                                            fecha_inicio,
                                            fecha_fin
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
                )
                UPDATE investigacion_docente i
                SET proyecto_id = r.canonico
                FROM ranked r
                WHERE i.proyecto_id = r.id
                  AND r.id <> r.canonico
            """)
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           MIN(id) OVER (
                               PARTITION BY institucion_id,
                                            UPPER(TRIM(COALESCE(nombre_proyecto, ''))),
                                            COALESCE(anio_llamado, -1),
                                            fecha_inicio,
                                            fecha_fin
                           ) AS canonico
                    FROM proyectos_investigacion
                    WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
                )
                DELETE FROM proyectos_investigacion p
                USING ranked r
                WHERE p.id = r.id
                  AND r.id <> r.canonico
            """)

            # Mantiene las columnas históricas de cada asignación sincronizadas
            # con el único proyecto institucional.
            cur.execute("""
                UPDATE investigacion_docente i
                SET nombre_proyecto = p.nombre_proyecto,
                    codigo_proyecto = p.codigo_proyecto,
                    instituto_proyecto = p.instituto_proyecto,
                    anio_llamado = p.anio_llamado,
                    periodo_ejecucion = p.periodo_ejecucion
                FROM proyectos_investigacion p
                WHERE i.proyecto_id = p.id
            """)

            cur.execute("DROP INDEX IF EXISTS idx_deptit_proyectos_inv_scope")
            cur.execute("DROP INDEX IF EXISTS idx_deptit_proyectos_inv_codigo")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_institucion ON proyectos_investigacion (institucion_id)")
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_codigo_institucional
                ON proyectos_investigacion (institucion_id, UPPER(TRIM(codigo_proyecto)))
                WHERE TRIM(COALESCE(codigo_proyecto, '')) <> ''
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_sin_codigo_institucional
                ON proyectos_investigacion (
                    institucion_id,
                    UPPER(TRIM(nombre_proyecto)),
                    COALESCE(anio_llamado, -1),
                    fecha_inicio,
                    fecha_fin
                )
                WHERE TRIM(COALESCE(codigo_proyecto, '')) = ''
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_inv_fechas ON proyectos_investigacion (fecha_inicio, fecha_fin)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_inv_doc_proyecto ON investigacion_docente (proyecto_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_inv_doc_cuil_periodo ON investigacion_docente (institucion_id, cuil, periodo_id)")

            conn.commit()
            cur.close()
            conn.close()
            st.session_state["_esquema_investigacion_institucional_v4_ok"] = True
            return
        except Exception as e:
            try:
                st.warning(f"No se pudo preparar el catálogo institucional de investigación: {e}")
            except Exception:
                pass
            return

    # Compatibilidad SQLite: se conserva el catálogo dentro de la base activa.
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS proyectos_investigacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_proyecto TEXT NOT NULL,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                anio_llamado INTEGER,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                periodo_ejecucion TEXT,
                observaciones TEXT,
                estado TEXT DEFAULT 'Activo',
                fecha_carga TEXT
            )
        """)
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_inicio", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_fin", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "fecha_suspension", "TEXT")
        add_column_if_not_exists(c, "proyectos_investigacion", "motivo_suspension", "TEXT")
        add_column_if_not_exists(c, "investigacion_docente", "proyecto_id", "INTEGER")
        add_column_if_not_exists(c, "investigacion_docente", "estado_asignacion", "TEXT DEFAULT 'Activa'")
        add_column_if_not_exists(c, "investigacion_docente", "fecha_baja", "TEXT")
        add_column_if_not_exists(c, "investigacion_docente", "motivo_baja", "TEXT")
        c.execute("""
            UPDATE investigacion_docente
            SET estado_asignacion = 'Activa'
            WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
        """)
        conn.commit()

        df_legacy = pd.read_sql("""
            SELECT DISTINCT COALESCE(nombre_proyecto, '') AS nombre_proyecto,
                COALESCE(codigo_proyecto, '') AS codigo_proyecto,
                COALESCE(instituto_proyecto, '') AS instituto_proyecto,
                anio_llamado, COALESCE(periodo_ejecucion, '') AS periodo_ejecucion
            FROM investigacion_docente
            WHERE proyecto_id IS NULL
              AND TRIM(COALESCE(nombre_proyecto, '')) <> ''
        """, conn)
        for _, row in df_legacy.iterrows():
            nombre = str(row.get("nombre_proyecto") or "").strip()
            codigo = str(row.get("codigo_proyecto") or "").strip()
            instituto = str(row.get("instituto_proyecto") or "").strip()
            anio = row.get("anio_llamado")
            ejecucion = str(row.get("periodo_ejecucion") or "").strip()
            if codigo:
                c.execute("""
                    SELECT id FROM proyectos_investigacion
                    WHERE UPPER(TRIM(COALESCE(codigo_proyecto,'')))=UPPER(TRIM(?))
                    ORDER BY id LIMIT 1
                """, (codigo,))
            else:
                c.execute("""
                    SELECT id FROM proyectos_investigacion
                    WHERE UPPER(TRIM(COALESCE(nombre_proyecto,'')))=UPPER(TRIM(?))
                      AND COALESCE(anio_llamado,-1)=COALESCE(?,-1)
                      AND UPPER(TRIM(COALESCE(periodo_ejecucion,'')))=UPPER(TRIM(?))
                    ORDER BY id LIMIT 1
                """, (nombre, anio, ejecucion))
            existente = c.fetchone()
            if existente:
                proyecto_id = int(existente[0])
            else:
                fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(ejecucion, anio)
                c.execute("""
                    INSERT INTO proyectos_investigacion
                    (nombre_proyecto, codigo_proyecto, instituto_proyecto, anio_llamado,
                     fecha_inicio, fecha_fin, periodo_ejecucion, observaciones, estado, fecha_carga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '', 'Activo', ?)
                """, (nombre, codigo, instituto, anio,
                      str(fecha_inicio) if fecha_inicio else None,
                      str(fecha_fin) if fecha_fin else None,
                      ejecucion, str(date.today())))
                proyecto_id = int(c.lastrowid)
            if codigo:
                c.execute("""
                    UPDATE investigacion_docente
                    SET proyecto_id=?
                    WHERE proyecto_id IS NULL
                      AND UPPER(TRIM(COALESCE(codigo_proyecto,'')))=UPPER(TRIM(?))
                """, (proyecto_id, codigo))
            else:
                c.execute("""
                    UPDATE investigacion_docente SET proyecto_id=?
                    WHERE proyecto_id IS NULL
                      AND UPPER(TRIM(COALESCE(nombre_proyecto,'')))=UPPER(TRIM(?))
                      AND COALESCE(anio_llamado,-1)=COALESCE(?,-1)
                      AND UPPER(TRIM(COALESCE(periodo_ejecucion,'')))=UPPER(TRIM(?))
                """, (proyecto_id, nombre, anio, ejecucion))

        df_fechas = pd.read_sql("""
            SELECT id, periodo_ejecucion, anio_llamado, fecha_inicio, fecha_fin
            FROM proyectos_investigacion
        """, conn)
        for _, row in df_fechas.iterrows():
            if _fecha_proyecto(row.get("fecha_inicio")) and _fecha_proyecto(row.get("fecha_fin")):
                continue
            fecha_inicio, fecha_fin = _fechas_desde_periodo_legacy(
                row.get("periodo_ejecucion"), row.get("anio_llamado")
            )
            if fecha_inicio or fecha_fin:
                c.execute("""
                    UPDATE proyectos_investigacion
                    SET fecha_inicio=COALESCE(fecha_inicio, ?),
                        fecha_fin=COALESCE(fecha_fin, ?),
                        periodo_ejecucion=?
                    WHERE id=?
                """, (str(fecha_inicio) if fecha_inicio else None,
                      str(fecha_fin) if fecha_fin else None,
                      _texto_periodo_proyecto(fecha_inicio, fecha_fin) or row.get("periodo_ejecucion", ""),
                      int(row["id"])))
        conn.commit()
        conn.close()
        st.session_state["_esquema_investigacion_institucional_v4_ok"] = True
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar el esquema histórico de investigación: {e}")
        except Exception:
            pass


# --- entry l. 11167-11232
def copiar_investigacion_vigente_periodo(periodo_origen_id, periodo_destino_id, nombre_destino=""):
    """Renueva asignaciones solo cuando las fechas del proyecto cubren el nuevo cuatrimestre."""
    asegurar_esquema_investigacion_separado()
    if not periodo_origen_id or not periodo_destino_id:
        return 0
    conn = get_conn()
    df_dest = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin
        FROM periodos WHERE id = ? LIMIT 1
    """, conn, params=[periodo_destino_id])
    if df_dest.empty:
        conn.close()
        return 0
    periodo_destino = df_dest.iloc[0].to_dict()
    df_origen = pd.read_sql("""
        SELECT i.*, pr.fecha_inicio, pr.fecha_fin, COALESCE(pr.estado, 'Activo') AS estado_proyecto,
               COALESCE(pr.periodo_ejecucion, i.periodo_ejecucion, '') AS periodo_proyecto
        FROM investigacion_docente i
        LEFT JOIN proyectos_investigacion pr ON pr.id = i.proyecto_id
        WHERE i.periodo_id = ?
          AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'
    """, conn, params=[periodo_origen_id])
    if df_origen.empty:
        conn.close()
        return 0

    c = conn.cursor()
    copiados = 0
    for _, row in df_origen.iterrows():
        proyecto = {
            "estado": row.get("estado_proyecto", "Activo"),
            "fecha_inicio": row.get("fecha_inicio"),
            "fecha_fin": row.get("fecha_fin"),
            "periodo_ejecucion": row.get("periodo_proyecto", ""),
            "anio_llamado": row.get("anio_llamado"),
        }
        if not proyecto_vigente_en_periodo(proyecto, periodo_destino):
            continue
        c.execute("""
            SELECT id FROM investigacion_docente
            WHERE periodo_id = ? AND cuil = ? AND proyecto_id = ?
              AND UPPER(TRIM(COALESCE(rol,''))) = UPPER(TRIM(?))
              AND COALESCE(estado_asignacion, 'Activa') = 'Activa'
            LIMIT 1
        """, (periodo_destino_id, row.get("cuil"), row.get("proyecto_id"), row.get("rol", "")))
        if c.fetchone():
            continue
        c.execute("""
            INSERT INTO investigacion_docente
            (proyecto_id, periodo_id, cuil, nombre_proyecto, rol, anio_llamado, periodo_ejecucion,
             horas_asignadas, observaciones, fecha_carga, codigo_proyecto, instituto_proyecto,
             estado_asignacion, fecha_baja, motivo_baja)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activa', NULL, NULL)
        """, (
            row.get("proyecto_id"), periodo_destino_id, row.get("cuil"),
            row.get("nombre_proyecto", ""), row.get("rol", ""),
            int(row.get("anio_llamado")) if pd.notna(row.get("anio_llamado")) and str(row.get("anio_llamado")).strip() else None,
            row.get("periodo_proyecto", ""), float(row.get("horas_asignadas") or 0),
            (str(row.get("observaciones") or "").strip() + " | " if str(row.get("observaciones") or "").strip() else "")
            + f"Renovado automáticamente en {nombre_destino} porque el proyecto continúa vigente.",
            str(date.today()), row.get("codigo_proyecto", ""), row.get("instituto_proyecto", "")
        ))
        copiados += 1
    conn.commit()
    conn.close()
    return copiados


# --- entry l. 11549-11552
def contar_datos_asociados_periodo(periodo_id):
    'Cuenta datos vinculados a un período para decidir si puede eliminarse.\n\n    Criterio: Eliminar período queda reservado para períodos vacíos creados por error.\n    Si hay designaciones, movimientos de gestión, comisiones, inscriptos, investigación,\n    extensión o disposiciones, no se permite borrar. Los movimientos simples de apertura\n    no bloquean la eliminación porque se generan automáticamente al crear el período.\n    '
    from analisis.motor.ref.extracted_batch03.readonly_queries import contar_datos_asociados_periodo as _b03_core_contar_datos_asociados_periodo
    return _b03_core_contar_datos_asociados_periodo(periodo_id, get_conn=get_conn, pd=pd)


# --- entry l. 11553-11555
def periodo_puede_eliminarse(conteos):
    from integraciones.ciclo_periodos.motor.ref.domain.periodos import periodo_puede_eliminarse as _b05_core_periodo_puede_eliminarse
    return _b05_core_periodo_puede_eliminarse(conteos)


# --- entry l. 11813-11815
def _texto_designacion_para_match(row):
    from analisis.motor.ref.domain.designaciones import _texto_designacion_para_match as _b05_core__texto_designacion_para_match
    return _b05_core__texto_designacion_para_match(row)


# --- entry l. 11818-11883
def _finalizaciones_automaticas_reactivables(periodo_id, periodo_cierre_nombre=None):
    """Detecta designaciones que fueron finalizadas solo por cierre automático.

    Se usa cuando se elimina el período nuevo y se vuelve a abrir el anterior.
    En ese caso, las finalizaciones automáticas del período reabierto ya no
    corresponden: los docentes deben volver a quedar Activos en ese período.
    """
    conn = get_conn()
    try:
        df_cierres = pd.read_sql("""
            SELECT id, cuil, nombre, detalle, observaciones
            FROM movimientos
            WHERE periodo_id = ?
              AND tipo_movimiento = 'Finalización automática por cierre de período'
        """, conn, params=[periodo_id])

        if df_cierres.empty:
            return {"ids_reactivar": set(), "movimientos_ids": set(), "movimientos_total": 0}

        # Si sabemos qué período se eliminó, priorizamos los movimientos generados
        # al crear ese período. Si no hay coincidencia, usamos todos los cierres
        # automáticos del período abierto como reparación segura.
        if periodo_cierre_nombre:
            nombre = str(periodo_cierre_nombre or "").strip()
            mask = (
                df_cierres["observaciones"].fillna("").astype(str).str.contains(nombre, case=False, regex=False)
                | df_cierres["detalle"].fillna("").astype(str).str.contains(nombre, case=False, regex=False)
            )
            if mask.any():
                df_cierres = df_cierres[mask].copy()

        df_finalizadas = pd.read_sql("""
            SELECT id, cuil, cargo, dedicacion, horas, tipo_designacion, estado
            FROM designaciones
            WHERE periodo_id = ?
              AND estado = 'Finalizada'
        """, conn, params=[periodo_id])

        ids_reactivar = set()
        for _, mov in df_cierres.iterrows():
            cuil = str(mov.get("cuil", "") or "").strip()
            detalle = str(mov.get("detalle", "") or "")
            posibles = df_finalizadas[df_finalizadas["cuil"].fillna("").astype(str).str.strip() == cuil].copy()
            if posibles.empty:
                continue

            encontrados = []
            for _, des in posibles.iterrows():
                texto = _texto_designacion_para_match(des)
                if texto and texto in detalle:
                    encontrados.append(int(des["id"]))

            if encontrados:
                ids_reactivar.update(encontrados)
            elif len(posibles) == 1:
                # Fallback conservador: si solo hay una finalizada para ese CUIL,
                # es muy probable que sea la que cerró automáticamente el sistema.
                ids_reactivar.add(int(posibles.iloc[0]["id"]))

        return {
            "ids_reactivar": ids_reactivar,
            "movimientos_ids": set(int(x) for x in df_cierres["id"].dropna().tolist()),
            "movimientos_total": int(len(df_cierres)),
        }
    finally:
        conn.close()


# --- entry l. 11886-11936
def reactivar_finalizaciones_automaticas_periodo(periodo_id, periodo_cierre_nombre=None, observaciones=""):
    """Revierte las finalizaciones automáticas de cierre en un período que queda abierto.

    No toca bajas reales ni finalizaciones manuales. Solo reactiva designaciones
    que tienen movimiento de tipo 'Finalización automática por cierre de período'.
    También elimina esos movimientos automáticos para que el resumen docente no
    siga mostrando una baja/finalización que ya fue revertida.
    """
    datos = _finalizaciones_automaticas_reactivables(periodo_id, periodo_cierre_nombre)
    ids_reactivar = set(datos.get("ids_reactivar") or set())
    movimientos_ids = set(datos.get("movimientos_ids") or set())

    if not ids_reactivar and not movimientos_ids:
        return {"designaciones_reactivadas": 0, "movimientos_cierre_eliminados": 0}

    conn = get_conn()
    try:
        c = conn.cursor()
        if ids_reactivar:
            placeholders = ",".join(["?"] * len(ids_reactivar))
            c.execute(
                f"UPDATE designaciones SET estado = 'Activa' WHERE id IN ({placeholders})",
                list(ids_reactivar)
            )

        movimientos_eliminados = 0
        if movimientos_ids:
            placeholders_mov = ",".join(["?"] * len(movimientos_ids))
            c.execute(
                f"DELETE FROM movimientos WHERE id IN ({placeholders_mov})",
                list(movimientos_ids)
            )
            try:
                movimientos_eliminados = int(c.rowcount or 0)
            except Exception:
                movimientos_eliminados = len(movimientos_ids)

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return {
        "designaciones_reactivadas": len(ids_reactivar),
        "movimientos_cierre_eliminados": movimientos_eliminados,
    }


# --- entry l. 11939-11944
def diagnosticar_finalizaciones_automaticas_periodo(periodo_id):
    datos = _finalizaciones_automaticas_reactivables(periodo_id, None)
    return {
        "designaciones_reactivables": len(set(datos.get("ids_reactivar") or set())),
        "movimientos_cierre": len(set(datos.get("movimientos_ids") or set())),
    }


# --- entry l. 11947-11996
def diagnosticar_reversion_ultimo_cierre(periodo_nuevo_id=None):
    """Devuelve un diagnóstico previo para revertir un cierre de período.

    La reversión pensada es: borrar el último período creado por error, borrar sus
    renovaciones automáticas y reabrir el período anterior reactivando solo las
    designaciones que fueron finalizadas automáticamente por el cierre.
    """
    periodo_nuevo = get_periodo_abierto() if periodo_nuevo_id is None else None
    if periodo_nuevo_id is not None:
        conn = get_conn()
        df = pd.read_sql("""
            SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
            FROM periodos
            WHERE id = ?
            LIMIT 1
        """, conn, params=[periodo_nuevo_id])
        conn.close()
        if not df.empty:
            periodo_nuevo = df.iloc[0].to_dict()

    if periodo_nuevo is None:
        return {"ok": False, "mensaje": "No hay período seleccionado o abierto.", "periodo_nuevo": None, "periodo_anterior": None}

    ultimo = get_ultimo_periodo()
    if ultimo is None or int(ultimo["id"]) != int(periodo_nuevo["id"]):
        return {"ok": False, "mensaje": "Solo se puede revertir el último período creado.", "periodo_nuevo": periodo_nuevo, "periodo_anterior": None}

    periodo_anterior = get_periodo_anterior_cronologico(periodo_nuevo["id"])
    if periodo_anterior is None:
        return {"ok": False, "mensaje": "No hay período anterior para restaurar.", "periodo_nuevo": periodo_nuevo, "periodo_anterior": None}

    conn = get_conn()
    conteos = pd.read_sql("""
        SELECT
            (SELECT COUNT(*) FROM designaciones WHERE periodo_id = ?) AS designaciones_nuevo,
            (SELECT COUNT(*) FROM movimientos WHERE periodo_id = ?) AS movimientos_nuevo,
            (SELECT COUNT(*) FROM movimientos WHERE periodo_id = ? AND tipo_movimiento = 'Renovación automática de designación') AS renovaciones_nuevo,
            (SELECT COUNT(*) FROM movimientos WHERE periodo_id = ? AND tipo_movimiento = 'Finalización automática por cierre de período') AS cierres_anterior,
            (SELECT COUNT(*) FROM designaciones WHERE periodo_id = ? AND estado = 'Finalizada') AS finalizadas_anterior,
            (SELECT COUNT(*) FROM designaciones WHERE periodo_id = ? AND estado = 'Activa') AS activas_anterior
    """, conn, params=[periodo_nuevo["id"], periodo_nuevo["id"], periodo_nuevo["id"], periodo_anterior["id"], periodo_anterior["id"], periodo_anterior["id"]]).iloc[0].to_dict()
    conn.close()

    return {
        "ok": True,
        "mensaje": "Se puede revertir el último cierre.",
        "periodo_nuevo": periodo_nuevo,
        "periodo_anterior": periodo_anterior,
        **{k: int(v or 0) for k, v in conteos.items()}
    }


# --- entry l. 11999-12094
def revertir_ultimo_cierre_periodo(periodo_nuevo_id=None, observaciones=""):
    """Revierte el último cierre de período de forma controlada.

    Hace exactamente esto:
    - elimina el último período creado;
    - elimina sus designaciones y movimientos;
    - reabre el período anterior;
    - reactiva solo las designaciones del período anterior que tengan movimiento
      'Finalización automática por cierre de período'.

    No toca otros departamentos porque cada departamento usa su propia base SQLite.
    """
    diag = diagnosticar_reversion_ultimo_cierre(periodo_nuevo_id)
    if not diag.get("ok"):
        raise ValueError(diag.get("mensaje", "No se puede revertir el cierre."))

    periodo_nuevo = diag["periodo_nuevo"]
    periodo_anterior = diag["periodo_anterior"]
    conn = get_conn()
    try:
        df_cierres = pd.read_sql("""
            SELECT id, cuil, nombre, detalle
            FROM movimientos
            WHERE periodo_id = ?
              AND tipo_movimiento = 'Finalización automática por cierre de período'
        """, conn, params=[periodo_anterior["id"]])

        df_finalizadas = pd.read_sql("""
            SELECT id, cuil, cargo, dedicacion, horas, tipo_designacion, estado
            FROM designaciones
            WHERE periodo_id = ?
              AND estado = 'Finalizada'
        """, conn, params=[periodo_anterior["id"]])

        ids_reactivar = set()
        for _, mov in df_cierres.iterrows():
            cuil = str(mov.get("cuil", "") or "").strip()
            detalle = str(mov.get("detalle", "") or "")
            posibles = df_finalizadas[df_finalizadas["cuil"].fillna("").astype(str).str.strip() == cuil].copy()
            if posibles.empty:
                continue
            encontrados = []
            for _, des in posibles.iterrows():
                texto = _texto_designacion_para_match(des)
                if texto and texto in detalle:
                    encontrados.append(int(des["id"]))
            if encontrados:
                ids_reactivar.update(encontrados)
            elif len(posibles) == 1:
                # Fallback conservador: si solo hay una finalizada para ese CUIL, es la del movimiento.
                ids_reactivar.add(int(posibles.iloc[0]["id"]))

        c = conn.cursor()
        if ids_reactivar:
            placeholders = ",".join(["?"] * len(ids_reactivar))
            c.execute(f"UPDATE designaciones SET estado = 'Activa' WHERE id IN ({placeholders})", list(ids_reactivar))

        # Al reabrir el período anterior, los movimientos automáticos de cierre
        # dejan de corresponder y no deben aparecer en el resumen docente.
        cierres_ids = [int(x) for x in df_cierres["id"].dropna().tolist()] if not df_cierres.empty else []
        if cierres_ids:
            placeholders_cierres = ",".join(["?"] * len(cierres_ids))
            c.execute(f"DELETE FROM movimientos WHERE id IN ({placeholders_cierres})", cierres_ids)

        # Borra únicamente el período nuevo que se revierte y sus registros propios.
        c.execute("DELETE FROM designaciones WHERE periodo_id = ?", (periodo_nuevo["id"],))
        c.execute("DELETE FROM movimientos WHERE periodo_id = ?", (periodo_nuevo["id"],))
        try:
            c.execute("DELETE FROM estado_consulta_designacion WHERE periodo_id = ?", (periodo_nuevo["id"],))
        except Exception:
            pass
        c.execute("DELETE FROM periodos WHERE id = ?", (periodo_nuevo["id"],))

        # Deja abierto el período anterior.
        c.execute("UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto'")
        c.execute("UPDATE periodos SET estado = 'Abierto' WHERE id = ?", (periodo_anterior["id"],))
        conn.commit()
    finally:
        conn.close()

    registrar_movimiento(
        "Reversión de cierre de período",
        "",
        "",
        f"Se revirtió el cierre que había creado {periodo_nuevo['nombre']}. Se eliminó ese período y se reabrió {periodo_anterior['nombre']}. Designaciones reactivadas: {len(ids_reactivar)}.",
        observaciones,
        periodo_anterior["id"]
    )

    return {
        "periodo_eliminado": periodo_nuevo["nombre"],
        "periodo_reabierto": periodo_anterior["nombre"],
        "designaciones_reactivadas": len(ids_reactivar),
        "designaciones_eliminadas_periodo_nuevo": diag.get("designaciones_nuevo", 0),
        "movimientos_eliminados_periodo_nuevo": diag.get("movimientos_nuevo", 0),
    }


# --- entry l. 12105-12233
def asegurar_esquema_extension_separado():
    """Crea el catálogo institucional de extensión y sus asignaciones departamentales."""
    if st.session_state.get("_esquema_extension_institucional_v2_ok"):
        return
    if USE_POSTGRESQL:
        try:
            conn = _pg_raw_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proyectos_extension (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    nombre_proyecto TEXT NOT NULL,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    anio_llamado INTEGER,
                    fecha_inicio DATE,
                    fecha_fin DATE,
                    periodo_ejecucion TEXT,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Activo',
                    fecha_carga TEXT,
                    fecha_suspension DATE,
                    motivo_suspension TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS extension_docente (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT,
                    proyecto_id BIGINT,
                    periodo_id BIGINT,
                    cuil TEXT,
                    nombre_proyecto TEXT,
                    rol TEXT,
                    anio_llamado INTEGER,
                    periodo_ejecucion TEXT,
                    horas_asignadas REAL,
                    observaciones TEXT,
                    fecha_carga TEXT,
                    codigo_proyecto TEXT,
                    instituto_proyecto TEXT,
                    estado_asignacion TEXT DEFAULT 'Activa',
                    fecha_baja TEXT,
                    motivo_baja TEXT
                )
            """)
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_inicio DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_fin DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS fecha_suspension DATE")
            cur.execute("ALTER TABLE proyectos_extension ADD COLUMN IF NOT EXISTS motivo_suspension TEXT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS institucion_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS departamento_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS proyecto_id BIGINT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS estado_asignacion TEXT DEFAULT 'Activa'")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS fecha_baja TEXT")
            cur.execute("ALTER TABLE extension_docente ADD COLUMN IF NOT EXISTS motivo_baja TEXT")
            cur.execute("""
                UPDATE extension_docente
                SET estado_asignacion = 'Activa'
                WHERE estado_asignacion IS NULL OR TRIM(estado_asignacion) = ''
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_institucion ON proyectos_extension (institucion_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_codigo ON proyectos_extension (institucion_id, UPPER(TRIM(codigo_proyecto)))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_proyectos_ext_fechas ON proyectos_extension (fecha_inicio, fecha_fin)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_ext_doc_proyecto ON extension_docente (proyecto_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deptit_ext_doc_cuil_periodo ON extension_docente (institucion_id, cuil, periodo_id)")
            conn.commit()
            cur.close(); conn.close()
            st.session_state["_esquema_extension_institucional_v2_ok"] = True
            return
        except Exception as e:
            try:
                st.warning(f"No se pudo preparar el catálogo institucional de extensión: {e}")
            except Exception:
                pass
            return

    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS proyectos_extension (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_proyecto TEXT NOT NULL,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                anio_llamado INTEGER,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                periodo_ejecucion TEXT,
                observaciones TEXT,
                estado TEXT DEFAULT 'Activo',
                fecha_carga TEXT
            )
        """)
        add_column_if_not_exists(c, "proyectos_extension", "fecha_suspension", "TEXT")
        add_column_if_not_exists(c, "proyectos_extension", "motivo_suspension", "TEXT")
        c.execute("""
            CREATE TABLE IF NOT EXISTS extension_docente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto_id INTEGER,
                periodo_id INTEGER,
                cuil TEXT,
                nombre_proyecto TEXT,
                rol TEXT,
                anio_llamado INTEGER,
                periodo_ejecucion TEXT,
                horas_asignadas REAL,
                observaciones TEXT,
                fecha_carga TEXT,
                codigo_proyecto TEXT,
                instituto_proyecto TEXT,
                estado_asignacion TEXT DEFAULT 'Activa',
                fecha_baja TEXT,
                motivo_baja TEXT
            )
        """)
        conn.commit(); conn.close()
        st.session_state["_esquema_extension_institucional_v2_ok"] = True
    except Exception as e:
        try:
            st.warning(f"No se pudo preparar el esquema de extensión: {e}")
        except Exception:
            pass


# --- entry l. 16533-16535
def limpiar_texto_tabla(valor):
    from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla as _b04_core_limpiar_texto_tabla
    return _b04_core_limpiar_texto_tabla(valor)


# --- entry l. 16538-16540
def limpiar_cuil(valor):
    from analisis.motor.ref.extracted_batch04.identidad import limpiar_cuil as _b04_core_limpiar_cuil
    return _b04_core_limpiar_cuil(valor)


# --- entry l. 18020-18031
def get_periodo_por_nombre(nombre):
    conn = get_conn()
    df = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        WHERE nombre = ?
        LIMIT 1
    """, conn, params=[str(nombre).strip()])
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


# --- entry l. 22240-22305
def copiar_extension_vigente_periodo(periodo_origen_id, periodo_destino_id, nombre_destino=""):
    """Renueva asignaciones solo cuando las fechas del proyecto cubren el nuevo cuatrimestre."""
    asegurar_esquema_extension_separado()
    if not periodo_origen_id or not periodo_destino_id:
        return 0
    conn = get_conn()
    df_dest = pd.read_sql("""
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin
        FROM periodos WHERE id = ? LIMIT 1
    """, conn, params=[periodo_destino_id])
    if df_dest.empty:
        conn.close()
        return 0
    periodo_destino = df_dest.iloc[0].to_dict()
    df_origen = pd.read_sql("""
        SELECT i.*, pr.fecha_inicio, pr.fecha_fin, COALESCE(pr.estado, 'Activo') AS estado_proyecto,
               COALESCE(pr.periodo_ejecucion, i.periodo_ejecucion, '') AS periodo_proyecto
        FROM extension_docente i
        LEFT JOIN proyectos_extension pr ON pr.id = i.proyecto_id
        WHERE i.periodo_id = ?
          AND COALESCE(i.estado_asignacion, 'Activa') = 'Activa'
    """, conn, params=[periodo_origen_id])
    if df_origen.empty:
        conn.close()
        return 0

    c = conn.cursor()
    copiados = 0
    for _, row in df_origen.iterrows():
        proyecto = {
            "estado": row.get("estado_proyecto", "Activo"),
            "fecha_inicio": row.get("fecha_inicio"),
            "fecha_fin": row.get("fecha_fin"),
            "periodo_ejecucion": row.get("periodo_proyecto", ""),
            "anio_llamado": row.get("anio_llamado"),
        }
        if not proyecto_vigente_en_periodo(proyecto, periodo_destino):
            continue
        c.execute("""
            SELECT id FROM extension_docente
            WHERE periodo_id = ? AND cuil = ? AND proyecto_id = ?
              AND UPPER(TRIM(COALESCE(rol,''))) = UPPER(TRIM(?))
              AND COALESCE(estado_asignacion, 'Activa') = 'Activa'
            LIMIT 1
        """, (periodo_destino_id, row.get("cuil"), row.get("proyecto_id"), row.get("rol", "")))
        if c.fetchone():
            continue
        c.execute("""
            INSERT INTO extension_docente
            (proyecto_id, periodo_id, cuil, nombre_proyecto, rol, anio_llamado, periodo_ejecucion,
             horas_asignadas, observaciones, fecha_carga, codigo_proyecto, instituto_proyecto,
             estado_asignacion, fecha_baja, motivo_baja)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activa', NULL, NULL)
        """, (
            row.get("proyecto_id"), periodo_destino_id, row.get("cuil"),
            row.get("nombre_proyecto", ""), row.get("rol", ""),
            int(row.get("anio_llamado")) if pd.notna(row.get("anio_llamado")) and str(row.get("anio_llamado")).strip() else None,
            row.get("periodo_proyecto", ""), float(row.get("horas_asignadas") or 0),
            (str(row.get("observaciones") or "").strip() + " | " if str(row.get("observaciones") or "").strip() else "")
            + f"Renovado automáticamente en {nombre_destino} porque el proyecto continúa vigente.",
            str(date.today()), row.get("codigo_proyecto", ""), row.get("instituto_proyecto", "")
        ))
        copiados += 1
    conn.commit()
    conn.close()
    return copiados


# --- entry l. 24674-24677
def get_periodo_anterior_cronologico(periodo_id):
    '\n    Devuelve el período inmediatamente anterior al seleccionado.\n    Sirve para inferir bajas docentes aunque no exista un movimiento manual cargado.\n    '
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_periodo_anterior_cronologico as _b03_core_get_periodo_anterior_cronologico
    return _b03_core_get_periodo_anterior_cronologico(periodo_id, get_conn=get_conn, pd=pd)


# --- entry l. 27137-27139
def _hora_numero(valor):
    from analisis.motor.ref.extracted_batch04.numeros import _hora_numero as _b04_core__hora_numero
    return _b04_core__hora_numero(valor)


# --- entry l. 29279-29281
def _normalizar_cargo_para_jerarquia(valor):
    from analisis.motor.ref.domain.designaciones import _normalizar_cargo_para_jerarquia as _b05_core__normalizar_cargo_para_jerarquia
    return _b05_core__normalizar_cargo_para_jerarquia(valor)


# --- entry l. 29284-29287
def _cargo_mas_alto(cargos):
    """Selecciona el cargo de mayor jerarquía; conserva un valor desconocido solo como último recurso."""
    from analisis.motor.ref.domain.catalog_unlocked.designaciones import _cargo_mas_alto as _b08_core__cargo_mas_alto
    return _b08_core__cargo_mas_alto(cargos)


# --- entry l. 29290-29292
def _extraer_departamento_origen_prestado(observaciones):
    from analisis.motor.ref.domain.designaciones import _extraer_departamento_origen_prestado as _b05_core__extraer_departamento_origen_prestado
    return _b05_core__extraer_departamento_origen_prestado(observaciones)


# --- entry l. 29295-29316
def _buscar_departamento_id_por_nombre(inst_id, nombre_departamento):
    if not USE_POSTGRESQL or not inst_id or not nombre_departamento:
        return None
    try:
        df = _pg_read_dataframe(
            "SELECT id, nombre FROM departamentos WHERE institucion_id = %s ORDER BY id",
            [int(inst_id)],
        )
        objetivo = normalizar_clave(nombre_departamento)
        if df.empty or not objetivo:
            return None
        exactos = df[df["nombre"].fillna("").astype(str).apply(normalizar_clave) == objetivo]
        if not exactos.empty:
            return int(exactos.iloc[0]["id"])
        parciales = df[df["nombre"].fillna("").astype(str).apply(
            lambda x: objetivo in normalizar_clave(x) or normalizar_clave(x) in objetivo
        )]
        if len(parciales) == 1:
            return int(parciales.iloc[0]["id"])
    except Exception:
        pass
    return None


# --- entry l. 29319-29460
def obtener_cargo_prioritario_docente_periodo(cuil, periodo_id, departamento_contexto_id=None):
    """Obtiene el cargo que debe usarse por defecto en una comisión.

    - Docente propio: designaciones activas del departamento de la comisión.
    - Docente prestado: designaciones activas de su departamento de origen.
    - Si hay varios cargos en ese departamento, devuelve el de mayor jerarquía.
    """
    cuil = limpiar_cuil(cuil)
    if not cuil or not periodo_id:
        return {"cargo": "", "departamento": "", "motivo": "Falta CUIL o período."}

    if not USE_POSTGRESQL:
        try:
            conn = get_conn()
            df = pd.read_sql(
                """
                SELECT cargo
                FROM designaciones
                WHERE cuil = ? AND periodo_id = ? AND estado = 'Activa'
                  AND COALESCE(TRIM(cargo), '') <> ''
                """,
                conn,
                params=[cuil, int(periodo_id)],
            )
            conn.close()
            cargo = _cargo_mas_alto(df["cargo"].tolist() if not df.empty else [])
            return {
                "cargo": cargo,
                "departamento": _departamento_actual_operativo_nombre() if cargo else "",
                "motivo": "Cargo activo del departamento actual." if cargo else "No se encontró designación activa.",
            }
        except Exception as e:
            return {"cargo": "", "departamento": "", "motivo": str(e)}

    try:
        inst_id = _pg_current_inst_id()
        dep_contexto = int(departamento_contexto_id or _pg_current_dep_id())
        if inst_id is None or dep_contexto is None:
            return {"cargo": "", "departamento": "", "motivo": "No se pudo determinar institución/departamento."}

        df_doc = _pg_read_dataframe(
            """
            SELECT COALESCE(tipo_docente, 'Propio') AS tipo_docente,
                   COALESCE(observaciones, '') AS observaciones
            FROM docentes
            WHERE institucion_id = %s AND departamento_id = %s AND cuil = %s
            ORDER BY id
            LIMIT 1
            """,
            [int(inst_id), int(dep_contexto), cuil],
        )
        tipo = str(df_doc.iloc[0].get("tipo_docente") or "Propio") if not df_doc.empty else "Propio"
        obs = str(df_doc.iloc[0].get("observaciones") or "") if not df_doc.empty else ""
        es_prestado = normalizar_clave(tipo) == "PRESTADO"

        dep_designacion = dep_contexto
        dep_origen_nombre = ""
        if es_prestado:
            dep_origen_nombre = _extraer_departamento_origen_prestado(obs)
            dep_origen_id = _buscar_departamento_id_por_nombre(inst_id, dep_origen_nombre)
            dep_designacion = dep_origen_id

        params = [int(periodo_id), cuil, int(inst_id)]
        filtro_dep = ""
        if dep_designacion is not None:
            filtro_dep = " AND d.departamento_id = %s"
            params.append(int(dep_designacion))
        elif es_prestado:
            filtro_dep = " AND COALESCE(d.departamento_id, -1) <> %s"
            params.append(int(dep_contexto))

        df_cargos = _pg_read_dataframe(
            f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id = %s
                LIMIT 1
            )
            SELECT d.cargo, d.departamento_id, COALESCE(dep.nombre, '') AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            WHERE d.cuil = %s
              AND d.institucion_id = %s
              AND d.estado = 'Activa'
              AND COALESCE(TRIM(d.cargo), '') <> ''
              {filtro_dep}
            """,
            params,
        )

        # Respaldo para prestados antiguos cuyo departamento de origen no quedó
        # escrito de forma reconocible: toma sus designaciones fuera del receptor.
        if df_cargos.empty and es_prestado and dep_designacion is not None:
            df_cargos = _pg_read_dataframe(
                f"""
                WITH pr AS (
                    SELECT id, institucion_id, nombre, anio, semestre
                    FROM periodos WHERE id = %s LIMIT 1
                )
                SELECT d.cargo, d.departamento_id, COALESCE(dep.nombre, '') AS departamento
                FROM designaciones d
                JOIN periodos p ON p.id = d.periodo_id
                JOIN pr ON {_condicion_periodo_equivalente_sql('p', 'pr')}
                LEFT JOIN departamentos dep ON dep.id = d.departamento_id
                WHERE d.cuil = %s
                  AND d.institucion_id = %s
                  AND d.estado = 'Activa'
                  AND COALESCE(TRIM(d.cargo), '') <> ''
                  AND COALESCE(d.departamento_id, -1) <> %s
                """,
                [int(periodo_id), cuil, int(inst_id), int(dep_contexto)],
            )

        if df_cargos.empty:
            origen_txt = f" en {dep_origen_nombre}" if dep_origen_nombre else ""
            return {
                "cargo": "",
                "departamento": dep_origen_nombre,
                "motivo": f"No se encontró una designación activa{origen_txt} para el período de la comisión.",
            }

        # Si por un dato heredado aparecen designaciones de más de un departamento,
        # primero selecciona el departamento esperado; en el respaldo, el cargo más
        # alto disponible y conserva el departamento de esa fila.
        df_cargos = df_cargos.copy()
        df_cargos["cargo_canonico"] = df_cargos["cargo"].apply(_normalizar_cargo_para_jerarquia)
        prioridad = {cargo: i for i, cargo in enumerate(ORDEN_JERARQUICO_CARGOS_COMISION)}
        df_cargos["_prioridad"] = df_cargos["cargo_canonico"].map(prioridad).fillna(999)
        df_cargos = df_cargos.sort_values(["_prioridad", "departamento", "cargo_canonico"])
        elegido = df_cargos.iloc[0]
        cargo = str(elegido.get("cargo_canonico") or elegido.get("cargo") or "").strip()
        departamento = str(elegido.get("departamento") or dep_origen_nombre or "").strip()
        return {
            "cargo": cargo,
            "departamento": departamento,
            "motivo": f"Cargo activo de {departamento}." if departamento else "Cargo activo detectado.",
        }
    except Exception as e:
        return {"cargo": "", "departamento": "", "motivo": f"No se pudo determinar el cargo: {e}"}


# --- entry l. 29724-29751
def sincronizar_cargos_asignaciones_docente_periodo(cuil, periodo_id):
    """Actualiza el cargo visible en comisiones al cambiar la designación del docente."""
    cuil = limpiar_cuil(cuil)
    if not cuil or periodo_id is None:
        return 0
    dato = obtener_cargo_prioritario_docente_periodo(
        cuil, int(periodo_id), _pg_current_dep_id() if USE_POSTGRESQL else None
    )
    cargo = limpiar_texto_tabla(dato.get("cargo", ""))
    if not cargo:
        return 0
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE asignaciones_docentes_comision
        SET rol = ?
        WHERE cuil = ?
          AND COALESCE(estado, 'Activa') = 'Activa'
          AND comision_id IN (
              SELECT id FROM comisiones WHERE periodo_id = ?
          )
    """, (cargo, cuil, int(periodo_id)))
    total = max(c.rowcount or 0, 0)
    conn.commit()
    conn.close()
    if total:
        limpiar_cache_comisiones_operativas()
    return total


# --- entry l. 32479-32497
def get_designaciones(periodo_id=None):
    # v212: al consultar un período, reparar primero las bajas históricas que ya
    # existen como movimiento real pero dejaron vacía fecha_finalizacion_efectiva.
    # Se usa globals() porque la rutina v212 se define más abajo en el archivo.
    if periodo_id is not None:
        try:
            _repair_v212 = globals().get("reconciliar_fechas_finalizacion_desde_movimientos_v212")
            if callable(_repair_v212):
                _repair_v212(int(periodo_id))
        except Exception:
            pass
    conn=get_conn();f="";p=[]
    if periodo_id is not None:f="WHERE d.periodo_id=?";p=[int(periodo_id)]
    df=pd.read_sql(f"""SELECT d.id,d.periodo_id,per.nombre AS periodo,CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido||', '||doc.nombres WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE '' END AS nombre_completo,
        d.cuil,d.cargo,d.dedicacion,d.horas,d.tipo_designacion,COALESCE(d.numero_resolucion,'') AS numero_resolucion,d.ad_honorem,d.fecha_desde,d.fecha_hasta,
        COALESCE(NULLIF(d.fecha_hasta_prevista,''),d.fecha_hasta) AS fecha_hasta_prevista,d.fecha_finalizacion_efectiva,d.fecha_registro_finalizacion,d.motivo_finalizacion,
        CASE WHEN per.estado='Cerrado' AND d.estado='Activa' THEN 'Finalizada' ELSE d.estado END AS estado,d.observaciones
        FROM designaciones d LEFT JOIN docentes doc ON d.cuil=doc.cuil LEFT JOIN periodos per ON d.periodo_id=per.id {f}
        ORDER BY per.anio DESC,per.semestre DESC,doc.apellido,doc.nombres""",conn,params=p);conn.close();return df


# --- entry l. 32557-32713
def _finalizar_comisiones_si_sin_designacion_docente_v214(cuil, periodo_id, fecha_efectiva, designacion_finalizada_id=None):
    """Finaliza asignaciones a comisión solo si ya no queda cobertura docente vigente.

    Regla v214:
    - la baja de una designación NO saca al docente de las comisiones si conserva
      otra designación docente vigente en ese mismo período y fecha;
    - si ya no queda ninguna, finaliza todas sus asignaciones activas a comisiones
      del período con la misma fecha efectiva;
    - cada baja de comisión deja su movimiento físico, de modo idempotente.
    """
    cuil_txt = str(cuil or "").strip()
    try:
        pid = int(periodo_id)
    except Exception:
        return 0
    fe = safe_date(fecha_efectiva, None)
    if not cuil_txt or fe is None:
        return 0

    conn = get_conn()
    asignaciones_a_finalizar = []
    nombre_docente = cuil_txt
    try:
        # Primero comprobar si todavía existe otra designación DOCENTE realmente
        # vigente en la fecha de la baja. Las funciones no docentes no sostienen
        # una asignación a comisión.
        df_des = pd.read_sql("""
            SELECT id, estado, fecha_desde,
                   COALESCE(NULLIF(fecha_hasta_prevista,''), fecha_hasta) AS fecha_hasta_limite,
                   fecha_finalizacion_efectiva, COALESCE(funcion_no_docente,0) AS funcion_no_docente
            FROM designaciones
            WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
              AND COALESCE(estado,'Activa')='Activa'
            ORDER BY id
        """, conn, params=[pid, cuil_txt])

        queda_docente_vigente = False
        for _, d in df_des.iterrows():
            try:
                did = int(d.get("id"))
            except Exception:
                did = None
            if designacion_finalizada_id is not None and did == int(designacion_finalizada_id):
                continue
            if _es_funcion_no_docente_v162(d.get("funcion_no_docente")):
                continue
            fd = safe_date(d.get("fecha_desde"), None)
            fh = safe_date(d.get("fecha_hasta_limite"), None)
            fef = safe_date(d.get("fecha_finalizacion_efectiva"), None)
            if fd is not None and fe < fd:
                continue
            if fh is not None and fe > fh:
                continue
            if fef is not None and fe >= fef:
                continue
            queda_docente_vigente = True
            break

        if queda_docente_vigente:
            return 0

        df_asig = pd.read_sql("""
            SELECT a.id, a.comision_id, a.cuil, a.rol, a.horas_asignadas,
                   a.observaciones, c.nombre_comision
            FROM asignaciones_docentes_comision a
            JOIN comisiones c ON c.id=a.comision_id
            WHERE c.periodo_id=?
              AND TRIM(COALESCE(a.cuil,''))=TRIM(?)
              AND COALESCE(a.estado,'Activa')='Activa'
            ORDER BY a.id
        """, conn, params=[pid, cuil_txt])
        if df_asig.empty:
            return 0

        try:
            df_nom = pd.read_sql(
                "SELECT apellido, nombres, nombre FROM docentes WHERE TRIM(COALESCE(cuil,''))=TRIM(?) LIMIT 1",
                conn, params=[cuil_txt]
            )
            if not df_nom.empty:
                nr = df_nom.iloc[0]
                nombre_docente = nombre_completo(str(nr.get("apellido") or ""), str(nr.get("nombres") or "")) or str(nr.get("nombre") or "").strip() or cuil_txt
        except Exception:
            pass

        cur = conn.cursor()
        for _, a in df_asig.iterrows():
            aid = int(a.get("id"))
            cid = int(a.get("comision_id"))
            obs_actual = limpiar_texto_tabla(a.get("observaciones", ""))
            nota = (
                f"Baja automática de comisión por quedar sin designaciones docentes vigentes. "
                f"Fecha efectiva: {fe.isoformat()}. Comisión ID {cid}."
            )
            obs_nueva = (obs_actual.rstrip(". ") + ". " if obs_actual else "") + nota
            cur.execute(
                "UPDATE asignaciones_docentes_comision SET estado='Finalizada', observaciones=? WHERE id=? AND COALESCE(estado,'Activa')='Activa'",
                (obs_nueva, aid)
            )
            if int(cur.rowcount or 0) > 0:
                asignaciones_a_finalizar.append({
                    "id": aid,
                    "comision_id": cid,
                    "nombre_comision": limpiar_texto_tabla(a.get("nombre_comision", "")),
                    "rol": limpiar_texto_tabla(a.get("rol", "")),
                    "horas": float(_hora_numero(a.get("horas_asignadas", 0)) or 0),
                })
        cur.close()
        if asignaciones_a_finalizar:
            conn.commit()
    finally:
        conn.close()

    # El movimiento se registra después del UPDATE y solo si no existe ya uno
    # equivalente. Esto permite ejecutar la función más de una vez sin duplicar.
    for a in asignaciones_a_finalizar:
        cid = int(a["comision_id"])
        conn_chk = get_conn()
        try:
            existente = pd.read_sql("""
                SELECT id
                FROM movimientos
                WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?) AND fecha=?
                  AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))='baja docente por modificación de asignación'
                  AND (COALESCE(detalle,'') LIKE ? OR COALESCE(observaciones,'') LIKE ?)
                LIMIT 1
            """, conn_chk, params=[pid, cuil_txt, fe.isoformat(), f"%Comisión ID {cid}%", f"%Comisión ID {cid}%"])
        finally:
            conn_chk.close()
        if not existente.empty:
            continue
        detalle_mov = (
            f"Baja docente por modificación de asignación: Comisión ID {cid} - {a['nombre_comision']}. "
            f"Docente {nombre_docente} [{cuil_txt}], rol {a['rol']}, {a['horas']:g} hs. "
            f"Fecha efectiva: {fe.isoformat()}. Baja automática por finalización de su última designación docente vigente."
        )
        registrar_movimiento(
            "Baja docente por modificación de asignación",
            cuil_txt,
            nombre_docente,
            detalle_mov,
            f"Baja automática de comisión por quedar sin designaciones docentes vigentes. Fecha efectiva: {fe.isoformat()}. Comisión ID {cid}.",
            pid,
            horas_variacion=0,
            fecha_movimiento=fe,
        )

    if asignaciones_a_finalizar:
        try:
            invalidar_cache_rendimiento_v191("baja automática de comisiones por finalización de designación v214")
        except Exception:
            pass
        try:
            limpiar_cache_comisiones_operativas()
        except Exception:
            pass
    return len(asignaciones_a_finalizar)


# --- entry l. 34251-34253
def _es_funcion_no_docente_v162(valor):
    from analisis.motor.ref.extracted_batch04.designaciones import _es_funcion_no_docente_v162 as _b04_core__es_funcion_no_docente_v162
    return _b04_core__es_funcion_no_docente_v162(valor)


# --- entry l. 34409-34411
def _texto_funcion_no_docente_limpio_v164(valor):
    from analisis.motor.ref.extracted_batch01.docentes import _texto_funcion_no_docente_limpio_v164 as _b01_core__texto_funcion_no_docente_limpio_v164
    return _b01_core__texto_funcion_no_docente_limpio_v164(valor)


# --- entry l. 34440
_get_designaciones_pre_v162 = get_designaciones


# --- entry l. 34443-34478
def get_designaciones(periodo_id=None):
    df = _get_designaciones_pre_v162(periodo_id)
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        if "funcion_no_docente" not in out.columns:
            out["funcion_no_docente"] = pd.Series(dtype=int)
        if "texto_funcion_no_docente" not in out.columns:
            out["texto_funcion_no_docente"] = pd.Series(dtype=str)
        return out
    try:
        conn = get_conn()
        if periodo_id is None:
            extra = pd.read_sql(
                "SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente, COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente FROM designaciones",
                conn,
            )
        else:
            extra = pd.read_sql(
                "SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente, COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente FROM designaciones WHERE periodo_id = ?",
                conn,
                params=[int(periodo_id)],
            )
        conn.close()
        out = out.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore").merge(extra, on="id", how="left")
    except Exception:
        out["funcion_no_docente"] = 0
        out["texto_funcion_no_docente"] = ""
    out["funcion_no_docente"] = pd.to_numeric(
        out.get("funcion_no_docente", 0), errors="coerce"
    ).fillna(0).astype(int)
    if "texto_funcion_no_docente" not in out.columns:
        out["texto_funcion_no_docente"] = ""
    out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
    return out


# --- entry l. 41265
_get_designaciones_pre_v191 = get_designaciones


# --- entry l. 41267-41268
def _get_designaciones_cache_v191(periodo_id, db_url, inst, dep, version):
    return _get_designaciones_pre_v191(periodo_id)


# --- entry l. 41269-41273
def get_designaciones(periodo_id=None):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_designaciones_cache_v191(periodo_id, db_url, inst, dep, version)
    )


# --- entry l. 42936
_get_periodos_pre_v193 = get_periodos


# --- entry l. 42938-42939
def _get_periodos_cache_v193(db_url, inst, dep, version):
    return _get_periodos_pre_v193()


# --- entry l. 42940-42944
def get_periodos():
    db_url, inst, dep, version = _scope_rendimiento_v191()
    return _copiar_resultado_cache_v191(
        _get_periodos_cache_v193(db_url, inst, dep, version)
    )


# --- entry l. 43602
_obtener_cargo_prioritario_pre_v195 = obtener_cargo_prioritario_docente_periodo


# --- entry l. 43605-43611
def _obtener_cargo_prioritario_cache_v195(
    cuil, periodo_id, departamento_contexto_id,
    db_url, inst, dep, version
):
    return _obtener_cargo_prioritario_pre_v195(
        cuil, int(periodo_id), departamento_contexto_id
    )


# --- entry l. 43613-43623
def obtener_cargo_prioritario_docente_periodo(
    cuil, periodo_id, departamento_contexto_id=None
):
    db_url, inst, dep, version = _scope_rendimiento_v191()
    resultado = _obtener_cargo_prioritario_cache_v195(
        str(cuil or ""),
        int(periodo_id),
        int(departamento_contexto_id) if departamento_contexto_id is not None else None,
        db_url, inst, dep, version,
    )
    return dict(resultado or {})


# --- entry l. 44658
_get_periodos_legacy_v280 = get_periodos


# --- entry l. 44685-44712
def _guardar_diagnostico_periodos_v280(decision, inst=None, dep=None, error=None):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v280_periods_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_PERIODS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v280 períodos] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 44723-44776
def get_periodos():
    legacy = _get_periodos_legacy_v280()
    mode = _modo_lectura_periodos_v280()

    # Default conservador: cero imports/costo adicional si el piloto está apagado.
    if mode == "off":
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_periodos_v280(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v280"),
            )
            _guardar_diagnostico_periodos_v280(decision)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    db_url = str(DATABASE_URL)
    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        new_df = _get_periodos_nuevo_cache_v280(
            str(db_url), int(inst), int(dep), version
        )
        from integraciones.ciclo_periodos.motor.pilotos_no_portados.periods_pilot import choose_periods_frame
        decision = choose_periods_frame(
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_periodos_v280(decision, inst, dep)
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.periods_pilot import choose_periods_frame
            decision = choose_periods_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_periodos_v280(decision, inst, dep, error=exc)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)


# --- entry l. 46509
_obtener_cargo_prioritario_pre_v200 = obtener_cargo_prioritario_docente_periodo


# --- entry l. 46512-46663
def _mapa_cargos_prioritarios_v200(periodo_id, dep_contexto, inst_id, version_dep):
    if not USE_POSTGRESQL:
        return {}

    try:
        df_dep = _pg_read_dataframe(
            """
            SELECT id, nombre
            FROM departamentos
            WHERE institucion_id=%s
            ORDER BY id
            """,
            [int(inst_id)],
        )
    except Exception:
        df_dep = pd.DataFrame()

    dep_por_nombre = {}
    if isinstance(df_dep, pd.DataFrame) and not df_dep.empty:
        for _, r in df_dep.iterrows():
            k = normalizar_clave(r.get("nombre", ""))
            if k:
                dep_por_nombre[k] = int(r.get("id"))

    try:
        df_doc = _pg_read_dataframe(
            """
            SELECT cuil,
                   COALESCE(tipo_docente,'Propio') AS tipo_docente,
                   COALESCE(observaciones,'') AS observaciones
            FROM docentes
            WHERE institucion_id=%s
              AND departamento_id=%s
            ORDER BY id
            """,
            [int(inst_id), int(dep_contexto)],
        )
    except Exception:
        df_doc = pd.DataFrame()

    try:
        df_des = _pg_read_dataframe(
            f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id=%s
                LIMIT 1
            )
            SELECT
                d.cuil, d.cargo, d.departamento_id,
                COALESCE(dep.nombre,'') AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id=d.periodo_id
            JOIN pr ON {_condicion_periodo_equivalente_sql('p','pr')}
            LEFT JOIN departamentos dep ON dep.id=d.departamento_id
            WHERE d.institucion_id=%s
              AND d.estado='Activa'
              AND COALESCE(TRIM(d.cargo),'') <> ''
            """,
            [int(periodo_id), int(inst_id)],
        )
    except Exception:
        df_des = pd.DataFrame()

    tipos = {}
    if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
        for _, r in df_doc.iterrows():
            k = _clave_cuil(r.get("cuil"))
            if not k:
                continue
            tipos[k] = {
                "tipo": str(r.get("tipo_docente") or "Propio"),
                "obs": str(r.get("observaciones") or ""),
            }

    grupos = {}
    if isinstance(df_des, pd.DataFrame) and not df_des.empty:
        aux = df_des.copy()
        aux["_cuil_v200"] = aux["cuil"].fillna("").astype(str).map(_clave_cuil)
        for k, g in aux.groupby("_cuil_v200", sort=False):
            if k:
                grupos[str(k)] = g.copy()

    prioridad = {cargo: i for i, cargo in enumerate(ORDEN_JERARQUICO_CARGOS_COMISION)}
    claves = set(grupos) | set(tipos)
    salida = {}

    for k in claves:
        meta = tipos.get(k, {"tipo": "Propio", "obs": ""})
        es_prestado = normalizar_clave(meta.get("tipo", "")) == "PRESTADO"
        dep_esperado = int(dep_contexto)
        dep_origen_nombre = ""

        if es_prestado:
            dep_origen_nombre = _extraer_departamento_origen_prestado(meta.get("obs", ""))
            dep_esperado = dep_por_nombre.get(normalizar_clave(dep_origen_nombre))

        g = grupos.get(k, pd.DataFrame())
        candidatos = pd.DataFrame()
        if isinstance(g, pd.DataFrame) and not g.empty:
            if es_prestado:
                if dep_esperado is not None:
                    candidatos = g[
                        pd.to_numeric(g["departamento_id"], errors="coerce")
                        .fillna(-1).astype(int).eq(int(dep_esperado))
                    ].copy()
                    if candidatos.empty:
                        candidatos = g[
                            ~pd.to_numeric(g["departamento_id"], errors="coerce")
                            .fillna(-1).astype(int).eq(int(dep_contexto))
                        ].copy()
                else:
                    candidatos = g[
                        ~pd.to_numeric(g["departamento_id"], errors="coerce")
                        .fillna(-1).astype(int).eq(int(dep_contexto))
                    ].copy()
            else:
                candidatos = g[
                    pd.to_numeric(g["departamento_id"], errors="coerce")
                    .fillna(-1).astype(int).eq(int(dep_contexto))
                ].copy()

        if candidatos.empty:
            salida[k] = {
                "cargo": "",
                "departamento": dep_origen_nombre,
                "motivo": (
                    f"No se encontró una designación activa en {dep_origen_nombre} para el período de la comisión."
                    if dep_origen_nombre
                    else "No se encontró designación activa."
                ),
            }
            continue

        candidatos = candidatos.copy()
        candidatos["cargo_canonico"] = candidatos["cargo"].map(_normalizar_cargo_para_jerarquia)
        candidatos["_prioridad"] = candidatos["cargo_canonico"].map(prioridad).fillna(999)
        candidatos = candidatos.sort_values(
            ["_prioridad", "departamento", "cargo_canonico"],
            kind="stable",
        )
        elegido = candidatos.iloc[0]
        cargo = str(elegido.get("cargo_canonico") or elegido.get("cargo") or "").strip()
        departamento = str(elegido.get("departamento") or dep_origen_nombre or "").strip()
        salida[k] = {
            "cargo": cargo,
            "departamento": departamento,
            "motivo": f"Cargo activo de {departamento}." if departamento else "Cargo activo detectado.",
        }

    return salida


# --- entry l. 46666-46694
def obtener_cargo_prioritario_docente_periodo(cuil, periodo_id, departamento_contexto_id=None):
    if not USE_POSTGRESQL:
        return _obtener_cargo_prioritario_pre_v200(
            cuil, periodo_id, departamento_contexto_id
        )
    cuil_limpio = limpiar_cuil(cuil)
    if not cuil_limpio or periodo_id is None:
        return {"cargo": "", "departamento": "", "motivo": "Falta CUIL o período."}
    try:
        inst = int(_pg_current_inst_id() or 0)
        dep = int(departamento_contexto_id or _pg_current_dep_id() or 0)
        version_dep = _version_dependencias_v200(
            ("docentes", "designaciones", "prestamos", "periodos"),
            inst,
            dep,
        )
        mapa = _mapa_cargos_prioritarios_v200(
            int(periodo_id), dep, inst, version_dep
        )
        dato = mapa.get(_clave_cuil(cuil_limpio))
        if dato is not None:
            return dict(dato)
    except Exception:
        pass

    # Fallback exacto a la lógica histórica si aparece un caso no contemplado.
    return _obtener_cargo_prioritario_pre_v200(
        cuil, periodo_id, departamento_contexto_id
    )


# --- entry l. 50006-50074
def asegurar_esquema_documentos_respaldo_v249():
    if st.session_state.get("_esquema_documentos_respaldo_v249_ok"):
        return
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    tipo_documento TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    numero TEXT,
                    fecha DATE,
                    periodo_id BIGINT,
                    cuil TEXT,
                    docente_nombre TEXT,
                    proyecto_tipo TEXT,
                    proyecto_id BIGINT,
                    referencia_texto TEXT,
                    titulo TEXT,
                    detalle TEXT,
                    observaciones TEXT,
                    archivo_nombre TEXT NOT NULL,
                    archivo_mime TEXT DEFAULT 'application/pdf',
                    archivo_pdf BYTEA NOT NULL,
                    archivo_bytes BIGINT DEFAULT 0,
                    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_carga TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_dep_fecha_v249 ON documentos_respaldo (institucion_id, departamento_id, fecha DESC, id DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_docente_v249 ON documentos_respaldo (institucion_id, departamento_id, cuil)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_docresp_proyecto_v249 ON documentos_respaldo (institucion_id, proyecto_tipo, proyecto_id)")
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_documento TEXT NOT NULL,
                categoria TEXT NOT NULL,
                numero TEXT,
                fecha TEXT,
                periodo_id INTEGER,
                cuil TEXT,
                docente_nombre TEXT,
                proyecto_tipo TEXT,
                proyecto_id INTEGER,
                referencia_texto TEXT,
                titulo TEXT,
                detalle TEXT,
                observaciones TEXT,
                archivo_nombre TEXT NOT NULL,
                archivo_mime TEXT DEFAULT 'application/pdf',
                archivo_pdf BLOB NOT NULL,
                archivo_bytes INTEGER DEFAULT 0,
                fecha_carga TEXT,
                usuario_carga TEXT
            )
        """)
        conn.commit(); conn.close()
    st.session_state["_esquema_documentos_respaldo_v249_ok"] = True


# --- entry l. 50077-50100
def asegurar_tipo_resolucion_documentos_v255():
    """Agrega de forma compatible el subtipo de resolución al repositorio existente."""
    if st.session_state.get("_esquema_tipo_resolucion_v255_ok"):
        return
    asegurar_esquema_documentos_respaldo_v249()
    if USE_POSTGRESQL:
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS tipo_resolucion TEXT")
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        try:
            cols = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo)").fetchall()]
            if "tipo_resolucion" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN tipo_resolucion TEXT")
                conn.commit()
        finally:
            conn.close()
    st.session_state["_esquema_tipo_resolucion_v255_ok"] = True


# --- entry l. 50113-50213
def asegurar_esquema_dependencias_documentales_v262():
    """Catálogo institucional de organismos/áreas que emiten actos administrativos."""
    if st.session_state.get("_esquema_dependencias_documentales_v262_ok"):
        return
    asegurar_esquema_documentos_respaldo_v249()
    asegurar_tipo_resolucion_documentos_v255()

    if USE_POSTGRESQL:
        inst = _pg_current_inst_id()
        if inst is None:
            return
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dependencias_documentales (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    nombre TEXT NOT NULL,
                    estado TEXT DEFAULT 'Activa',
                    observaciones TEXT,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_dependencias_documentales_nombre_v262
                ON dependencias_documentales (institucion_id, LOWER(TRIM(nombre)))
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS ix_dependencias_documentales_estado_v262
                ON dependencias_documentales (institucion_id, estado, nombre)
            """)
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS dependencia_id BIGINT")
            cur.execute("ALTER TABLE documentos_respaldo ADD COLUMN IF NOT EXISTS dependencia_nombre TEXT")

            # Valores que ya existían implícitamente en v255.
            for nombre in ["Rectorado", "Consejo Superior"]:
                cur.execute("""
                    INSERT INTO dependencias_documentales
                        (institucion_id, nombre, estado, observaciones, fecha_creacion, fecha_actualizacion)
                    SELECT %s, %s, 'Activa', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dependencias_documentales
                        WHERE institucion_id=%s AND LOWER(TRIM(nombre))=LOWER(TRIM(%s))
                    )
                """, [int(inst), nombre, int(inst), nombre])

            # Migra documentos viejos cuyo emisor puede inferirse sin ambigüedad.
            cur.execute("""
                UPDATE documentos_respaldo d
                SET dependencia_id = dep.id, dependencia_nombre = dep.nombre
                FROM dependencias_documentales dep
                WHERE d.institucion_id=%s
                  AND dep.institucion_id=d.institucion_id
                  AND COALESCE(d.dependencia_id,0)=0
                  AND (
                       (LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' AND LOWER(TRIM(dep.nombre))='rectorado')
                    OR (LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' AND LOWER(TRIM(dep.nombre))='consejo superior')
                  )
            """, [int(inst)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        try: inst = int(_institucion_id_operativa() or 1)
        except Exception: inst = 1
        conn = get_conn(); c = conn.cursor()
        try:
            c.execute("""
                CREATE TABLE IF NOT EXISTS dependencias_documentales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    institucion_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    estado TEXT DEFAULT 'Activa',
                    observaciones TEXT,
                    fecha_creacion TEXT,
                    fecha_actualizacion TEXT
                )
            """)
            cols = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo)").fetchall()]
            if "dependencia_id" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN dependencia_id INTEGER")
            if "dependencia_nombre" not in cols:
                c.execute("ALTER TABLE documentos_respaldo ADD COLUMN dependencia_nombre TEXT")
            for nombre in ["Rectorado", "Consejo Superior"]:
                ex = c.execute("SELECT id FROM dependencias_documentales WHERE institucion_id=? AND LOWER(TRIM(nombre))=LOWER(TRIM(?)) LIMIT 1", (inst, nombre)).fetchone()
                if not ex:
                    ahora = datetime.now().isoformat(timespec="seconds")
                    c.execute("INSERT INTO dependencias_documentales (institucion_id,nombre,estado,observaciones,fecha_creacion,fecha_actualizacion) VALUES (?,?,?,?,?,?)", (inst,nombre,"Activa","",ahora,ahora))
            deps = c.execute("SELECT id,nombre FROM dependencias_documentales WHERE institucion_id=?", (inst,)).fetchall()
            mapa = {str(n or "").strip().casefold(): int(i) for i,n in deps}
            if "rectorado" in mapa:
                c.execute("UPDATE documentos_respaldo SET dependencia_id=?, dependencia_nombre='Rectorado' WHERE COALESCE(dependencia_id,0)=0 AND LOWER(TRIM(COALESCE(tipo_resolucion,'')))='rectoral'", (mapa["rectorado"],))
            if "consejo superior" in mapa:
                c.execute("UPDATE documentos_respaldo SET dependencia_id=?, dependencia_nombre='Consejo Superior' WHERE COALESCE(dependencia_id,0)=0 AND LOWER(TRIM(COALESCE(tipo_resolucion,'')))='consejo superior'", (mapa["consejo superior"],))
            conn.commit()
        finally:
            conn.close()
    st.session_state["_esquema_dependencias_documentales_v262_ok"] = True


# --- entry l. 50636-50711
def asegurar_esquema_documentos_respaldo_docentes_v251():
    """Relación uno-a-muchos entre un PDF respaldatorio y sus docentes."""
    asegurar_esquema_documentos_respaldo_v249()
    if st.session_state.get("_esquema_documentos_respaldo_docentes_v263_ok"):
        return

    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_docentes (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    cuil TEXT NOT NULL,
                    docente_nombre TEXT,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (institucion_id, departamento_id, documento_id, cuil)
                )
            """)
            cur.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN IF NOT EXISTS tipo_movimiento TEXT")
            cur.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN IF NOT EXISTS detalle_vinculo TEXT")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_docentes_documento_v251
                ON documentos_respaldo_docentes (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_docentes_cuil_v251
                ON documentos_respaldo_docentes (institucion_id, departamento_id, cuil)
            """)
            # Migra automáticamente los documentos creados con v249, que admitían
            # un único docente guardado en la tabla principal.
            cur.execute("""
                INSERT INTO documentos_respaldo_docentes
                    (institucion_id, departamento_id, documento_id, cuil, docente_nombre)
                SELECT d.institucion_id, d.departamento_id, d.id, TRIM(d.cuil), COALESCE(d.docente_nombre,'')
                FROM documentos_respaldo d
                WHERE d.institucion_id=%s AND d.departamento_id=%s
                  AND TRIM(COALESCE(d.cuil,'')) <> ''
                ON CONFLICT (institucion_id, departamento_id, documento_id, cuil) DO NOTHING
            """, [int(inst), int(dep)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_docentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                cuil TEXT NOT NULL,
                docente_nombre TEXT,
                fecha_vinculacion TEXT,
                UNIQUE (documento_id, cuil)
            )
        """)
        cols_docresp_v263 = [str(r[1]) for r in c.execute("PRAGMA table_info(documentos_respaldo_docentes)").fetchall()]
        if "tipo_movimiento" not in cols_docresp_v263:
            c.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN tipo_movimiento TEXT")
        if "detalle_vinculo" not in cols_docresp_v263:
            c.execute("ALTER TABLE documentos_respaldo_docentes ADD COLUMN detalle_vinculo TEXT")
        c.execute("""
            INSERT OR IGNORE INTO documentos_respaldo_docentes
                (documento_id, cuil, docente_nombre, fecha_vinculacion)
            SELECT id, TRIM(cuil), COALESCE(docente_nombre,''), ?
            FROM documentos_respaldo
            WHERE TRIM(COALESCE(cuil,'')) <> ''
        """, (datetime.now().isoformat(timespec="seconds"),))
        conn.commit(); conn.close()

    st.session_state["_esquema_documentos_respaldo_docentes_v251_ok"] = True
    st.session_state["_esquema_documentos_respaldo_docentes_v263_ok"] = True


# --- entry l. 51297-51299
def _etiqueta_acto_v263(tipo_documento, numero, dependencia=""):
    from analisis.motor.ref.extracted_batch01.documentos import _etiqueta_acto_v263 as _b01_core__etiqueta_acto_v263
    return _b01_core__etiqueta_acto_v263(tipo_documento, numero, dependencia)


# --- entry l. 54116-54297
def asegurar_esquema_actos_administrativos_v266():
    """Crea vínculos documento↔designación y documento↔movimiento y migra lo inequívoco."""
    # La migración de datos es departamental. No alcanza con recordar que las tablas
    # ya existen: si el usuario cambia de departamento en la misma sesión también
    # hay que migrar las referencias manuales de ese nuevo ámbito.
    if USE_POSTGRESQL:
        _inst_scope_v266 = _pg_current_inst_id(); _dep_scope_v266 = _pg_current_dep_id()
        _scope_key_v266 = f"pg_{_inst_scope_v266}_{_dep_scope_v266}"
    else:
        _scope_key_v266 = "sqlite_" + hashlib.md5(str(DB_PATH).encode("utf-8", errors="ignore")).hexdigest()[:12]
    _state_key_v266 = f"_esquema_actos_admin_v266_ok_{_scope_key_v266}"
    if st.session_state.get(_state_key_v266):
        return

    asegurar_esquema_documentos_respaldo_v249()
    asegurar_esquema_documentos_respaldo_docentes_v251()
    asegurar_esquema_dependencias_documentales_v262()

    if USE_POSTGRESQL:
        inst = _inst_scope_v266; dep = _dep_scope_v266
        conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_designaciones (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    designacion_id BIGINT NOT NULL REFERENCES designaciones(id) ON DELETE CASCADE,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_vinculacion TEXT,
                    UNIQUE (institucion_id, departamento_id, designacion_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_designaciones_doc_v266
                ON documentos_respaldo_designaciones (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_designaciones_desig_v266
                ON documentos_respaldo_designaciones (institucion_id, departamento_id, designacion_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos_respaldo_movimientos (
                    id BIGSERIAL PRIMARY KEY,
                    institucion_id BIGINT NOT NULL,
                    departamento_id BIGINT NOT NULL,
                    documento_id BIGINT NOT NULL REFERENCES documentos_respaldo(id) ON DELETE CASCADE,
                    movimiento_id BIGINT NOT NULL REFERENCES movimientos(id) ON DELETE CASCADE,
                    fecha_vinculacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_vinculacion TEXT,
                    UNIQUE (institucion_id, departamento_id, movimiento_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_movimientos_doc_v266
                ON documentos_respaldo_movimientos (institucion_id, departamento_id, documento_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_docresp_movimientos_mov_v266
                ON documentos_respaldo_movimientos (institucion_id, departamento_id, movimiento_id)
            """)

            # Números manuales históricos: solo se vinculan si el número identifica
            # exactamente un documento del repositorio dentro del departamento.
            cur.execute("""
                INSERT INTO documentos_respaldo_designaciones
                    (institucion_id, departamento_id, documento_id, designacion_id, usuario_vinculacion)
                SELECT d.institucion_id, d.departamento_id,
                       MIN(doc.id) AS documento_id, d.id, 'migracion-v266'
                FROM designaciones d
                JOIN documentos_respaldo doc
                  ON doc.institucion_id=d.institucion_id
                 AND doc.departamento_id=d.departamento_id
                 AND TRIM(COALESCE(doc.numero,''))=TRIM(COALESCE(d.numero_resolucion,''))
                LEFT JOIN documentos_respaldo_designaciones rel
                  ON rel.institucion_id=d.institucion_id
                 AND rel.departamento_id=d.departamento_id
                 AND rel.designacion_id=d.id
                WHERE d.institucion_id=%s AND d.departamento_id=%s
                  AND TRIM(COALESCE(d.numero_resolucion,''))<>''
                  AND rel.id IS NULL
                GROUP BY d.institucion_id, d.departamento_id, d.id
                HAVING COUNT(DISTINCT doc.id)=1
                ON CONFLICT (institucion_id, departamento_id, designacion_id) DO NOTHING
            """, [int(inst), int(dep)])

            # PDFs creados por v263 para movimientos: transforma el vínculo genérico
            # por CUIL/tipo/detalle en una relación exacta al movimiento, si es único.
            cur.execute("""
                INSERT INTO documentos_respaldo_movimientos
                    (institucion_id, departamento_id, documento_id, movimiento_id, usuario_vinculacion)
                SELECT m.institucion_id, m.departamento_id,
                       MIN(rd.documento_id) AS documento_id, m.id, 'migracion-v266'
                FROM movimientos m
                JOIN documentos_respaldo_docentes rd
                  ON rd.institucion_id=m.institucion_id
                 AND rd.departamento_id=m.departamento_id
                 AND TRIM(COALESCE(rd.cuil,''))=TRIM(COALESCE(m.cuil,''))
                 AND TRIM(COALESCE(rd.tipo_movimiento,''))=TRIM(COALESCE(m.tipo_movimiento,''))
                 AND TRIM(COALESCE(rd.detalle_vinculo,''))=TRIM(COALESCE(m.detalle,''))
                LEFT JOIN documentos_respaldo_movimientos rm
                  ON rm.institucion_id=m.institucion_id
                 AND rm.departamento_id=m.departamento_id
                 AND rm.movimiento_id=m.id
                WHERE m.institucion_id=%s AND m.departamento_id=%s
                  AND rm.id IS NULL
                GROUP BY m.institucion_id, m.departamento_id, m.id
                HAVING COUNT(DISTINCT rd.documento_id)=1
                ON CONFLICT (institucion_id, departamento_id, movimiento_id) DO NOTHING
            """, [int(inst), int(dep)])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_designaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                designacion_id INTEGER NOT NULL UNIQUE,
                fecha_vinculacion TEXT,
                usuario_vinculacion TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS documentos_respaldo_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                movimiento_id INTEGER NOT NULL UNIQUE,
                fecha_vinculacion TEXT,
                usuario_vinculacion TEXT
            )
        """)
        try:
            candidatos = pd.read_sql("""
                SELECT d.id AS designacion_id, TRIM(COALESCE(d.numero_resolucion,'')) AS numero
                FROM designaciones d
                LEFT JOIN documentos_respaldo_designaciones r ON r.designacion_id=d.id
                WHERE TRIM(COALESCE(d.numero_resolucion,''))<>'' AND r.id IS NULL
            """, conn)
            for _, row in candidatos.iterrows():
                docs = pd.read_sql(
                    "SELECT id FROM documentos_respaldo WHERE TRIM(COALESCE(numero,''))=TRIM(?)",
                    conn, params=[str(row.get("numero") or "")]
                )
                if len(docs) == 1:
                    c.execute("""
                        INSERT OR IGNORE INTO documentos_respaldo_designaciones
                            (documento_id, designacion_id, fecha_vinculacion, usuario_vinculacion)
                        VALUES (?,?,?,?)
                    """, (int(docs.iloc[0]["id"]), int(row["designacion_id"]), datetime.now().isoformat(timespec="seconds"), "migracion-v266"))
        except Exception:
            pass
        try:
            candidatos_mov = pd.read_sql("""
                SELECT m.id AS movimiento_id, m.cuil, m.tipo_movimiento, m.detalle
                FROM movimientos m
                LEFT JOIN documentos_respaldo_movimientos r ON r.movimiento_id=m.id
                WHERE r.id IS NULL
            """, conn)
            for _, row in candidatos_mov.iterrows():
                docs = pd.read_sql("""
                    SELECT DISTINCT documento_id
                    FROM documentos_respaldo_docentes
                    WHERE TRIM(COALESCE(cuil,''))=TRIM(?)
                      AND TRIM(COALESCE(tipo_movimiento,''))=TRIM(?)
                      AND TRIM(COALESCE(detalle_vinculo,''))=TRIM(?)
                """, conn, params=[str(row.get("cuil") or ""), str(row.get("tipo_movimiento") or ""), str(row.get("detalle") or "")])
                if len(docs) == 1:
                    c.execute("""
                        INSERT OR IGNORE INTO documentos_respaldo_movimientos
                            (documento_id, movimiento_id, fecha_vinculacion, usuario_vinculacion)
                        VALUES (?,?,?,?)
                    """, (int(docs.iloc[0]["documento_id"]), int(row["movimiento_id"]), datetime.now().isoformat(timespec="seconds"), "migracion-v266"))
        except Exception:
            pass
        conn.commit(); conn.close()

    st.session_state[_state_key_v266] = True


# --- entry l. 54300-54305
def _usuario_acto_v266():
    try:
        u = current_user() or {}
        return str(u.get("email") or u.get("nombre") or "").strip()
    except Exception:
        return ""


# --- entry l. 54319-54321
def _id_documento_valido_v266(valor):
    from analisis.motor.ref.extracted_batch04.numeros import _id_documento_valido_v266 as _b04_core__id_documento_valido_v266
    return _b04_core__id_documento_valido_v266(valor)


# --- entry l. 54344-54378
def _mapa_actos_designaciones_v266(ids_designacion):
    asegurar_esquema_actos_administrativos_v266()
    ids = sorted({int(x) for x in ids_designacion if pd.notna(x)})
    if not ids:
        return {}
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id()
        ph = ",".join(["%s"] * len(ids))
        df = _pg_read_dataframe(f"""
            SELECT r.designacion_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_designaciones r
            JOIN documentos_respaldo d ON d.id=r.documento_id
              AND d.institucion_id=r.institucion_id AND d.departamento_id=r.departamento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
            WHERE r.institucion_id=%s AND r.departamento_id=%s
              AND r.designacion_id IN ({ph})
        """, [int(inst), int(dep)] + ids)
    else:
        conn = get_conn(); ph = ",".join(["?"] * len(ids))
        df = pd.read_sql(f"""
            SELECT r.designacion_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_designaciones r
            JOIN documentos_respaldo d ON d.id=r.documento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
            WHERE r.designacion_id IN ({ph})
        """, conn, params=ids); conn.close()
    return {int(r["designacion_id"]): r.to_dict() for _, r in df.iterrows()}


# --- entry l. 54381-54414
def _mapa_actos_movimientos_v266(ids_movimiento):
    asegurar_esquema_actos_administrativos_v266()
    ids = sorted({int(x) for x in ids_movimiento if pd.notna(x)})
    if not ids:
        return {}
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id(); ph = ",".join(["%s"] * len(ids))
        df = _pg_read_dataframe(f"""
            SELECT r.movimiento_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_movimientos r
            JOIN documentos_respaldo d ON d.id=r.documento_id
              AND d.institucion_id=r.institucion_id AND d.departamento_id=r.departamento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id AND depdoc.institucion_id=d.institucion_id
            WHERE r.institucion_id=%s AND r.departamento_id=%s
              AND r.movimiento_id IN ({ph})
        """, [int(inst), int(dep)] + ids)
    else:
        conn = get_conn(); ph = ",".join(["?"] * len(ids))
        df = pd.read_sql(f"""
            SELECT r.movimiento_id, d.id AS documento_id, d.tipo_documento,
                   COALESCE(d.numero,'') AS numero, d.fecha,
                   COALESCE(NULLIF(TRIM(d.dependencia_nombre),''), depdoc.nombre,
                            CASE WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='rectoral' THEN 'Rectorado'
                                 WHEN LOWER(TRIM(COALESCE(d.tipo_resolucion,'')))='consejo superior' THEN 'Consejo Superior' ELSE '' END) AS dependencia_emisora
            FROM documentos_respaldo_movimientos r
            JOIN documentos_respaldo d ON d.id=r.documento_id
            LEFT JOIN dependencias_documentales depdoc ON depdoc.id=d.dependencia_id
            WHERE r.movimiento_id IN ({ph})
        """, conn, params=ids); conn.close()
    return {int(r["movimiento_id"]): r.to_dict() for _, r in df.iterrows()}


# --- entry l. 54417-54449
def vincular_acto_designacion_v266(designacion_id, documento_id):
    asegurar_esquema_actos_administrativos_v266()
    usuario = _usuario_acto_v266()
    if USE_POSTGRESQL:
        inst = _pg_current_inst_id(); dep = _pg_current_dep_id(); conn = _pg_raw_conn(); cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO documentos_respaldo_designaciones
                    (institucion_id, departamento_id, documento_id, designacion_id, usuario_vinculacion)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (institucion_id, departamento_id, designacion_id)
                DO UPDATE SET documento_id=EXCLUDED.documento_id,
                              fecha_vinculacion=CURRENT_TIMESTAMP,
                              usuario_vinculacion=EXCLUDED.usuario_vinculacion
            """, [int(inst), int(dep), int(documento_id), int(designacion_id), usuario])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn = get_conn(); c = conn.cursor()
        c.execute("""
            INSERT INTO documentos_respaldo_designaciones
                (documento_id, designacion_id, fecha_vinculacion, usuario_vinculacion)
            VALUES (?,?,?,?)
            ON CONFLICT(designacion_id) DO UPDATE SET
                documento_id=excluded.documento_id,
                fecha_vinculacion=excluded.fecha_vinculacion,
                usuario_vinculacion=excluded.usuario_vinculacion
        """, (int(documento_id), int(designacion_id), datetime.now().isoformat(timespec="seconds"), usuario))
        conn.commit(); conn.close()
    invalidar_cache_rendimiento_v191("acto administrativo de designación vinculado")


# --- entry l. 54468-54499
def vincular_acto_movimiento_v266(movimiento_id, documento_id):
    if not _id_documento_valido_v266(movimiento_id):
        return
    asegurar_esquema_actos_administrativos_v266(); usuario = _usuario_acto_v266()
    if USE_POSTGRESQL:
        inst=_pg_current_inst_id(); dep=_pg_current_dep_id(); conn=_pg_raw_conn(); cur=conn.cursor()
        try:
            cur.execute("""
                INSERT INTO documentos_respaldo_movimientos
                    (institucion_id, departamento_id, documento_id, movimiento_id, usuario_vinculacion)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (institucion_id, departamento_id, movimiento_id)
                DO UPDATE SET documento_id=EXCLUDED.documento_id,
                              fecha_vinculacion=CURRENT_TIMESTAMP,
                              usuario_vinculacion=EXCLUDED.usuario_vinculacion
            """, [int(inst), int(dep), int(documento_id), int(movimiento_id), usuario])
            conn.commit()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()
    else:
        conn=get_conn(); c=conn.cursor(); c.execute("""
            INSERT INTO documentos_respaldo_movimientos
                (documento_id, movimiento_id, fecha_vinculacion, usuario_vinculacion)
            VALUES (?,?,?,?)
            ON CONFLICT(movimiento_id) DO UPDATE SET
                documento_id=excluded.documento_id,
                fecha_vinculacion=excluded.fecha_vinculacion,
                usuario_vinculacion=excluded.usuario_vinculacion
        """, (int(documento_id), int(movimiento_id), datetime.now().isoformat(timespec="seconds"), usuario)); conn.commit(); conn.close()
    invalidar_cache_rendimiento_v191("acto administrativo de movimiento vinculado")


# --- entry l. 55154-55183
def _enriquecer_designaciones_acto_v266(df):
    if df is None or df.empty:
        return df
    out=df.copy()
    if "id" not in out.columns:
        return out
    mapa=_mapa_actos_designaciones_v266(pd.to_numeric(out["id"],errors="coerce").dropna().astype(int).tolist())
    out["numero_resolucion_legacy"] = out.get("numero_resolucion", pd.Series("", index=out.index)).fillna("").astype(str)
    out["acto_documento_id"] = pd.NA
    out["acto_administrativo"] = ""
    out["acto_dependencia"] = ""
    out["acto_fecha"] = ""
    for idx,row in out.iterrows():
        try: did=int(row.get("id"))
        except Exception: continue
        act=mapa.get(did)
        legacy=str(row.get("numero_resolucion_legacy") or "").strip()
        if act:
            out.at[idx,"acto_documento_id"] = int(act.get("documento_id"))
            out.at[idx,"acto_administrativo"] = _etiqueta_acto_v263(act.get("tipo_documento"),act.get("numero"),act.get("dependencia_emisora"))
            out.at[idx,"acto_dependencia"] = str(act.get("dependencia_emisora") or "")
            out.at[idx,"acto_fecha"] = str(act.get("fecha") or "")
            # El campo físico numero_resolucion NO se modifica ni se maquilla:
            # carga rápida conserva exactamente su comportamiento histórico y
            # los módulos nuevos consumen acto_documento_id/acto_administrativo.
        elif legacy:
            out.at[idx,"acto_administrativo"] = f"Resolución {legacy} — pendiente de vincular al repositorio"
        else:
            out.at[idx,"acto_administrativo"] = "Pendiente de vincular"
    return out


# --- entry l. 55186
_get_designaciones_pre_v266 = get_designaciones


# --- entry l. 55187-55188
def get_designaciones(periodo_id=None):
    return _enriquecer_designaciones_acto_v266(_get_designaciones_pre_v266(periodo_id))


# --- entry l. 55201
_get_designaciones_legacy_v282 = get_designaciones


# --- entry l. 55225-55254
def _guardar_diagnostico_designaciones_v282(decision, inst=None, dep=None, periodo_id=None, error=None):
    try:
        diag = decision.diagnostics() if decision is not None else {}
    except Exception:
        diag = {}
    try:
        diag.update({
            "institucion_id": int(inst) if inst is not None else None,
            "departamento_id": int(dep) if dep is not None else None,
            "periodo_id": int(periodo_id) if periodo_id is not None else None,
            "error": str(error)[:500] if error is not None else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        st.session_state["_v282_designations_read_diag"] = diag
        try:
            mostrar_stdout = str(_valor_configuracion("DEPTIT_DESIGNATIONS_DIAG_STDOUT", "0")).strip().casefold() in {"1", "true", "yes", "si", "sí"}
            if mostrar_stdout:
                print(
                    "[DEPTIT v282 designaciones] "
                    f"mode={diag.get('mode')} source={diag.get('source')} "
                    f"equivalent={diag.get('equivalent')} "
                    f"inst={diag.get('institucion_id')} dep={diag.get('departamento_id')} "
                    f"periodo={diag.get('periodo_id')} "
                    f"legacy_rows={diag.get('legacy_rows')} new_rows={diag.get('new_rows')} "
                    f"reason={diag.get('reason')} error={diag.get('error')}"
                )
        except Exception:
            pass
    except Exception:
        pass


# --- entry l. 55265-55318
def get_designaciones(periodo_id=None):
    legacy = _get_designaciones_legacy_v282(periodo_id)
    mode = _modo_lectura_designaciones_v282()

    if mode == "off":
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(mode="off", legacy=legacy)
            _guardar_diagnostico_designaciones_v282(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    if not USE_POSTGRESQL or not DATABASE_URL:
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(
                mode=mode,
                legacy=legacy,
                new_error=RuntimeError("PostgreSQL no disponible para el piloto v282"),
            )
            _guardar_diagnostico_designaciones_v282(decision, periodo_id=periodo_id)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)

    db_url = str(DATABASE_URL)
    inst = dep = None
    try:
        db_url, inst, dep, version = _scope_rendimiento_v191()
        new_df = _get_designaciones_nuevo_cache_v282(
            int(periodo_id) if periodo_id is not None else None,
            str(db_url), int(inst), int(dep), version
        )
        from integraciones.ciclo_periodos.motor.pilotos_no_portados.designations_pilot import choose_designations_frame
        decision = choose_designations_frame(
            mode=mode,
            legacy=legacy,
            new=new_df,
        )
        _guardar_diagnostico_designaciones_v282(decision, inst, dep, periodo_id)
        return _copiar_resultado_cache_v191(decision.frame)
    except Exception as exc:
        try:
            from integraciones.ciclo_periodos.motor.pilotos_no_portados.designations_pilot import choose_designations_frame
            decision = choose_designations_frame(
                mode=mode,
                legacy=legacy,
                new_error=exc,
            )
            _guardar_diagnostico_designaciones_v282(decision, inst, dep, periodo_id, error=exc)
        except Exception:
            pass
        return _copiar_resultado_cache_v191(legacy)


# --- entry l. 55321
_copiar_designaciones_periodo_pre_v266 = copiar_designaciones_periodo


# --- entry l. 55322-55367
def copiar_designaciones_periodo(periodo_origen_id, periodo_destino_id, nombre_destino, copiar_no_concursadas=True):
    """v266: conserva el mismo acto solo para concursados cuya vigencia continúa."""
    origen_v266 = pd.DataFrame()
    if periodo_origen_id is not None:
        try:
            origen_v266 = get_designaciones(int(periodo_origen_id))
        except Exception:
            origen_v266 = pd.DataFrame()
    resultado = _copiar_designaciones_periodo_pre_v266(
        periodo_origen_id, periodo_destino_id, nombre_destino,
        copiar_no_concursadas=copiar_no_concursadas
    )
    try:
        invalidar_cache_rendimiento_v191("copia de designaciones v266")
    except Exception:
        pass
    try:
        destino_v266 = get_designaciones(int(periodo_destino_id))
        if isinstance(origen_v266, pd.DataFrame) and not origen_v266.empty and isinstance(destino_v266, pd.DataFrame) and not destino_v266.empty:
            orig_conc = origen_v266[origen_v266.get("tipo_designacion", pd.Series(index=origen_v266.index,dtype=str)).fillna("").astype(str).str.strip().str.casefold().eq("concursado")].copy()
            dest_conc = destino_v266[destino_v266.get("tipo_designacion", pd.Series(index=destino_v266.index,dtype=str)).fillna("").astype(str).str.strip().str.casefold().eq("concursado")].copy()
            for _, dd in dest_conc.iterrows():
                clave = _clave_cuil(dd.get("cuil")) or str(dd.get("cuil") or "").strip()
                candidatos = orig_conc[orig_conc.get("cuil",pd.Series(index=orig_conc.index,dtype=str)).fillna("").astype(str).map(lambda x:_clave_cuil(x) or str(x).strip()).eq(clave)].copy()
                for col in ["cargo","dedicacion","tipo_designacion"]:
                    if col in candidatos.columns:
                        candidatos = candidatos[candidatos[col].fillna("").astype(str).str.strip().str.casefold().eq(str(dd.get(col) or "").strip().casefold())]
                candidatos = candidatos[candidatos.get("acto_documento_id",pd.Series(index=candidatos.index,dtype=object)).notna()] if not candidatos.empty else candidatos
                ids_doc = pd.to_numeric(candidatos.get("acto_documento_id",pd.Series(dtype=float)),errors="coerce").dropna().astype(int).unique().tolist() if not candidatos.empty else []
                if len(ids_doc)==1:
                    vincular_acto_designacion_v266(int(dd.get("id")), int(ids_doc[0]))
            # Vincula las renovaciones automáticas solo cuando el CUIL quedó con un único acto de designación.
            movs = get_movimientos_designaciones_periodo_v266(int(periodo_destino_id))
            if isinstance(movs,pd.DataFrame) and not movs.empty:
                renov = movs[movs["tipo_movimiento"].fillna("").astype(str).eq("Renovación automática de designación")].copy()
                destino_ref = get_designaciones(int(periodo_destino_id))
                for _, mm in renov.iterrows():
                    clave = _clave_cuil(mm.get("cuil")) or str(mm.get("cuil") or "").strip()
                    ds = destino_ref[destino_ref.get("cuil",pd.Series(index=destino_ref.index,dtype=str)).fillna("").astype(str).map(lambda x:_clave_cuil(x) or str(x).strip()).eq(clave)].copy()
                    ids_doc = pd.to_numeric(ds.get("acto_documento_id",pd.Series(dtype=float)),errors="coerce").dropna().astype(int).unique().tolist() if not ds.empty else []
                    if len(ids_doc)==1 and pd.isna(mm.get("acto_documento_id")):
                        vincular_acto_movimiento_v266(int(mm.get("id")),int(ids_doc[0]))
    except Exception:
        # La copia del período no debe fallar por una asociación documental posterior.
        pass
    return resultado


# --- entry l. 55370-55479
def get_movimientos_designaciones_periodo_v266(periodo_id):
    asegurar_esquema_actos_administrativos_v266()
    # v268: al consultar un período también se completa, de forma idempotente, la
    # baja natural de concursadas que vencieron dentro de ese período.
    try:
        sincronizar_vencimientos_concursados_v268(int(periodo_id))
    except Exception:
        pass
    conn=get_conn()
    try:
        df=pd.read_sql("""
            SELECT id, periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle,
                   COALESCE(observaciones,'') AS observaciones,
                   COALESCE(horas_variacion,0) AS horas_variacion
            FROM movimientos
            WHERE periodo_id=?
            ORDER BY fecha DESC, id DESC
        """, conn, params=[int(periodo_id)])
    finally:
        conn.close()
    if df.empty:
        return df
    tipos = {
        "Alta de designación", "Renovación automática de designación", "Cambio de cargo", "Aumento de dedicación", "Disminución de dedicación",
        "Cambio de tipo de designación", "Cambio de número de resolución",
        "Cambio de condición Ad Honorem", "Pase a Ad Honorem", "Pase a Rentado",
        "Cambio de función docente / no docente", "Cambio de funciones no docentes",
        "Finalizar / baja de designación", "Baja de designación", "Finalización de designación",
        "Finalización automática por vencimiento de designación",
        "Continuidad automática de designación concursada",
        "Modificación general",
    }
    df=df[df["tipo_movimiento"].fillna("").astype(str).isin(tipos)].copy()
    if df.empty: return df

    # v268: versiones antiguas pudieron dejar un movimiento de "Renovación automática"
    # rotulado como Concursado aun después de corregir/eliminar la continuidad. Eso no
    # representa la foto real: una concursada o continúa por vigencia real o queda de baja.
    descartar=[]
    for idx,row in df.iterrows():
        if str(row.get("tipo_movimiento") or "").strip() != "Renovación automática de designación":
            continue
        det_norm=normalizar_clave(str(row.get("detalle") or ""))
        if "CONCURSADO" not in det_norm:
            continue
        if _renovacion_concursada_legacy_valida_v268(row.get("cuil"), int(periodo_id)):
            df.at[idx,"tipo_movimiento"]="Continuidad automática de designación concursada"
            obs=str(df.at[idx,"observaciones"] or "").strip()
            nota="Reclasificado automáticamente: una designación concursada vigente continúa; no se renueva cuatrimestralmente."
            df.at[idx,"observaciones"]=(obs+" | " if obs else "")+nota
        else:
            descartar.append(idx)
    if descartar:
        df=df.drop(index=descartar).copy()
    if df.empty: return df

    mapa=_mapa_actos_movimientos_v266(pd.to_numeric(df["id"],errors="coerce").dropna().astype(int).tolist())
    df["acto_documento_id"]=pd.NA; df["acto_administrativo"]=""
    # Para altas históricas sin vínculo exacto, se usa el acto de la designación solo
    # cuando el CUIL tiene una única designación en ese período (sin adivinar entre paralelas).
    try:
        des=get_designaciones(int(periodo_id))
    except Exception:
        des=pd.DataFrame()
    unicos={}
    if isinstance(des,pd.DataFrame) and not des.empty:
        for clave,g in des.groupby(des.get("cuil",pd.Series(index=des.index,dtype=str)).fillna("").astype(str).map(lambda x:_clave_cuil(x) or str(x).strip())):
            if not clave or g.empty:
                continue
            if len(g)==1:
                unicos[clave]=g.iloc[0].to_dict()
                continue
            # v267: si un docente tiene varias designaciones paralelas pero TODAS fueron
            # vinculadas al mismo acto, ese acto también puede mostrarse con seguridad en
            # sus altas/renovaciones históricas. Si falta un vínculo o hay actos distintos,
            # no se adivina la correspondencia y el movimiento queda pendiente.
            ids_acto = pd.to_numeric(g.get("acto_documento_id", pd.Series(index=g.index,dtype=float)), errors="coerce")
            ids_no_nulos = ids_acto.dropna().astype(int)
            if len(ids_no_nulos) == len(g) and len(ids_no_nulos.unique()) == 1:
                dref = g.iloc[0].to_dict()
                dref["acto_documento_id"] = int(ids_no_nulos.iloc[0])
                etiquetas = [str(x).strip() for x in g.get("acto_administrativo", pd.Series(index=g.index,dtype=str)).fillna("").astype(str).tolist() if str(x).strip()]
                if etiquetas:
                    dref["acto_administrativo"] = etiquetas[0]
                unicos[clave]=dref
    for idx,row in df.iterrows():
        mid=int(row["id"]); tipo=str(row.get("tipo_movimiento") or "")
        act=mapa.get(mid)
        if act:
            df.at[idx,"acto_documento_id"]=int(act.get("documento_id"))
            df.at[idx,"acto_administrativo"]=_etiqueta_acto_v263(act.get("tipo_documento"),act.get("numero"),act.get("dependencia_emisora"))
        elif tipo == "Cambio de número de resolución":
            df.at[idx,"acto_administrativo"]="No corresponde (movimiento histórico de corrección manual)"
        elif tipo in {"Alta de designación", "Renovación automática de designación", "Continuidad automática de designación concursada"}:
            clave=_clave_cuil(row.get("cuil")) or str(row.get("cuil") or "").strip()
            d=unicos.get(clave)
            if d:
                df.at[idx,"acto_documento_id"]=d.get("acto_documento_id",pd.NA)
                df.at[idx,"acto_administrativo"]=str(d.get("acto_administrativo") or "Pendiente de vincular")
            else:
                df.at[idx,"acto_administrativo"]="Pendiente de vincular"
        elif tipo in MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266:
            df.at[idx,"acto_administrativo"]="Pendiente de vincular"
        else:
            df.at[idx,"acto_administrativo"]="No requerido"
    try:
        df = _canonizar_movimientos_designaciones_v269(df, int(periodo_id), preservar_no_designacion=False)
    except Exception:
        pass
    return df
