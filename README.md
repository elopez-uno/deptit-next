# DEPTIT NEXT — despliegue Docker (servidor de desarrollo y productivo)

Todo el desarrollo vive en **esta carpeta** (`Docker/`, que es la raíz del repositorio git) y es autocontenida: el código de la aplicación
(`backend/`, `frontend/`), el esquema versionado (`migration/`) y todo el empaquetado (`compose.yaml`,
Dockerfiles, init del clúster, certificados, secretos y proxy) están aquí. El contexto de build es esta
misma carpeta: no hay que copiar ni referenciar nada de afuera. La aplicación sigue siendo la misma que
certifica el runbook; lo que cambia es el empaquetado y la operación por servidor.

`docs/` y `ops/` quedan en la raíz del proyecto (documentación histórica y herramientas sin Docker) y no
hacen falta para construir ni operar el stack.

> Nota de estructura: el código se movió dentro de `Docker/` (2026-11). Donde la documentación histórica
> en `docs/` diga `backend/`, `frontend/` o `migration/` desde la raíz del proyecto, ahora corresponde a
> `Docker/backend`, `Docker/frontend` y `Docker/migration`. El runbook de instalación sin Docker no
> aplica a este empaquetado.

```
navegador ──80/443──> proxy (Caddy 2, único público)
                        └──> frontend (Next.js :3000, BFF)      ── red interna 172.28.0.0/24 ──>
                                backend (FastAPI :8001, 1 worker)
                                    ├─> db (PostgreSQL 18, TLS interno, volumen persistente)
                                    └─> volúmenes: documents (raíz documental) y backups (read-only)
docker compose --profile tools run --rm ops …   (backup-set / verify / restore drills / bootstrap / health)
```

| Servicio | Imagen | Público | Notas |
|---|---|---|---|
| `db` | `postgres:18` | No | TLS interno, init automático la primera vez, volumen `db-data` |
| `backend` | `Dockerfile.backend` | No | `serve.py` valida TODA la config antes de levantar uvicorn |
| `frontend` | `Dockerfile.frontend` | No | `next start`; `/api/backend-health` reexpone `/health` del backend |
| `proxy` | `caddy:2` | **80/443** | Único punto de entrada. 3 modos (ver abajo) |
| `ops` (perfil `tools`) | = backend | No | Contenedor efímero con la CLI `python -m operacion` + pg_dump 18 |
| `backend-tests` / `frontend-tests` (perfil `tools`) | = backend/frontend | No | Suites; ver "Tests" |

## Contenido

```
./ (raíz del repositorio)           TODO el proyecto dockerizado (código + empaquetado)
├── backend/                         aplicación FastAPI (código + tests)
├── frontend/                        aplicación Next.js (código + tests)
├── migration/                       esquema versionado (migration/schema lo monta el db)
├── compose.yaml                     stack completo (fuente de verdad de servicios, mounts y healthchecks)
├── .env.example                     INFRAESTRUCTURA (sin secretos): copiar a Docker/.env
├── Dockerfile.backend (+ .dockerignore específico)   imagen runtime y tests del backend
├── Dockerfile.frontend (+ .dockerignore específico) imagen build, runtime y tests del frontend
├── db/initdb/01-init.sh             inicialización UNICA del clúster (roles → base → esquema → grants)
├── proxy/Caddyfile.desarrollo       HTTP plano (servidor de desarrollo)
├── proxy/Caddyfile.produccion       HTTPS con certificado institucional
├── proxy/Caddyfile.produccion-acme  HTTPS con ACME (Let's Encrypt)
├── certs/generar-certificados-db.sh CA + certificado TLS interno del PostgreSQL
├── certs/README.md                  qué generar y dónde instalar el certificado institucional
└── env/                             SECRETOS y plantillas (los .env reales NUNCA van a git)
    ├── .gitignore                   excluye *.env (doble barrera con el .gitignore raíz)
    ├── db.env.example               plantilla → copiar a env/db.env
    ├── backend.desarrollo.env.example  plantilla → copiar a env/backend.env
    ├── backend.produccion.env.example   plantilla → copiar a env/backend.env
    └── ops.env.example              plantilla → copiar a env/ops.env
```

