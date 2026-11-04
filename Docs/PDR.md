# Sistema de Operação Logística Hypera

## Documento Unificado

### Product Requirements Document (PRD)

### Software Architecture Document (SAD)

---

# Changelog

> Histórico de revisões deste documento. Cada linha aponta o que mudou e, quando existe, o Card/Task de origem no Azure DevOps. Adicionar uma linha aqui é parte de toda atualização deste PDR.

| Data | O que mudou |
| --- | --- |
| 28/08/2026 | Seção 3 (Perfis de Usuário) escrita/detalhada, com matriz de permissões, conferida contra `require_perfis()` e `RoleRoute`. |
| 29/08/2026 | Seção 8 (Status Operacional) revisada — Card #33 / Task #53: `Transmitido` deixou de reaproveitar o literal `Processado`, `Cancelado` passou a ser gravado de fato, e o enum ganhou estados granulares de falha. |
| 29/09/2026 | Tela "Confecção" renomeada para **Triagem** no menu (rota e termos internos de status continuam "confecção"). Adicionadas as telas **Histórico** (pedidos com `status_erp` em Pedido Concluído ou Pedido Cancelado) e **Parametrização** (Administrador + Gerente Comercial), com os parâmetros `limitador_de_envio` e `transmissao_automatica_pronto`. Adicionada a ação de **Reenvio de Arquivos** (retorno/espelho/cancelamento), por seleção ou período. Corrigida a lista de Status ERP na seção 8, que estava desatualizada. |

**Em desenvolvimento, ainda fora de `master`** (entram numa próxima revisão, assim que forem commitados): a coluna `pedido.motivo_cancelamento` (motivo real do cancelamento vindo do ERP; já aplicada no banco de desenvolvimento) e a lógica por trás do parâmetro `transmissao_automatica_pronto` (o parâmetro e a tela de Parametrização já existem; falta commitar a automação em si, hoje em `OL_CORE/ol_core/services/import_service.py`).

---

# 1. Visão Geral

## Objetivo

Desenvolver uma plataforma web para gerenciamento operacional dos pedidos recebidos eletronicamente da Hypera, permitindo:

* Recebimento de arquivos via FTP
* Validação automática dos pedidos
* Controle de erros e ocorrências
* Rastreabilidade completa dos arquivos
* Monitoramento operacional
* Geração de arquivos de retorno
* Geração de arquivos espelho
* Geração de arquivos de cancelamento
* Reprocessamento de pedidos
* Integração com ERP
* Dashboards operacionais e gerenciais

---

# 2. Objetivos do Produto

## Operacionais

* Eliminar análise manual de diretórios FTP
* Centralizar informações dos pedidos
* Exibir erros de forma amigável
* Facilitar reprocessamentos
* Monitorar status dos pedidos

## Gerenciais

* Acompanhar faturamento
* Acompanhar volume de pedidos
* Identificar clientes com maior volume
* Monitorar indicadores operacionais
* Acompanhar SLA de processamento

---

# 3. Perfis de Usuário e Controle de Acesso

> Atualizado em 28/08/2026 — permissões consolidadas a partir da regra de negócio (perfil comercial, operacional e T.I.) e conferidas contra a implementação atual. Fonte da verdade no código: `require_perfis()` em `OL_API/app/core/deps.py`, aplicado por endpoint em `OL_API/app/routers/*.py` (`pedidos.py`, `arquivos.py`, `ocorrencias.py`, `erros.py`, `dashboard.py`, `usuarios.py`, `servicos.py`, `industrias.py`); no frontend, o guard `RoleRoute` (`OL_Web/src/components/RoleRoute.tsx`) e o filtro de menu em `Sidebar.tsx`. Os três perfis existem na tabela `perfil` (`Docs/schemas/painel_ol_perfil.sql`) e são vinculados ao usuário via `usuario.id_perfil`. O nome do perfil administrativo no banco e no código é `Administrador`; no dia a dia da empresa esse é o perfil operado pela equipe de T.I.

