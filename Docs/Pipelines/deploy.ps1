<#
============================================================================
 PainelOL — script de deploy em produção (RASCUNHO PARA REVISÃO)
----------------------------------------------------------------------------
 Roda no servidor de produção, disparado pelo agente self-hosted do Azure
 Pipelines (pool SITE_POOL) na stage DeployProducao. Ainda não foi testado
 em produção — revisar os pontos marcados com <CONFIRMAR> antes de usar.

 O que ele faz:
   1. Para os serviços NSSM (PainelOL_api, PainelOL_web)
   2. Faz backup versionado da release atual (mantém só as 2 últimas)
   3. Copia os artefatos novos:
        - dist do frontend  -> C:\PainelOL\PainelOL\OL_Web\dist
        - código da API     -> C:\Projetos\PainelOL\OL_API
        - executáveis       -> C:\Projetos\PainelOL\OL_Services
   4. Atualiza a venv da API (ol_core + requirements.txt)
   5. Reinicia os serviços NSSM
   6. Health check em /health
============================================================================
#>

param(
    [Parameter(Mandatory = $true)] [string]$WebArtifact,
    [Parameter(Mandatory = $true)] [string]$CoreWheelArtifact,
    [Parameter(Mandatory = $true)] [string]$ApiArtifact,
    [Parameter(Mandatory = $true)] [string]$ServicesArtifact
)

$ErrorActionPreference = 'Stop'

# --- Caminhos confirmados ---------------------------------------------------
$NssmExe      = 'C:\nssm-2.24\nssm-2.24\win64\nssm.exe'
$ApiService   = 'PainelOL_api'
$WebService   = 'PainelOL_web'          # roda o Caddy, que serve o dist

$WebRoot      = 'C:\PainelOL\PainelOL\OL_Web'
$ApiRoot      = 'C:\Projetos\PainelOL\OL_API'
$ServicesRoot = 'C:\Projetos\PainelOL\OL_Services'

# O uvicorn sobe com --host 192.168.100.133 (parâmetros do NSSM), então não
# escuta em localhost; e a rota de health é a raiz da API, não /health.
$HealthCheckUrl = 'http://192.168.100.133:8080/'

# Backups: uma raiz própria, fora das pastas servidas, com retenção de 2.
$BackupRoot   = 'C:\Projetos\PainelOL\_deploy_backups'
$KeepReleases = 2
$Timestamp    = Get-Date -Format 'yyyy-MM-dd_HHmm'
$ReleaseDir   = Join-Path $BackupRoot $Timestamp

function Invoke-Nssm {
    param(
        [Parameter(Mandatory = $true)] [string[]]$Arguments,
        [int[]]$TolerateExitCodes = @()
    )

    # Escopo local (não vaza para o script): com 'Stop', o 2>&1 abaixo faria o
    # PowerShell 5.1 empacotar cada linha do stderr do nssm num ErrorRecord e
    # lançar erro terminante mesmo quando o nssm retorna exit code 0.
    $ErrorActionPreference = 'Continue'

    $output = & $NssmExe @Arguments 2>&1
    $code = $LASTEXITCODE

    if ($code -ne 0 -and $TolerateExitCodes -notcontains $code) {
        # nssm escreve os erros em UTF-16 quando a saída é redirecionada (por
        # isso o log do pipeline mostra os caracteres intercalados/estranhos);
        # remover os nulos devolve o texto real.
        $msg = (($output | ForEach-Object { "$_" }) -join ' ') -replace "`0", ''
        throw "Comando 'nssm $($Arguments -join ' ')' falhou (exit code $code): $msg"
    }
    return $output
}

function Stop-Services {
    Write-Host "Parando serviços NSSM ($ApiService, $WebService)..."
    # 1062 = ERROR_SERVICE_NOT_ACTIVE. Serviço já parado (deploy anterior que
    # abortou no meio, por exemplo) não é motivo para derrubar o deploy.
    Invoke-Nssm -Arguments @('stop', $ApiService) -TolerateExitCodes 1062 | Out-Null
    Invoke-Nssm -Arguments @('stop', $WebService) -TolerateExitCodes 1062 | Out-Null
    Start-Sleep -Seconds 3
}

function Start-Services {
    Write-Host "Iniciando serviços NSSM..."
    # 1056 = ERROR_SERVICE_ALREADY_RUNNING.
    Invoke-Nssm -Arguments @('start', $ApiService) -TolerateExitCodes 1056 | Out-Null
    Invoke-Nssm -Arguments @('start', $WebService) -TolerateExitCodes 1056 | Out-Null
}