Divisiones que se mantienen igual que el proyecto (fail-closed):

* **Secretos dentro del proyecto pero nunca en git**: `env/{db,backend,ops}.env` con `0600`
  (gitignored por el `.gitignore` raíz y por `env/.gitignore`; los dockerignore excluyen `env/`,
  `certs/` y los patrones `**/.env`/`**/*.key` del contexto de build, así tampoco viajan al daemon ni a
  ninguna imagen).
  Las plantillas `*.example` sí se versionan y solo traen nombres de variables y comentarios.
* **Roles PostgreSQL separados**: `owner` (dueño, solo init/GRANT), `app` (DML sin DDL, la app nunca es
  owner), `backup` (solo lectura), `restore` (CREATEDB solo para drills). La app y el backup no conectan a
  la base de mantenimiento.
* **Gate B11**: `Crear período` exige un backup verificado reciente; el backend monta `backups` read-only.
* **Guardas de `settings.py`**: entorno/base/rol exactos, `sslmode` cifrado fuera de loopback, cookie
  `Secure` y Swagger deshabilitados en producción, documentos en volumen propio.

---

## 1. Prerrequisitos del servidor (Debian)

* `git`, Docker ≥ 27, docker compose v5.6.1.
* **Salida a Internet** para el build: PyPI, `apt.postgresql.org` (cliente 18), npm y
  `next/font/google` (descarga fuentes al compilar). Las imágenes base (`python:3.14-slim`,
  `node:24-slim`, `postgres:18`, `caddy:2`) se bajan de Docker Hub.
* Firewall: solo 80/443 hacia la red institucional (el resto de los servicios no publica puertos).
* El código llega por **git** (`git pull` + `docker compose build` en cada servidor; no hay registro
  privado de imágenes). Si el repositorio aún no está en un remoto: `git init` + push desde la máquina
  de desarrollo es el prerrequisito.

> **Sin Docker en la máquina de desarrollo local no pasa nada**: no hay que construir nada ahí. El
> build ocurre en cada servidor.

## 2. Primer despliegue — servidor de DESARROLLO