> Atualizado em 29/09/2026 — a tela de Parametrização (`OL_API/app/routers/parametros.py`) introduziu a primeira exceção de escrita para o Gerente Comercial; ver nota na seção do perfil abaixo.

Todos os perfis autenticam pelo mesmo login (JWT); o que muda entre eles é o que aparece no menu lateral e o que a API autoriza em cada endpoint. Regra geral do produto: o **Operador Logístico executa** as operações (reprocessar, gerar, transmitir, reenviar); o **Gerente Comercial parametriza a política** por trás delas (ex.: ligar/desligar a transmissão automática, ajustar o teto de reenvio) — mas não executa ações operacionais diretamente.

## Gerente Comercial

Acesso majoritariamente de leitura, voltado ao acompanhamento comercial e gerencial — com uma única exceção de escrita: a tela de Parametrização.

Pode:

* Visualizar o Dashboard (cards, gráficos de faturamento, top clientes/produtos)
* Consultar pedidos em Triagem (tela renomeada de "Confecção" no menu; a rota e os termos internos de status continuam usando "confecção")
* Consultar Rastreamento — status de Retorno, Espelho e Cancelamento de pedidos já transmitidos
* Consultar Histórico — pedidos com o fluxo encerrado (`status_erp` = Pedido Concluído ou Pedido Cancelado)
* Consultar Ocorrências e Erros
* Consultar a lista de Arquivos gerados (nome, tipo, hash, situação)
* Exportar para Excel as listas de pedidos em Triagem e de Rastreamento
* Configurar os parâmetros do sistema na tela de Parametrização — hoje, o teto de pedidos por disparo de reenvio (`limitador_de_envio`) e se pedidos "Prontos" são transmitidos automaticamente (`transmissao_automatica_pronto`). É a única ação de escrita do perfil: o Gerente decide a política, quem executa continua sendo o Operador Logístico

Não pode:

* Baixar o conteúdo de um arquivo individual — essa ação exige perfil Operador Logístico ou Administrador; o que o Gerente Comercial exporta é a planilha de dados do pedido, não o arquivo em si
* Reprocessar, gerar retorno/espelho/cancelamento, transmitir ou reenviar pedidos, isolado ou em lote
* Acessar as telas de Usuários, Serviços ou Indústrias

---

## Operador Logístico

Acesso operacional: além de tudo o que o Gerente Comercial consulta, executa as ações do dia a dia sobre pedidos, ocorrências e arquivos — é o perfil que executa; a política por trás da execução é definida pelo Gerente Comercial na Parametrização.

Pode, além do que está liberado para o Gerente Comercial:

* Baixar arquivos individualmente
* Reprocessar um pedido específico, e gerar Retorno, Espelho ou Cancelamento para ele
* Executar operações em lote por período: reprocessar pedidos não transmitidos, gerar retorno, gerar espelho, registrar cancelamento
* Transmitir pedidos que estão em Triagem, individualmente (tela de detalhes do pedido) ou em lote — a transmissão copia os arquivos ainda "Não Transmitidos" para a pasta de entrada da indústria e atualiza o status do pedido; no lote há a opção de excluir da leva os pedidos com ocorrência ainda não resolvida
* Reenviar, por seleção ou por período (tela Histórico), um arquivo já gerado (retorno, espelho ou cancelamento) para a indústria, sem alterar o status do pedido — sujeito ao teto definido em `limitador_de_envio` (Parametrização)
* Baixar o arquivo/XML do pedido gerado para o ERP

Não pode:

* Alterar cadastro de clientes, produtos ou condições comerciais — todas as correções de dados mestres continuam sendo feitas diretamente no ERP, nunca pelo PainelOL
* Acessar as telas de Usuários, Serviços, Indústrias ou Parametrização

---

## Administrador (perfil operado pela equipe de T.I.)

Acesso global ao sistema. Além de todas as ações dos dois perfis acima (incluindo Parametrização, compartilhada com o Gerente Comercial), é o único perfil com acesso às três telas administrativas — protegidas tanto na API quanto no guard de rota do frontend:

