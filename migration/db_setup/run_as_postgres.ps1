# DEPTIT NEXT - ejecuta un script SQL como postgres SOLO contra deptit_next_dev.
# La contrasena se pide de forma oculta, vive solo en este proceso y nunca se escribe en disco.
# Uso: powershell -ExecutionPolicy Bypass -File run_as_postgres.ps1 -Sql <archivo.sql> -Out <salida.txt> [-ReadOnly]
param(
    [Parameter(Mandatory = $true)][string]$Sql,
    [Parameter(Mandatory = $true)][string]$Out,
    [switch]$ReadOnly
)
$ErrorActionPreference = 'Stop'
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$conn = 'host=127.0.0.1 port=5432 dbname=deptit_next_dev user=postgres application_name=deptit_next_setup'

$secure = Read-Host -AsSecureString "Contrasena de postgres (no se muestra)"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    # Nunca consultar pgpass.conf (contiene una entrada de la base productiva).
    $env:PGPASSFILE = 'C:\DEPTIT_NEXT\migration\db_setup\__no_pgpass__'
    if ($ReadOnly) { $env:PGOPTIONS = '-c default_transaction_read_only=on' } else { Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue }
    $p = Start-Process -FilePath $psql -NoNewWindow -Wait -PassThru `
        -ArgumentList @('-X', '-w', '-v', 'ON_ERROR_STOP=1', '-d', "`"$conn`"", '-f', "`"$Sql`"") `
        -RedirectStandardOutput $Out -RedirectStandardError "$Out.stderr.txt"
    $code = $p.ExitCode
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:PGPASSWORD, Env:PGPASSFILE, Env:PGOPTIONS -ErrorAction SilentlyContinue
}
Write-Host "PSQL_EXIT_CODE = $code"
Write-Host "Salida: $Out"
exit $code