### 2.1 Código

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone <url-del-repo> deptit-next && cd deptit-next
```

> El repositorio **es** esta carpeta: al clonar, `compose.yaml` queda directamente en
> `/opt/deptit-next` (no hay subcarpeta `Docker/`). Todos los comandos de esta guía se ejecutan
> desde ahí.

### 2.2 Secretos en `env/` (dentro del proyecto, fuera de git)

```bash
cp env/db.env.example                     env/db.env
cp env/backend.desarrollo.env.example     env/backend.env
cp env/ops.env.example                   env/ops.env
chmod 600 env/db.env env/backend.env env/ops.env
nano env/db.env env/backend.env env/ops.env
```

Generar cada contraseña con **≥ 48 caracteres** y pegarla en cada archivo:

```bash
openssl rand -base64 48      # una por rol: postgres, app, owner, backup, restore
```

Esos tres archivos están excluidos de git (`.gitignore` raíz + `env/.gitignore`) y de los
builds (dockerignores). Al clonar el repo en otro servidor **no existen**: hay que crearlos de nuevo.
Si se prefiere tenerlos fuera del árbol del proyecto, `DEPTIT_ENV_DIR` en `.env` acepta
cualquier ruta (p. ej. `/etc/deptit-next`).

Coincidencias obligatorias (si no coinciden, el stack no arranca: fail-closed):

* `db.env: DEPTIT_APP_DB_USER/DEPTIT_APP_DB_PASSWORD` = `backend.env: DEPTIT_DB_USER/DEPTIT_DB_PASSWORD`.
* `db.env: DEPTIT_BACKUP_DB_*` y `DEPTIT_RESTORE_DB_*` = `ops.env` (mismos nombres).
* Desarrollo exige exactamente base `deptit_next_dev` y rol `deptit_next_app` (guardas de `settings.py`).

### 2.3 Certificado TLS interno del PostgreSQL

```bash
sudo bash certs/generar-certificados-db.sh     # (también funciona invocándolo con sh)
```

Crea `certs/db/` (CA + `server.crt`/`server.key`, owner `999:999` = usuario `postgres` de la
imagen). No se versiona. El backend en desarrollo usa `sslmode=require`; si se quiere
`verify-full`, descomentar las dos líneas en `backend.env` (la CA ya está montada en
`/etc/deptit-next/db-tls`).

### 2.4 `.env` (infraestructura, sin secretos)

```bash
install -m 600 .env.example .env
```

En el servidor de desarrollo no hay que tocar nada: `DEPTIT_ENTORNO=desarrollo`,
`DEPTIT_DB_NAME=deptit_next_dev`, `DEPTIT_PROXY_MODE=desarrollo` (HTTP plano) ya vienen así.

### 2.5 Primer arranque (inicialización de la base)

```bash
docker compose up -d --build
```

**Qué hace el init (solo la primera vez, con el volumen vacío)** — `db/initdb/01-init.sh`:

1. valida entrada: entorno/base/roles exactos, contraseñas ≥ 48, identificadores `[a-z_]`, roles distintos;
2. crea los roles `deptit_next_app` / `_owner` / `_backup` / `_restore` (contraseñas citadas por psql);
3. crea `deptit_next_dev` (owner `_owner`, sin CONNECT para PUBLIC) y el esquema `public` del owner;
4. aplica el esquema `migration/schema/0001_baseline_schema.sql` **verificado por SHA-256 contra el manifest**,
   en UNA transacción y como owner, y comprueba los conteos certificados (58 tablas, 55 secuencias,
   358 restricciones, 193 índices) y que no hay datos;
5. aplica los GRANT del modelo `operacion/preprod.py` y los verifica (DML sin DDL, `b12h_audit_log`
   solo SELECT+INSERT, backup solo lectura, restore sin acceso a la base del entorno).

Si cualquier paso falla, el contenedor `db` muere y **nada queda a medias** (cada fase es atómica).

Verificar:

```bash
docker compose ps                                   # los 4 servicios en healthy
docker compose logs db | grep 'INITDB DEPTIT'       # "INITDB COMPLETO: entorno=desarrollo ..."
```

> **Si el init falla** (p. ej. contraseñas cortas): los scripts de `/docker-entrypoint-initdb.d`
> SOLO corren con el volumen vacío; corregir el motivo y reinicializar:
> ```bash
> docker compose down
> docker volume rm deptit-next_db-data      # OJO: borra la base (recién creada, sin datos)
> docker compose up -d
> ```

### 2.6 Salud de la cadena completa

```bash
docker compose --profile tools run --rm ops python -m operacion health \
  --backend-url http://backend:8001/health --frontend-url http://frontend:3000/api/backend-health
```

(Sin parámetros revisa también volúmenes y backups; salida JSON. El `frontend` solo reporta healthy si
el backend responde, y el proxy solo arranca si el frontend está healthy.)

Prueba por HTTP: `curl -I http://<ip-servidor>/` → 200 desde el proxy.

### 2.7 Primer superadmin (bootstrap)

```bash
docker compose --profile tools run --rm ops python -m operacion bootstrap-superadmin \
  --email superadmin@universidad.edu --execute          # pide la contraseña dos veces
```

La base nace SIN cuentas (el esquema certificado no contiene datos).

### 2.8 Primer backup (evidencia para el gate de "Crear período")

