#!/usr/bin/env bash
# DEPTIT NEXT - genera la CA y el certificado TLS del contenedor PostgreSQL (red interna de compose).
#
# Produce en Docker/certs/db/ (NO se versiona: .gitignore):
#   ca.crt      CA propia del stack. La usan el backend (PGSSLROOTCERT) y psql/pg_dump con verify-full.
#   ca.key      clave de la CA (0600). Guardar fuera del repositorio; permite emitir/renovar.
#   server.crt  certificado del servidor PostgreSQL. SAN: DNS:db, DNS:localhost, IP:127.0.0.1, IP:<DEPTIT_DB_IP>
#   server.key  clave del servidor (0600, owner uid 999 = usuario postgres de la imagen postgres:18)
#
# Uso (en el servidor, desde cualquier directorio; funciona igual con bash o sh):
#   sudo bash Docker/certs/generar-certificados-db.sh                 # 825 dias, IP 172.28.0.2
#   sudo sh Docker/certs/generar-certificados-db.sh                   # idem
#   sudo DEPTIT_DB_IP=172.28.0.2 DEPTIT_CERT_DAYS=825 sh Docker/certs/generar-certificados-db.sh
#   sudo sh Docker/certs/generar-certificados-db.sh --force           # reemplaza los existentes
#
# Requisitos: openssl. Si no se ejecuta como root, imprime los chown/chmod a ejecutar.
# El backend verifica el servidor con DEPTIT_DB_SSLMODE=verify-full + PGSSLROOTCERT=/etc/deptit-next/db-tls/ca.crt
# (montado read-only en backend y ops desde Docker/certs/db).
#
# POSIX puro: no usa bashismos (pipefail, BASH_SOURCE, [[ ]]) para que corra tambien con sh/dash.
set -eu

die() { echo "CERT DB: ERROR: $*" >&2; exit 1; }
note() { echo "CERT DB: $*"; }

command -v openssl >/dev/null 2>&1 || die "falta openssl (apt-get install openssl)"

DEST="$(cd "$(dirname "$0")" && pwd)/db"
DB_IP="${DEPTIT_DB_IP:-172.28.0.2}"
DAYS="${DEPTIT_CERT_DAYS:-825}"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

mkdir -p "$DEST"

if [ "$FORCE" -eq 0 ]; then
    for f in ca.crt ca.key server.crt server.key; do
        [ -e "$DEST/$f" ] && die "$DEST/$f ya existe (usar --force para regenerar TODO el juego)"
    done
fi

case "$DB_IP" in
    *[!0-9.]*|"") die "DEPTIT_DB_IP invalida: '$DB_IP' (IPv4, p.ej. 172.28.0.2)" ;;
esac

note "CA + servidor en $DEST (SAN DNS:db, DNS:localhost, IP:127.0.0.1, IP:$DB_IP; $DAYS dias)"

umask 077
# 1. CA propia del stack (valida 10 anos: firma los certificados del servidor, que se renuevan antes).
openssl req -x509 -newkey rsa:3072 -sha256 -days 3650 -nodes \
    -keyout "$DEST/ca.key" -out "$DEST/ca.crt" \
    -subj "/CN=DEPTIT NEXT DB CA/O=DEPTIT NEXT" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1

# 2. Certificado del servidor firmado por la CA, con SAN para el nombre de servicio `db` y loopback.
openssl req -newkey rsa:3072 -sha256 -nodes \
    -keyout "$DEST/server.key" -out "$DEST/server.csr" \
    -subj "/CN=db/O=DEPTIT NEXT" >/dev/null 2>&1

cat > "$DEST/server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:db,DNS:localhost,IP:127.0.0.1,IP:$DB_IP
EOF

openssl x509 -req -in "$DEST/server.csr" -CA "$DEST/ca.crt" -CAkey "$DEST/ca.key" \
    -CAcreateserial -days "$DAYS" -sha256 -extfile "$DEST/server.ext" \
    -out "$DEST/server.crt" >/dev/null 2>&1

rm -f "$DEST/server.csr" "$DEST/server.ext" "$DEST/ca.srl"
chmod 600 "$DEST/ca.key" "$DEST/server.key"
chmod 644 "$DEST/ca.crt" "$DEST/server.crt"

# 3. Propiedad: PostgreSQL (uid/gid 999 en la imagen postgres:18 Debian) necesita leer server.key.
if [ "$(id -u)" -eq 0 ]; then
    chown 999:999 "$DEST/server.key" "$DEST/server.crt"
    chown 0:0 "$DEST/ca.key" "$DEST/ca.crt"
    chmod 600 "$DEST/server.key"
    note "propietario aplicado: server.* -> 999:999 (postgres), ca.* -> root"
else
    note "AVISO: no se ejecuto como root. Ejecutar:"
    note "  sudo chown 999:999 '$DEST/server.key' '$DEST/server.crt' && sudo chmod 600 '$DEST/server.key'"
    note "  sudo chown 0:0 '$DEST/ca.key' '$DEST/ca.crt'"
fi

note "verificacion del certificado:"
openssl verify -CAfile "$DEST/ca.crt" "$DEST/server.crt"
openssl x509 -in "$DEST/server.crt" -noout -subject -dates -ext subjectAltName

note "listo. El backend puede usar DEPTIT_DB_SSLMODE=verify-full con PGSSLROOTCERT=/etc/deptit-next/db-tls/ca.crt"