* **Usuários** — criar, editar, listar e desativar usuários do sistema, e consultar os perfis disponíveis
* **Serviços** — verificar se os serviços (Importador, Validador, Faturamento, Cancelamento, Monitoramento) estão online com base no heartbeat de cada um, e disparar manualmente a execução de um serviço
* **Indústrias** — cadastrar, editar, consultar e excluir indústrias atendidas, incluindo a configuração das pastas de FTP/integração de cada uma

---

## Matriz de permissões (visão consolidada)

| Recurso / Ação | Gerente Comercial | Operador Logístico | Administrador (T.I.) |
|---|---|---|---|
| Dashboard | Sim | Sim | Sim |
| Triagem / Rastreamento / Histórico (consulta) | Sim | Sim | Sim |
| Ocorrências / Erros (consulta) | Sim | Sim | Sim |
| Lista de Arquivos (consulta) | Sim | Sim | Sim |
| Exportar planilha (Triagem / Rastreamento) | Sim | Sim | Sim |
| Baixar arquivo individual | Não | Sim | Sim |
| Reprocessar / gerar Retorno, Espelho, Cancelamento (por pedido) | Não | Sim | Sim |
| Operações em lote (reprocessar, retorno, espelho, cancelamento) | Não | Sim | Sim |
| Transmitir pedidos (individual ou em lote) | Não | Sim | Sim |
| Reenviar arquivos gerados (retorno/espelho/cancelamento) | Não | Sim | Sim |
| Configurar Parâmetros do sistema | Sim | Não | Sim |
| Gestão de Usuários | Não | Não | Sim |
| Monitoramento de Serviços | Não | Não | Sim |
| Cadastro/edição de Indústrias | Não | Não | Sim |

Correções em clientes, produtos e condições comerciais não são feitas em nenhum perfil dentro do PainelOL — são sempre realizadas no ERP.

---

# 4. Fluxo Operacional

## Recebimento

A indústria envia arquivos TXT via FTP.

Fluxo:

1. Detectar novo arquivo
2. Validar integridade
3. Validar layout
4. Registrar recebimento
5. Armazenar arquivo original
6. Importar dados
7. Iniciar validações

---

## Estrutura dos Arquivos

Registro 1:

* Cabeçalho

Registro 2:

* Informações comerciais

Registro 3:

* Itens do pedido

---

## Validações

### Arquivo

* Estrutura válida
* Layout válido
* Integridade válida

### Cliente

* Cliente existe
* Cliente ativo
* Documentação válida

### Comercial

* Condição existe
* Condição vigente
* Cliente autorizado
* Precificação válida

### Produto

* EAN válido
* Produto ativo
* Estoque disponível
* Quantidade mínima
* Desconto permitido

---

# 5. Sistema de Ocorrências

## Conceito

Uma ocorrência poderá ser associada:

* Ao pedido
* Ao item
* A outra ocorrência

---

## Exemplo

Produto sem estoque

↓

Item cortado

↓

Pedido abaixo do valor mínimo

---

## Severidade

### INFO

Eventos informativos

Exemplo:

* Retorno gerado

### WARNING

Alertas

Exemplo:

* Item cortado

### ERROR

Necessita ação

Exemplo:

* Pedido abaixo do mínimo

### CRITICAL

Bloqueante

Exemplo:

* Cliente não cadastrado

---

# 6. Reprocessamento

Fluxo:

Erro encontrado

↓

Correção realizada no ERP

↓

Operador solicita reprocessamento

↓

Validações executadas novamente

↓

Atualização de status

---

# 7. Rastreabilidade de Arquivos

O arquivo original nunca será alterado.

Toda modificação gerará um novo arquivo.

---

## Tipos de Arquivo

### ORIGINAL

Recebido da indústria

### PROCESSADO

Arquivo validado

### RETORNO

Retorno enviado à indústria

### ESPELHO

Arquivo utilizado para auditoria

### CANCELAMENTO