```bash
docker compose --profile tools run --rm ops python -m operacion backup-set
docker compose --profile tools run --rm ops python -m operacion verify-set \
  --manifest /var/backups/deptit-next/sets/deptit_set_desarrollo_<ts>.manifest.json
```

## 3. Servidor de PRODUCCIÓN

Repetir 2.1–2.8 con estas diferencias (todo lo demás es idéntico):

1. **Roles y base propios** — `env/db.env` y `env/backend.env` (plantilla
   `backend.produccion.env.example`):
   * base `deptit_next_prod`, rol de la app `deptit_next_prod_app` (nunca `deptit_next_app`),
     owner/backup/restore `deptit_next_prod_{owner,backup,restore}`.
2. **`.env`**:
   ```dotenv
   DEPTIT_ENTORNO=produccion
   DEPTIT_DB_NAME=deptit_next_prod
   DEPTIT_PROXY_MODE=produccion            # o produccion-acme
   DEPTIT_PROXY_DOMAIN=deptit.universidad.edu
   DEPTIT_ACME_EMAIL=responsable@universidad.edu     # solo con produccion-acme
   ```
3. **HTTPS obligatorio**:
   * `produccion`: copiar el certificado institucional como `certs/proxy/fullchain.pem` +
     `privkey.pem` (ver `certs/README.md`). HSTS activo; el 80 redirige al 443.
   * `produccion-acme`: dominio público apuntando al servidor + puertos 80/443 accesibles desde
     Internet; Caddy obtiene y renueva solo (volumen `caddy-data`).
4. **TLS del db verificado**: `backend.env` ya viene con `DEPTIT_DB_SSLMODE=verify-full` +
   `PGSSLROOTCERT=/etc/deptit-next/db-tls/ca.crt`.
5. Defaults de producción: cookie `Secure`, sin Swagger/OpenAPI, gate B11 no desactivable.
6. **Pasar a producción solo después** de que el servidor de desarrollo pase los tests y el gate
   (§6) — el modelo de decisión del proyecto.

## 4. Operación diaria

### Backups programados (cron del host)

`/etc/cron.d/deptit-next-backup`:

```cron
# backup-set diario 02:00 (base + documentos + verificación) y retention semanal
0 2 * * *  root  cd /opt/deptit-next && docker compose --profile tools run --rm ops python -m operacion backup-set --json-out /var/backups/deptit-next/last-backup.json >> /var/log/deptit-backup.log 2>&1
0 4 * * 0  root  cd /opt/deptit-next && docker compose --profile tools run --rm ops python -m operacion retention --apply >> /var/log/deptit-backup.log 2>&1
```

El JSON queda dentro del volumen `backups` (host: `docker volume inspect deptit-next_backups`).
**Copiar ese volumen fuera del servidor** (rsync/cinta) es parte del modelo B11: un backup que vive
solo en el mismo disco no protege de la pérdida del host.

### Salud y logs

```bash
docker compose ps
docker compose logs -f backend          # (db | frontend | proxy)
docker compose --profile tools run --rm ops python -m operacion health
```

### Inspección puntual de la base (socket local del contenedor, sin contraseña)

```bash
docker compose exec db psql -U postgres -d deptit_next_dev -c '\du deptit_next_*'
docker compose exec db psql -U postgres -d deptit_next_dev -c "select count(*) from app_usuarios;"
```

## 5. Actualización y rollback

```bash
cd /opt/deptit-next && git pull --ff-only
docker compose build
docker compose up -d                   # recrea los contenedores que cambiaron
docker compose --profile tools run --rm ops python -m operacion health
```

* Los datos viven en volúmenes (`db-data`, `documents`, `backups`): `up -d` NO los toca.
* **Rollback de código**: `git checkout <commit-anterior> && docker compose build && docker compose up -d`
  (las imágenes de builds anteriores quedan en el host; con `DEPTIT_IMAGE_TAG` fijado al commit se
  pueden etiquetar y reusar sin rebuild).
