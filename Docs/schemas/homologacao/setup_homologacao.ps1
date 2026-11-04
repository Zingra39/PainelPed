<#
    setup_homologacao.ps1

    Cria (ou recria do zero) o banco de homologacao "painel_ol_homologacao"
    no MySQL LOCAL, copiando ESTRUTURA + DADOS ATUAIS do banco "painel_ol"
    via mysqldump.

    NAO toca no SQL Server / ERP (RX @ 10.1.2.6) em nenhum momento — este
    script so fala com o MySQL local (mysql.exe / mysqldump.exe).

    Pre-requisitos:
      - MySQL Server 8.x rodando localmente (o mesmo que a aplicacao usa).
      - Cliente MySQL (mysql.exe e mysqldump.exe) no PATH. Se voce instalou
        o MySQL Server padrao no Windows, eles ficam em algo como:
        C:\Program Files\MySQL\MySQL Server 8.0\bin

    Uso:
      powershell -ExecutionPolicy Bypass -File setup_homologacao.ps1
      powershell -ExecutionPolicy Bypass -File setup_homologacao.ps1 -Force   (pula a confirmacao)

    As credenciais sao lidas de OL_API\.env (nao ficam duplicadas neste
    script). Ajuste -EnvFile se o layout de pastas for diferente.
#>

param(
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\..\..\OL_API\.env"),
    [string]$SourceDb = "painel_ol",
    [string]$TargetDb = "painel_ol_homologacao",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Read-EnvVar {
    param([string]$Path, [string]$Name)
    $line = Select-String -Path $Path -Pattern "^\s*$Name\s*=" | Select-Object -First 1
    if (-not $line) { throw "Variavel $Name nao encontrada em $Path" }
    $value = $line.Line -replace "^\s*$Name\s*=", ""
    return $value.Trim()
}

if (-not (Test-Path $EnvFile)) {
    throw "Arquivo .env nao encontrado em: $EnvFile (informe -EnvFile apontando para o .env correto)"
}

$MysqlHostName = Read-EnvVar -Path $EnvFile -Name "MYSQL_HOST"
$MysqlPort     = Read-EnvVar -Path $EnvFile -Name "MYSQL_PORTA"
$MysqlUser     = Read-EnvVar -Path $EnvFile -Name "MYSQL_USUARIO"
$MysqlPass     = Read-EnvVar -Path $EnvFile -Name "MYSQL_SENHA"

Write-Host "================================================================"
Write-Host " Homologacao MySQL - painel_ol"
Write-Host "================================================================"
Write-Host " Servidor MySQL : $MysqlHostName`:$MysqlPort"
Write-Host " Banco origem   : $SourceDb"
Write-Host " Banco destino  : $TargetDb   (sera recriado do zero)"
Write-Host " SQL Server/ERP : NAO sera tocado por este script"
Write-Host "================================================================"

if (-not $Force) {
    $resp = Read-Host "Confirma a (re)criacao de '$TargetDb' com uma copia de '$SourceDb'? (s/N)"
    if ($resp -notmatch '^[sSyY]') {
        Write-Host "Cancelado pelo usuario."
        exit 0
    }
}

$env:MYSQL_PWD = $MysqlPass
try {
    Write-Host "`n[1/3] Recriando o banco '$TargetDb'..."
    & mysql --host=$MysqlHostName --port=$MysqlPort --user=$MysqlUser -e `
        "DROP DATABASE IF EXISTS $TargetDb; CREATE DATABASE $TargetDb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao (re)criar o banco $TargetDb (mysql exit code $LASTEXITCODE)" }

    Write-Host "[2/3] Copiando estrutura + dados de '$SourceDb' para '$TargetDb' (mysqldump | mysql)..."
    $dumpArgs = @(
        "--host=$MysqlHostName", "--port=$MysqlPort", "--user=$MysqlUser",
        "--single-transaction", "--routines", "--triggers", "--set-gtid-purged=OFF",
        $SourceDb
    )
    $importArgs = @("--host=$MysqlHostName", "--port=$MysqlPort", "--user=$MysqlUser", $TargetDb)

    & mysqldump @dumpArgs | & mysql @importArgs
    if ($LASTEXITCODE -ne 0) { throw "Falha ao copiar dados de $SourceDb para $TargetDb (exit code $LASTEXITCODE)" }

    Write-Host "[3/3] Concluido."
    Write-Host "`nBanco '$TargetDb' criado com estrutura + dados atuais de '$SourceDb'."
    Write-Host "Nada foi alterado no SQL Server / ERP nem no banco '$SourceDb' de origem."
}
finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}