Arquivo gerado após cancelamento

---

## Metadados

Cada arquivo deverá possuir:

* Nome
* Tipo
* Hash
* Caminho
* Data de criação
* Pedido associado

---

## Reenvio de Arquivos

> Adicionado em 29/09/2026. Fonte da verdade no código: `POST/GET /pedidos/lote/reenviar*` em `OL_API/app/routers/pedidos/lote.py`.

Diferente do Reprocessamento (seção 6), o reenvio não reprocessa nada: ele pega um arquivo **já gerado** (Retorno, Espelho ou Cancelamento) e o reenvia para o FTP da indústria, sem alterar o status do pedido. É usado quando a indústria não recebeu ou perdeu um arquivo que o PainelOL já tinha gerado corretamente.

* Sempre de **um tipo por vez** (retorno, espelho ou cancelamento) — não existe reenvio "de tudo"
* Disparado por seleção de pedidos (ids) ou por período (tela Histórico)
* Sujeito a um teto de pedidos por disparo — parâmetro `limitador_de_envio` (padrão 250, editável na tela de Parametrização), porque o reenvio é síncrono (FTP + cópia por arquivo) e um período muito largo travaria a requisição no meio do lote
* Restrito a Administrador e Operador Logístico

---

# 8. Status Operacionais

## Status Operacional

> Atualizado em 29/08/2026 — validação de QA sobre as correções do Backend no Card #33 / Task #53. Fonte da verdade no código: `TipoStatusOper` em `OL_CORE/ol_core/models/enums/tipo_status_oper.py`.

**Confirmados em uso no `status_operacional` do pedido:**

* Baixado — arquivo do pedido baixado do FTP da indústria
* Importado — pedido validado, um passo antes da transmissão (transição agora automática ao final da importação)
* Verificar — pedido com ao menos uma ocorrência em aberto
* Pronto — pedido validado sem pendências, aguardando transmissão
* Reprocessando — pedido em reprocessamento (marcado no início da operação, tanto individual quanto em lote)
* Transmitindo / Transmitido — marcado antes e depois do arquivo ser depositado na pasta de entrada da indústria
* Falha — falha sistêmica do PainelOL (não é falha do ERP nem do cliente)
* Retorno Gerado / Espelho Gerado / Cancelamento Gerado — estado final de cada operação, gravado no pedido

**Ainda não implementados:** existem no enum, mas nenhuma rotina grava esses valores no `status_operacional` do pedido — Aguardando Retorno, Aguardando Espelho, Aguardando Cancelamento.

**Nota:** os estágios intermediários "Retorno/Espelho/Cancelamento Sendo Gerado" hoje só existem na `situacao` do registro de **Arquivo** (rastreabilidade do arquivo gerado), não no `status_operacional` do **Pedido** — um operador olhando apenas o pedido não vê esse estágio intermediário ainda.

---

## Status ERP

> Corrigido em 29/09/2026 — a lista abaixo estava desatualizada ("Não Enviado / Enviado / Faturado / Cancelado" não existe no código). Fonte da verdade: `TipoStatusErp` em `OL_CORE/ol_core/models/enums/tipo_status_erp.py`.

Status do pedido do ponto de vista comercial/faturamento (coluna `status_erp`, distinta de `status_operacional` acima). Percorre sempre 5 estágios, nesta ordem:

1. **Não Transmitido** — pedido ainda não transmitido para o ERP/Delage
2. **Transmitido** — transmitido, aguardando geração do Retorno
3. **Aguardando Faturamento** — Retorno gerado, aguardando o Espelho (faturamento) ou o Cancelamento
4. **Pedido Concluído** — Espelho gerado, pedido faturado; fluxo encerrado
5. **Pedido Cancelado** — Cancelamento gerado; fluxo encerrado

"Pedido Concluído" e "Pedido Cancelado" são estágios finais: a partir deles o pedido sai da tela de Rastreamento e passa a aparecer só na tela de Histórico (ver seção 16).

---

# 9. Dashboards