* **Rollback de datos**: solo con un restore drill/recovery del backup (§6). Nada borra `db-data`
  salvo borrar el volumen a mano.

## 6. Recuperación (restore drills / DR)

* **Drill periódico** (recomendado, prueba el pipeline sin tocar producción):
  ```bash
  docker compose --profile tools run --rm ops python -m operacion restore-db \
    --manifest /var/backups/deptit-next/<...>/db-<...>.manifest.json --execute \
    --confirm deptit_next_restore_test_<algo>
  ```
  Crea/borra SOLO bases `deptit_next_restore_test_*` (rol `restore`, que no ve la base real).
* **Recuperación real**: `--modo recuperacion` sobre la base del entorno; el procedimiento completo
  (incluyendo `--drop-after` y la verificación posterior) está en `docs/RUNBOOK_DEPTIT_NEXT.md` §restore.
* Documentos: `restore-docs --manifest M --destino DIR` (solo a un directorio inexistente o vacío).

## 7. Tests (perfil `tools`)

```bash
docker compose --profile tools run --rm frontend-tests     # vitest (componentes, sin base)
docker compose --profile tools run --rm backend-tests     # pytest (suite del backend)
```

**Advertencias**:

* Parte de la suite del backend y del frontend depende de **fixtures privados excluidos de la
  entrega** (README_ENTREGA_SISTEMAS.txt; p. ej. `frontend/tests/fixtures/*.json` y los
  `backend/tests/*_fixtures.py`): no es un gate bloqueante; fallas puntuales por eso son esperables.
  Por eso el **build de producción del frontend excluye `tests/`** (`rm -rf tests` en el stage
  `build`): `next build` type-chequea todo lo presente y esos imports romperían el build aunque la
  aplicación compile perfecta. El target `tests` sí los copia.
* `backend-tests` corre SIEMPRE con `entorno=desarrollo` + base `deptit_next_dev`: en el **servidor
  productivo** esa base no existe y esos tests fallan por autenticación — está forzado así para que
  NUNCA se ejecuten contra datos de producción. Correr la suite en el servidor de desarrollo.
* El humo real de producción es `health` + un login manual tras cada actualización.

## 8. Detalles de diseño (por qué es así)

* **`postgres:18` cambió su `VOLUME`**: ahora es `/var/lib/postgresql` (PGDATA quedó en
  `/var/lib/postgresql/18/docker`, gestionado por la imagen). Por eso `db-data` se monta en
  `/var/lib/postgresql`; montar en `/var/lib/postgresql/data` NO persiste.
* **El init usa `SET ROLE` desde `postgres`** por socket (trust local dentro del contenedor): los
  objetos quedan del owner sin usar su contraseña; `CREATE DATABASE` va aparte porque no admite
  transacción.
* **`REVOKE ALL ON DATABASE postgres FROM PUBLIC`**: `initdb` deja `CONNECT` para PUBLIC en TODA
  base, incluida la de mantenimiento. Como el stack no sobreescribe `pg_hba.conf` (la imagen
  autentica cualquier rol con contraseña), el aislamiento se hace por ACL: solo `restore`
  (drills) y el superusuario acceden a `postgres`; la fase 5 del init lo verifica
  (`has_database_privilege` cuenta los grants de PUBLIC).
* **Contraseñas citadas por psql (`:'var'`)**: los bloques `DO $$...$$` no interpolan variables de
  psql, así que los identificadores se validan con regex y los interpola el script; las contraseñas
  entran solo en SQL plano, escapadas por el propio psql.
* **BFF e IP del cliente**: Caddy no confía en ningún proxy anterior → REEMPLAZA `X-Forwarded-For`
  por la IP real; con `DEPTIT_TRUSTED_PROXY_HOPS=1` el BFF toma la última entrada (contando desde la
  derecha), robusto aunque se agregue. El encabezado interno `X-Deptit-Client-Ip` se borra en el proxy y
  el backend solo lo acepta de `DEPTIT_FRONTEND_IP`.