function Backup-CurrentRelease {
    Write-Host "Backup da release atual em $ReleaseDir"
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

    Copy-Item -Path (Join-Path $WebRoot 'dist') `
              -Destination (Join-Path $ReleaseDir 'OL_Web_dist') `
              -Recurse -ErrorAction SilentlyContinue

    Copy-Item -Path $ApiRoot `
              -Destination (Join-Path $ReleaseDir 'OL_API') `
              -Recurse -ErrorAction SilentlyContinue -Exclude 'venv', 'logs', '__pycache__'

    Copy-Item -Path $ServicesRoot `
              -Destination (Join-Path $ReleaseDir 'OL_Services') `
              -Recurse -ErrorAction SilentlyContinue -Exclude 'logs', '__pycache__'

    # Mantém só as $KeepReleases mais recentes
    $old = Get-ChildItem -Path $BackupRoot -Directory |
        Sort-Object Name -Descending |
        Select-Object -Skip $KeepReleases
    foreach ($dir in $old) {
        Write-Host "Removendo backup antigo: $($dir.FullName)"
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Deploy-Web {
    Write-Host "Publicando novo dist do frontend..."
    $target = Join-Path $WebRoot 'dist'
    Remove-Item -Path $target -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path $WebArtifact -Destination $target -Recurse
    # Caddy lê o dist direto do disco (try_files + file_server); não precisa
    # reiniciar o serviço PainelOL_web só por causa do conteúdo — reiniciamos
    # de qualquer forma no fluxo abaixo, pra garantir estado limpo.
}

function Deploy-Api {
    Write-Host "Publicando nova versão da API..."
    Expand-Archive -Path (Join-Path $ApiArtifact '*.zip') -DestinationPath $ApiRoot -Force

    Write-Host "Atualizando venv da API (ol_core + requirements.txt)..."
    $venvPip = Join-Path $ApiRoot 'venv\Scripts\pip.exe'
    $wheel = Get-ChildItem -Path $CoreWheelArtifact -Filter '*.whl' | Select-Object -First 1
    & $venvPip install --upgrade $wheel.FullName
    & $venvPip install -r (Join-Path $ApiRoot 'requirements.txt')
}

function Deploy-Services {
    Write-Host "Publicando novos executáveis dos Services..."
    # <CONFIRMAR> os jobs do TaskTilldawn não têm como ser pausados por aqui —
    # se algum executável estiver em uso no momento do deploy, a cópia falha.
    # Se o TaskTilldawn tiver uma CLI/API para pausar jobs, vale adicionar
    # aqui antes da cópia (Stop) e reativar depois (Start).
    Copy-Item -Path (Join-Path $ServicesArtifact '*') -Destination $ServicesRoot -Recurse -Force
}

function Test-Health {
    Write-Host "Checando saúde da API em $HealthCheckUrl ..."
    try {
        $resp = Invoke-WebRequest -Uri $HealthCheckUrl -UseBasicParsing -TimeoutSec 15
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
            Write-Host "OK — API respondeu $($resp.StatusCode)"
            return $true
        }
    } catch {
        Write-Warning "Health check falhou: $_"
        return $false
    }
    return $false
}

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
try {
    # Checagem de Test-IsAdmin removida em 2026-09-13 — a conta do agente
    # (pool SITE_POOL) já tem as permissões necessárias (NSSM + pastas de
    # deploy) diretamente via ACL/grupo local, sem depender de checagem
    # explícita aqui. Se o deploy falhar por permissão, o próprio comando
    # (nssm/Copy-Item/etc.) vai reportar o erro real.

    Backup-CurrentRelease
    Stop-Services

    Deploy-Web
    Deploy-Api
    Deploy-Services

    Start-Services
    Start-Sleep -Seconds 5

    if (-not (Test-Health)) {
        throw "Health check falhou após o deploy — rollback manual disponível em $ReleaseDir"
    }

    Write-Host "Deploy concluído com sucesso."
}
catch {
    Write-Error "Deploy falhou: $_"
    # Rollback automático não está implementado de propósito — decidir se faz
    # sentido restaurar $ReleaseDir e reiniciar os serviços automaticamente
    # aqui, ou se o time prefere validar manualmente antes de reverter.
    exit 1
}