## Dashboard Operacional

Indicadores:

* Pedidos Recebidos
* Pedidos Pendentes
* Pedidos Processados
* Pedidos Faturados
* Pedidos Cancelados
* Retornos Gerados

---

## Dashboard Comercial

Indicadores:

* Faturamento Diário
* Faturamento Mensal
* Quantidade de Pedidos
* Quantidade de Itens Faturados
* Ticket Médio
* Top Clientes
* Top Produtos
* Dia de Maior Faturamento

---

# 10. Arquitetura da Solução

## Infraestrutura

Servidor dedicado

Tecnologias:

Frontend:

* React

Backend:

* FastAPI

Serviços:

* Python

Banco Operacional:

* MySQL

ERP:

* SQL Server

Autenticação:

* JWT

Armazenamento:

* File Server

---

# 11. Arquitetura Geral

FTP Hypera

↓

Importador Python

↓

MySQL

↓

Validador Python

↓

Ocorrências

↓

Gerador de Arquivos

↓

File Server

↓

FastAPI

↓

React

↓

Usuário

---

# 12. Integração ERP

Fonte oficial de dados:

SQL Server

Consultas:

* Clientes
* Produtos
* Condições
* Estoque
* Notas Fiscais
* Cancelamentos

A integração ocorrerá através de consultas diretas ao banco.

---

# 13. Serviços da Aplicação

## Serviço Importador

Responsável por:

* Monitorar FTP
* Receber arquivos
* Importar pedidos

Execução:

* Contínua

---

## Serviço Validador

Responsável por:

* Validar pedidos
* Validar itens
* Gerar ocorrências

Execução:

* Contínua

---

## Serviço de Faturamento

Responsável por:

* Consultar emissão de NF
* Atualizar pedidos

Execução:

* A cada 10 minutos

---

## Serviço de Cancelamento

Responsável por:

* Consultar cancelamentos
* Atualizar status

Execução:

* A cada 30 minutos

---

## Serviço de Monitoramento

Responsável por:

* Monitorar serviços
* Detectar falhas
* Enviar alertas

Execução:

* A cada 5 minutos

---

# 14. Estrutura do Banco de Dados

## Industria

Representa fabricantes atendidos.

Exemplos:

* Hypera
* EMS
* Eurofarma
* Aché

---

## Pedido

Representa o pedido importado.

Campos principais:

* id
* id_integracao
* cliente
* condição
* status_operacional
* status_erp
* valor_total

---

## PedidoItem

Itens do pedido.

---

## PedidoOcorrencia

Ocorrências associadas ao pedido.

---

## PedidoItemOcorrencia

Ocorrências associadas aos itens.

---

## Arquivo

Controle de rastreabilidade.

Tipos:

* ORIGINAL
* PROCESSADO
* RETORNO
* ESPELHO
* CANCELAMENTO

---

## PedidoHistorico

Auditoria de eventos.

---

## Usuario

Controle de acesso.

---

## Perfil

Controle de permissões.

---

## ServicoMonitorado

Heartbeat dos serviços.

---

## ConfiguracaoIntegracao

Configuração das integrações FTP.

---

# 15. Estrutura do File Server

\Pedidos

├── Hypera

│   ├── Original

│   ├── Processado

│   ├── Retorno

│   ├── Espelho

│   └── Cancelamento

---

# 16. Estrutura das Telas

## Login

Campos:

* Usuário
* Senha

Autenticação JWT

---

## Dashboard

Sidebar fixa

Cards:

* Pedidos Recebidos
* Pendentes
* Processados
* Faturados
* Cancelados

Gráficos:

* Faturamento
* Pedidos por dia
* Top Clientes
* Top Produtos

---

## Triagem (antes "Confecção")

Pedidos ainda não transmitidos para o ERP (`status_erp` = Não Transmitido).

Filtros: Pedido, Cliente, Status, Data, Indústria.

Ações: Visualizar, Baixar Arquivos, Reprocessar, Transmitir (individual ou em lote, com opção de incluir/excluir pedidos com ocorrência aberta).

