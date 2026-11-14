# Certificados TLS del stack (NO versionar: `*.key` y `*.pem` ya estan en .gitignore)

Todo lo que genere este directorio queda fuera del repositorio.

## `db/` — TLS interno de PostgreSQL (obligatorio)

Generar **una vez por servidor**, antes del primer `docker compose up` (funciona igual con `bash` o `sh`):

```bash
sudo bash Docker/certs/generar-certificados-db.sh
# opcional: sudo DEPTIT_DB_IP=172.28.0.2 DEPTIT_CERT_DAYS=825 sh Docker/certs/generar-certificados-db.sh
```

Produce:

| Archivo      | Uso                                                                    | Permisos   |
|--------------|------------------------------------------------------------------------|------------|
| `ca.crt`     | CA propia. `PGSSLROOTCERT` del backend y `pg_dump`/`psql` con verify-full | 0644 root  |
| `ca.key`     | Clave de la CA (permite renovar). Guardar fuera de línea                | 0600 root  |
| `server.crt` | Certificado del servidor (SAN `DNS:db`, `DNS:localhost`, IP de la red)  | 0644 999:999 |
| `server.key` | Clave del servidor                                                     | 0600 999:999 |

El contenedor `db` monta este directorio en `/etc/deptit-next/db-tls` (read-only) y arranca PostgreSQL con
`ssl=on`; `backend` y `ops` lo montan en la misma ruta para verificar el servidor (`verify-full`).

Si se cambia `DEPTIT_DB_IP` en `Docker/.env`, regenerar con `--force` (el SAN debe incluir la IP nueva).

## `proxy/` — certificado institucional (solo `DEPTIT_PROXY_MODE=produccion`)

Copiar aquí el certificado emitido por la universidad, **con estos nombres exactos**:

```
Docker/certs/proxy/fullchain.pem   # cadena completa (servidor + intermedios)
Docker/certs/proxy/privkey.pem     # clave privada
```

Permisos: `privkey.pem` 0600, `fullchain.pem` 0644. El proxy los monta en `/etc/caddy/tls` (read-only).

Con `DEPTIT_PROXY_MODE=produccion-acme` (Let's Encrypt) este directorio no se usa: Caddy pide y renueva los
certificados solo y los guarda en el volumen `caddy-data`.