* **Rate limit de `/api/auth/login`**: Caddy OSS no lo trae; lo aplica el backend por cuenta y por IP
  real (documentado en 6A-B4). El límite de body (52 MiB), el timeout (~120 s), la preservación del
  `Host`, el 421 por Host ajeno (`strict_sni_host`) y el `no-store` de `/api/*` sí están en el proxy.
* **`tzdata` en las imágenes**: `settings.apply_timezone` hace `time.tzset()`, que sin
  `/usr/share/zoneinfo` no aplica la zona y en producción el backend se niega a arrancar.
* **`pg_dump` 18 en la imagen del backend** (repo PGDG): el servidor es PostgreSQL 18 y pg_dump no
  puede dumpar una versión mayor que la propia.
* **Healthcheck del db exige que la base exista**: evita que el backend arranque contra un clúster a
  medio inicializar (los scripts de init corren ANTES de que `psql` vea la base del entorno).
* **Dockerignores específicos** (`Dockerfile.backend.dockerignore`, `Dockerfile.frontend.dockerignore`):
  BuildKit los aplica en vez del `.dockerignore` del contexto (que es esta carpeta): cada imagen recibe
  solo lo suyo (backend + migration, o frontend) y nunca `env/` (secretos), `certs/` (claves TLS),
  `**/.env`, `**/*.key`, `node_modules` ni artefactos.
* **Layout autocontenido**: `backend/`, `frontend/` y `migration/` viven en la raíz del repositorio
  (junto a `compose.yaml`, movidos ahí en 2026-11): el contexto de build es `.` y no hay rutas fuera
  de la carpeta. `docs/` y `ops/` quedan fuera del repositorio y no participan del build.
* **`DEPTIT_ENTORNO`/`DEPTIT_DB_NAME` en `.env`**: compose los inyecta a db/backend/ops; no se
  duplican en los archivos de secretos (una sola fuente, sin divergencia).
* **Secretos dentro de `env/`**: cómodos de mantener por servidor, y triple barrera para que
  nunca salgan: `.gitignore` raíz + `env/.gitignore` (no entran a git) y los dockerignore
  específicos (`**/.env` y `**/*.key` no entran al contexto de build). Ojo: `docker compose config`
  resuelve e IMPRIME los valores de los env_file — no pegar esa salida en tickets ni logs.

## 9. Troubleshooting rápido

| Síntoma | Causa probable / acción |
|---|---|
| `db` restart-loop, log `INITDB DEPTIT: ERROR: …` | Falta variable o contraseña corta en `env/db.env`; corregir y reinicializar el volumen (§2.5) |
| `db` healthy pero `backend` muere con `ConfigError` | `backend.env` incompleto o no coincide con `db.env` (rol/contraseña/base); ver el mensaje exacto en `docker compose logs backend` |
| `backend` healthy pero `frontend` unhealthy | El BFF no alcanza al backend: ver `DEPTIT_BACKEND_URL` en `.env` |
| `proxy` no arranca en producción | `DEPTIT_PROXY_DOMAIN` vacío o faltan `certs/proxy/fullchain.pem`/`privkey.pem` |
| `docker compose` reclama `DEPTIT_ENTORNO` | Falta `.env` o le falta esa variable |
| `env file … not found: …/db.env` | Faltan los secretos: crear `env/{db,backend,ops}.env` desde las plantillas (§2.2); si se movió de carpeta, ajustar `DEPTIT_ENV_DIR` en `.env` |
| Init no corre tras corregir | Los scripts solo corren con volumen vacío: `docker compose down && docker volume rm deptit-next_db-data && docker compose up -d` |
| Login bloquea todo | Límite por IP real activo (proxy+HOPS=1 correctos); ver política de lockout en el runbook |
