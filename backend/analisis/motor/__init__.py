"""Motor de lectura certificado de Analisis (generado + entorno).

6A-B3 (higiene de logs): el motor certificado lee con ``pd.read_sql`` sobre la conexion psycopg del request (decision de
equivalencia); pandas emite por CADA lectura el ``UserWarning`` "pandas only supports SQLAlchemy connectable ...", que en
el piloto llenaba stderr (~15.000 lineas con el SQL de cada llamada).  Se silencia SOLO ese mensaje y SOLO cuando lo
origina codigo de este paquete: cualquier otro warning (de este paquete o de otro) se sigue viendo.
"""
import warnings

warnings.filterwarnings("ignore", message=r"pandas only supports SQLAlchemy connectable", category=UserWarning,
                        module=r"analisis\.motor(\..*)?$")