---

## Rastreamento

Pedidos já transmitidos, ainda não encerrados (`Transmitido` ou `Aguardando Faturamento`) — mostra o status de Retorno, Espelho e Cancelamento de cada um.

---

## Histórico

Pedidos com o fluxo encerrado (`Pedido Concluído` ou `Pedido Cancelado`).

Filtros: Pedido, Cliente, Nome do arquivo, Indústria, Status, Data (a exportação em Excel exige período).

Ações: Visualizar, Reenviar arquivo gerado (retorno/espelho/cancelamento) por seleção ou por período.

---

## Parametrização

Disponível para Administrador e Gerente Comercial. Lista e permite editar os parâmetros do sistema:

* `limitador_de_envio` — teto de pedidos por disparo de reenvio de arquivos
* `transmissao_automatica_pronto` — liga/desliga a transmissão automática de pedidos que chegam a "Pronto", sem ação humana (a automação em si ainda não está em `master` — ver Changelog)

---

## Detalhes do Pedido

Exibir:

* Dados gerais
* Itens
* Ocorrências
* Arquivos relacionados
* Histórico

---

## Ocorrências

Exibir:

* Severidade
* Motivo
* Pedido
* Item
* Data

---

## Arquivos

Exibir:

* Nome
* Tipo
* Hash
* Caminho
* Data

---

## Usuários

Disponível apenas para administradores. Criar, editar, listar e desativar usuários; consultar perfis disponíveis.

---

## Serviços

Disponível apenas para administradores. Lista os serviços monitorados (Importador, Validador, Faturamento, Cancelamento, Monitoramento) com status online/offline por heartbeat, e permite disparar a execução manual de um serviço.

---

## Indústrias

Disponível apenas para administradores. Cadastro, edição, consulta e exclusão de indústrias atendidas, incluindo a configuração das pastas de FTP/integração.

---

# 17. APIs

## Auth

POST /auth/login

POST /auth/refresh

GET /auth/me

---

## Dashboard

GET /dashboard/cards

GET /dashboard/vendas

GET /dashboard/clientes

GET /dashboard/produtos

---

## Pedidos

GET /pedidos

GET /pedidos/confeccao (tela Triagem)

GET /pedidos/rastreamento

GET /pedidos/historico

GET /pedidos/confeccao/export · /pedidos/rastreamento/export

GET /pedidos/{id}

POST /pedidos/{id}/reprocessar

---

## Ocorrências

GET /ocorrencias

GET /ocorrencias/{id}

---

## Arquivos

GET /arquivos

GET /arquivos/{id}/download

---

## Parametrização

GET /parametros

PUT /parametros/{chave}

---

## Reenvio e Transmissão

GET /pedidos/lote/reenviar/preview

POST /pedidos/lote/reenviar

GET /pedidos/lote/transmitir/preview

POST /pedidos/lote/transmitir

POST /pedidos/{id}/transmitir

---

# 18. Auditoria

Registrar:

* Login
* Reprocessamento
* Geração de arquivos
* Mudança de status
* Faturamento
* Cancelamento

Campos:

* Usuário
* Data
* Hora
* Ação

---

# 19. Monitoramento

Todos os serviços deverão enviar heartbeat.

Caso um serviço fique sem atualização por período configurado:

* Registrar alerta
* Enviar e-mail para equipe de T.I.

---

# 20. Evoluções Futuras

* Suporte a múltiplas indústrias
* Correções operacionais via painel
* Integrações via API
* Dashboard avançado
* Notificações em Teams
* Workflow de aprovação
* Indicadores preditivos

---

# Critérios de Sucesso

* Centralização operacional
* Rastreabilidade completa
* Redução de erros operacionais
* Visibilidade dos pedidos
* Automação do acompanhamento
* Eliminação da análise manual de diretórios FTP
* Escalabilidade para novas indústrias
* Integração transparente com ERP
* Auditoria completa do ciclo de vida dos pedidos

---