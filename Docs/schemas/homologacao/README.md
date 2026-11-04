# Ambiente de homologação — MySQL (painel_ol_homologacao)

Criado a pedido do time em 2026-09-02. Objetivo: ter uma cópia isolada do
banco `painel_ol` (MySQL local) para testar sem risco de mexer nos dados
reais. **O SQL Server / ERP (RX @ 10.1.2.6) não é afetado por nada aqui.**

## Arquivos

- `setup_homologacao.ps1` — script principal. Recria o banco
  `painel_ol_homologacao` do zero e copia estrutura + dados atuais de
  `painel_ol` via `mysqldump | mysql`. Lê as credenciais de `OL_API\.env`
  (não duplica senha em texto novo). Rode sempre que quiser "resetar" a
  homologação com uma cópia fresca da produção local.

- `create_homologacao_schema.sql` — script alternativo, cria só a
  ESTRUTURA (12 tabelas, sem dados) direto de um `mysql -e` ou do
  MySQL Workbench. Use se não tiver `mysqldump` disponível, ou se quiser
  uma homologação vazia em vez de uma cópia dos dados.

## Como rodar (Windows, PowerShell)

```powershell
cd Docs\schemas\homologacao
powershell -ExecutionPolicy Bypass -File setup_homologacao.ps1
```

Requer `mysql.exe` e `mysqldump.exe` no PATH (parte da instalação padrão
do MySQL Server / MySQL Workbench no Windows).

## Apontando a aplicação para a homologação

Cada serviço tem um `.env.homologacao` ao lado do seu `.env` normal
(`OL_API`, `OL_CORE\ol_core`, `OL_Services`), idêntico ao original exceto
por `MYSQL_BANCO=painel_ol_homologacao`. Para testar contra a
homologação, aponte a execução para esse arquivo (ex.: copiando por cima
de `.env` numa cópia local de trabalho, ou ajustando o loader de config
para aceitar `--env-file`) — os `.env` de produção/local não foram
alterados.

⚠️ Os `.env.homologacao` têm as mesmas credenciais de FTP, ERP e Azure dos
originais (não há versão "sandbox" desses serviços externos). Rodar
serviços contra o `.env.homologacao` ainda vai falar com o FTP e o ERP
reais — só o banco MySQL é isolado.
