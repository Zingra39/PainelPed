# Auditoria — PainelPed

**Data:** 01/11/2026
**Escopo:** OL_API (arquitetura, DDD, SOLID), OL_Web (repetição de código e renderização), OL_CORE e OL_Services (layouts de integração, tempo real), infraestrutura (configuração, deploy, testes, logs).
**Método:** leitura do código-fonte no estado atual do working tree (incluindo alterações ainda não commitadas). As referências estão no formato `arquivo:linha`. As linhas podem deslocar com edições futuras.

---

## Sumário executivo

1. **A arquitetura atual não é DDD.** É um modelo em camadas "router gordo + serviço de orquestração", que se apoia numa biblioteca compartilhada (`ol_core`) com repositórios em SQL cru. A direção de dependência entre pacotes está correta (`ol_core` não conhece a API). O que falta é separação **dentro** da API: regra de negócio, consulta SQL, integração e montagem de resposta convivem nos mesmos arquivos (`routers/pedidos.py` tem 2.235 linhas).
2. **Migrar para DDD é viável e vale a pena para o núcleo de Pedidos.** Esse núcleo tem máquina de estados rica, invariantes de concorrência e integrações externas. **Não** vale para os cadastros (usuários, indústrias, parâmetros, serviços), que são CRUD. A migração deve ser incremental (padrão *strangler*), nunca *big-bang*: o `OL_Services` e cerca de 150 testes dependem das assinaturas atuais.
3. **A ideia de usar o layout como interface está correta, com um ajuste.** A interface deve cobrir só o **formato** do arquivo (ler e escrever texto). A orquestração (transação, status, FTP, histórico) fica comum a todos os layouts. Hoje a lógica do CloseUp está espalhada por cerca de 12 arquivos, e a API ignora a fábrica de layout.
4. **Tempo real é alcançável em etapas.** A primeira entrega (tabela de eventos + SSE + invalidação de cache no front) custa de 3 a 5 dias e já dá o efeito na tela sem trocar os scripts batch.
5. **Há bugs reais com correção pequena,** que devem vir antes de qualquer refatoração (seção 7): status de cancelamento com strings que não existem, pedidos presos em "Reprocessando", arquivo marcado como enviado sem ter sido enviado, coleta FTP que pode apagar pedido, arquivos essenciais fora do git.
6. **No frontend,** dá para eliminar cerca de 750 linhas repetidas. Os problemas de maior impacto não são de desempenho: são **erros de carregamento que aparecem como lista vazia** e a **seleção de itens que sobrevive à troca de página** (bug).

> **Correção feita durante esta auditoria:** o achado 4.1 da seção 7 tinha sido **introduzido por mim** na tarefa anterior (tratamento de `ErroConexaoBanco`). Nas gerações manuais de retorno, espelho e cancelamento, o `except ErroConexaoBanco: raise` passou a vir antes da restauração de status. Se o ERP caísse, o pedido ficava preso em "Sendo Gerado". Já está corrigido em `OL_API/app/services/operacoes.py` (função `_restaurar_status`). Fora isso, esta auditoria não alterou código.

---

## 1. Arquitetura atual do OL_API

### 1.1 Como está hoje

```
OL_Web ──HTTP──► OL_API/app/routers ──► app/models (SQLAlchemy ORM) ──► MySQL
                        │
                        └──► app/services/operacoes.py ──► ol_core (services, validators,
                                                             contexto_* SQL cru) ──► MySQL / ERP / FTP
OL_Services (scripts agendados) ─────────────────────────► ol_core
```

| Camada | Onde | Observação |
|---|---|---|
| Apresentação | `app/routers/*.py`, `app/schemas/*.py` | Routers contêm regra de negócio e consultas |
| Aplicação | `app/services/operacoes.py` (≈760 linhas) | Único serviço; mistura conversão, regra, ERP, FTP, arquivo |
| Domínio | `ol_core/models`, `ol_core/validators`, enums | Modelos anêmicos (sem comportamento); regras em funções soltas |
| Infraestrutura | `app/models.py` (ORM) **e** `ol_core/database/*` (SQL cru) | **Duas pilhas de persistência para as mesmas tabelas** |

### 1.2 Problemas estruturais

| # | Problema | Evidência | Impacto | Prioridade |
|---|---|---|---|---|
| A1 | **Regra de negócio dentro do router** | Máquina de estados da análise em `iniciar_analise` (`pedidos.py:1934`) e `encerrar_analise` (`:2004`, 107 linhas); transição para Transmitido por `setattr` (`:1145`, `:1911`); regra "envio só Pronto" (`:1639`); limite de reenvio (`:1210`); layout CloseUp reconstruído à mão em `gerar_pedido` (`:2180-2205`) | Regra só testável via HTTP. A transmissão manual e a automática (`import_service._transmitir_automaticamente`) implementam sequências de status diferentes | Alta |

| A2 | **Consultas duplicadas entre listagem e export** | Contagem de ocorrências copiada 5× (`pedidos.py:149`, `:289`, `:542`, `:660`, `:767`); filtros de `exportar_confeccao` (`:745`) copiados de `listar_confeccao` (`:256`); `detalhe_completo_pedido` (`:1386`) e `detalhe_pedido` (`:1506`) quase idênticos | **Divergência real:** só a Triagem desconta ocorrências "IGNORADO" (`:301`); Rastreamento e Histórico não. O contador muda entre telas | Alta |

| A3 | **Duas pilhas de persistência** | A API lê pelo ORM, mas `operacoes` grava status por pymysql em outra conexão (`contexto_pedidos.atualizar_status_pedido`). O código já precisa de `db.rollback(); db.refresh(pedido)` para enxergar a mudança (`pedidos.py:2063`) | Sem transação única em operações de várias etapas; leitura desatualizada; schema mantido em dois lugares | Alta |
| A4 | **API ignora a fábrica de layout** | `operacoes.py` chama `gerar_retorno_closeup`, `gerar_espelho_closeup` e `gerar_cancelado_closeup` direto (`:274`, `:361`, `:733`); `_layout()` cai em CLOSEUP para qualquer valor desconhecido (`:45`) | Uma indústria com outro layout geraria arquivo CloseUp **sem nenhum aviso** | Média (Alta antes do 2º layout) |
| A5 | **Modelos duplicados com nomes diferentes** | ORM: `layout`, `pasta_espelho`, `pasta_retorno_espelho`; ol_core: `tipo_layout`, `pasta_nfe`, `pasta_envio_nf`. Tradução manual em `_build_industria` (`operacoes.py:54-118`), que deixa campos de fora | Erros de mapeamento difíceis de ver; `Industria.__init__` cria diretórios a cada requisição (`ol_core/models/industria.py:58`) | Média |

---

## 2. Viabilidade e impacto da migração para DDD

### 2.1 Veredito

| Área | Merece DDD? | Por quê |
|---|---|---|
| **Pedidos** (itens, ocorrências, arquivos gerados, histórico) | **Sim, tático completo** | 2 eixos de status (≈25 operacionais + 5 ERP), invariantes de concorrência (análise, transmitindo, gerando), regras de transição espalhadas hoje |
| **Integração** (ERP, FTP, pastas, layouts) | **Sim, como portas e adaptadores** (*anti-corruption layer*) | Isola o domínio do formato do ERP e da indústria |
| Indústrias | Parcial | CRUD + value object `PastasIndustria` (validação de pastas) |
| Usuários e Perfis | Não | CRUD + política de autorização |
| Parâmetros, Erros, Serviços monitorados | Não | CRUD; basta um repositório fino |

### 2.2 Modelo proposto

**Bounded contexts:** Pedidos (núcleo) · Integração ERP/Indústria · Cadastro de Indústria · Acesso · Parametrização · Monitoramento.

**Agregado `Pedido`** (raiz), com comportamento no lugar de funções soltas:

```python
class Pedido:
    def iniciar_analise(self, usuario, agora) -> None: ...      # hoje no router
    def encerrar_analise(self, usuario, eh_admin, agora) -> None: ...
    def marcar_transmitindo(self, somente_pronto: bool) -> None: ...
    def confirmar_transmissao(self, agora) -> None: ...
    def pode_gerar_retorno_manual(self, agora) -> bool: ...      # hoje operacoes.py:199
    def registrar_falha(self, etapa) -> None: ...
    eventos: list[EventoDominio]                                   # base do tempo real (seção 5)
```

**Value objects:** `NumeroPedidoOL`, `Cnpj` (já existe `ol_core/utils/cnpj.py`), `StatusOperacional`/`StatusErp` com **tabela de transições**, `Observacao` (100 caracteres + autor), `PastasIndustria`, `Periodo` (máx. 366 dias).

**Repositórios:** interface no domínio (`PedidoRepository`), implementação na infraestrutura. As telas de listagem usam **read models** separados (CQRS leve), porque as consultas com subconsulta correlacionada não pertencem ao agregado.

**Estrutura de pastas sugerida** (no `ol_core`, que é compartilhado com o `OL_Services`):

```
ol_core/
  domain/pedido/        pedido.py, status.py, value_objects.py, eventos.py, repositorio.py
  domain/industria/  domain/parametro/
  application/pedido/   transmitir.py, gerar_arquivo.py, reprocessar.py, analise.py, reenviar.py
  infrastructure/       sqlalchemy/, erp/, ftp/, arquivos/
  layouts/              base.py, registro.py, closeup/          (seção 4)
OL_API/app/
  api/routers/  (finos: parse, autorização, exceção→HTTP)
  api/schemas/  api/deps.py  (injeção de dependência)
  queries/      (read models das telas e dos exports)
```

### 2.3 Impacto e risco

| Etapa | Esforço (1 dev) | Risco | O que quebra |
|---|---|---|---|
| Read models e deduplicação de listagens | 3–5 dias | Baixo | Nada (contrato HTTP igual) |
| Agregado Pedido e casos de uso de status | 3–4 semanas | **Alto** | Testes de `OL_TEST/api` que fazem `monkeypatch` em nomes de `operacoes` (dezenas de pontos) |
| Unificar persistência | 3–6 semanas | Alto | `OL_Services` (8 scripts importam funções de `ol_core` diretamente) |
| CRUDs | Sob demanda | Baixo | — |

### 2.4 Migração incremental recomendada

1. **Fixar o comportamento:** testes de caracterização das rotas sem cobertura (lotes de retorno, espelho, cancelamento e reenvio; geração manual; observação).
2. **Lado de leitura:** extrair `app/queries/pedidos.py` (filtros, contagem de ocorrências, mapeadores). Corrige a divergência A2 e remove cerca de 600 linhas.
3. **Domínio puro:** objeto `Pedido` com as regras de transição, testável sem banco.
4. **Portas:** `PedidoRepository`, `ErpGateway`, `EntregaArquivo` (FTP + pasta), `Relogio`. Os adaptadores iniciais só **embrulham** os `contexto_*` atuais, então o `OL_Services` não quebra.
5. **Casos de uso:** um por endpoint de escrita, injetados por `Depends`. Testes trocam `monkeypatch` por *fakes*.
6. **Persistência:** escrita de status na mesma transação; por último, o `OL_Services` passa a chamar os casos de uso.
7. **CRUDs:** só repositório fino, quando forem tocados.

---

## 3. Princípios SOLID

| Princípio | Situação | Evidência | Recomendação | Prioridade |
|---|---|---|---|---|
| **S** — Responsabilidade única | **Violado** | `routers/pedidos.py`: 2.235 linhas, ≈35 endpoints (listagem, export xlsx, lote, operações, análise, layout). Maiores funções: `detalhe_completo_pedido` 116 linhas, `encerrar_analise` 107, `gerar_pedido` 95; no core, `valida_produto` 197, `gerar_espelho_closeup` 181, `gerar_retorno_closeup` 172. `operacoes.py` mistura conversão ORM, validação de pastas, regra, ERP, FTP e formatação de exibição (`mapear_status_arquivo`) | Dividir em `pedidos_consulta`, `pedidos_export`, `pedidos_lote`, `pedidos_operacoes`, `pedidos_analise` + casos de uso | Alta |
| **O** — Aberto/fechado | **Violado** | `if layout == TipoLayout.CLOSEUP.value … else logger.error` 6× em `import_service.py`; regras "de qual status pode X" espalhadas em sets avulsos (`operacoes.py:170-185`, `:318`, `:681`; `pedidos.py:66`, `:463`) | Registro de layouts (seção 4) e tabela única de transições de status | Média |
| **L** — Substituição de Liskov | Sem hierarquias, sem violação clássica | Contrato implícito divergente: `_lote_executar` (`pedidos.py:902`) conta como **falha** um reprocessamento que terminou em "Verificar", porque `reprocessar` devolve `sucesso=False` nesse caso | Tipo `ResultadoOperacao` com status explícito (ok / pendências / erro) | Baixa |
| **I** — Segregação de interfaces | Leve | Objetos ORM completos passados para funções que usam 2 ou 3 campos, forçando *lazy-load*; os testes já usam `SimpleNamespace` como prova | `Protocol` mínimo por caso de uso | Baixa |
| **D** — Inversão de dependência | **Violado** | `operacoes.py` importa funções concretas de ERP, FTP e banco no topo do módulo (`:24-29`); testes dependem de `monkeypatch` por nome; `_OL_SERVICES_BASE` definido 3× com regras diferentes (`arquivos.py:5` ignora `OL_SERVICES_PATH`); CNPJ do distribuidor fixo no código (`operacoes.py:438-440`, `pedidos.py:2188`) mesmo existindo `settings.cnpj_distribuidor` | Injetar portas nos casos de uso via `Depends`; configuração só via `Settings` | Alta |

**Tratamento de erros (transversal):**
- `except Exception: return {"error": str(err)}` em `pedidos.py:188`, `:798`, `:839`, `:897`. Nos exports isso responde **HTTP 200** com JSON quando o cliente espera xlsx, e expõe a mensagem interna.
- Funções `contexto_*` devolvem `None` ou `[]` em erro de SQL. Exemplo: `buscar_ocorrencias_nao_resolvidas` devolve `[]` em erro, e o pedido vira **Pronto** sem validação.
- **Recomendação:** exceções de domínio (`TransicaoInvalida`, `RecursoNaoEncontrado`, `IntegracaoIndisponivel`) e *handler* global, sem try/except em cada endpoint. Prioridade **Alta**.

---

## 4. Layouts de integração: o layout como interface

### 4.1 Onde o CloseUp está "embutido" hoje

| Área | Onde |
|---|---|
| Despacho | `import_service.py`: 6 blocos `if layout == CLOSEUP` |
| Leitura do pedido (posições fixas) | `utils/conversor.py:152-183`; número/data no nome `:114`, `:69-99`; desconto `:27-67` |
| Retorno, espelho, cancelamento, estoque | `retorno_service.py:132-236`, `espelho_service.py:42-109`, `cancelamento_service.py:80-135`, `estoque_service.py:13-17` (nome e CNPJ fixos) |
| Códigos de motivo da indústria | `validators/validador.py:41-60` |
| Observação no arquivo | `utils/transmissao.py:6-8` e `OL_API/app/routers/pedidos.py:1799` |
| Reconstrução do arquivo | `OL_API/app/routers/pedidos.py:2188` |
| Pastas FTP fixas | `retorno_service.py:248`, `espelho_service.py:176`, `cancelamento_service.py:168`, `operacoes.py:438-440`. As colunas `industria.ftp_*` existem mas **não são lidas** |
| Indústria fixa | `OL_Services/coleta_pedidos_ftp.py:33` (`nome == "Hypera"`), `utils/substituir.py:27-33` (regra "vitamina") |
| API pulando a fábrica | `operacoes.py:274`, `:361`, `:733` e o *fallback* silencioso em `:45` |

Hoje, um layout novo mexe em cerca de 12 arquivos, no core e na API. A leitura também não é pura: `converter_arquivo_closeup` consulta o ERP e move arquivo para a pasta de erro, então o formato não pode ser testado isoladamente.

### 4.2 Avaliação da proposta

A ideia está **certa**. O ajuste é **o que** vira interface. Hoje o `LayouFactory` faz três papéis:

| Papel | Hoje | Proposta |
|---|---|---|
| Escolher o layout | `if/elif` repetido | **Registro** `layout_de(industria)` (é a verdadeira *factory*) |
| Orquestrar (transação, status, FTP, histórico) | `importar`, `reprocessar`, `_transmitir_automaticamente`, `*_service.py` | **Comum a todos os layouts** (*Template Method*) |
| Formato do arquivo (ler/escrever texto) | funções `*_closeup` | **A interface `LayoutIntegracao`** (*Strategy*), pura e sem I/O |

```python
# ol_core/layouts/base.py
class Operacao(Enum):
    PEDIDO = "pedido"; RETORNO = "retorno"; ESPELHO = "espelho"
    CANCELAMENTO = "cancelamento"; ESTOQUE = "estoque"

class LayoutIntegracao(ABC):
    tipo: ClassVar[TipoLayout]
    operacoes: ClassVar[frozenset[Operacao]]          # capacidades declaradas

    def suporta(self, op: Operacao) -> bool:
        return op in self.operacoes

    @abstractmethod
    def ler_pedido(self, conteudo: str, nome_arquivo: str) -> PedidoLido: ...   # puro, sem ERP
    @abstractmethod
    def aceita_arquivo(self, nome_arquivo: str) -> bool: ...
    @abstractmethod
    def nome_arquivo(self, op: Operacao, numero_ol: str, cnpj: str) -> str: ...
    def serializar_retorno(self, dados: DadosRetorno) -> str: raise OperacaoNaoSuportada
    def serializar_espelho(self, dados: DadosEspelho) -> str: raise OperacaoNaoSuportada
    def serializar_cancelamento(self, dados: DadosCancelamento) -> str: raise OperacaoNaoSuportada
    def serializar_estoque(self, dados: DadosEstoque) -> str: raise OperacaoNaoSuportada
    def aplicar_observacao(self, conteudo: str, obs: str) -> str: raise OperacaoNaoSuportada
    def codigo_motivo(self, motivo_erp: int, item) -> str: ...

# ol_core/layouts/registro.py
_REGISTRO: dict[TipoLayout, LayoutIntegracao] = {}
def registrar(cls): _REGISTRO[cls.tipo] = cls(); return cls
def layout_de(industria) -> LayoutIntegracao:
    try: return _REGISTRO[industria.tipo_layout]
    except KeyError: raise LayoutNaoSuportado(industria.tipo_layout) from None   # nunca cai em CloseUp

# ol_core/layouts/closeup/layout.py
@registrar
class LayoutCloseup(LayoutIntegracao):
    tipo = TipoLayout.CLOSEUP
    operacoes = frozenset(Operacao)
    ...   # fatiamento de conversor.py e montagem de linhas dos *_service.py

# ol_core/services/geracao_arquivo.py — orquestração única (Template Method)
def gerar(op: Operacao, industria, dados) -> bool:
    layout = layout_de(industria)
    if not layout.suporta(op):
        logger.info(f"{industria.nome}: layout {layout.tipo} não gera {op.value}")
        return False                                   # não é falha: não muda status
    perfil = PERFIS[op]                                # tipo de arquivo, status, pastas, coluna FTP
    id_arq = _registrar_ou_reabrir(perfil, dados)
    try:
        texto = getattr(layout, f"serializar_{op.value}")(dados)
        caminho = _gravar(perfil, layout.nome_arquivo(op, dados.numero_ol, dados.cnpj), texto)
        _entregar(caminho, industria, perfil)          # FTP + pasta; LEVANTA se falhar
        _marcar_sucesso(perfil, id_arq, dados.numero_ol)   # status só depois da entrega
        return True
    except ErroConexaoBanco:
        raise
    except Exception:
        _marcar_falha(perfil, id_arq, dados.numero_ol)
        return False
```

**Operação não suportada por um layout:** a classe declara isso em `operacoes`. O orquestrador pula com log informativo, sem status de falha. A API expõe `suporta()` para a tela esconder o botão correspondente.

**Nome `LayouFactory`:** além do erro de digitação, "Factory" não descreve a classe, que orquestra e não fabrica. Sugestão: `IntegracaoService`, mantendo `LayouFactory` como *alias* deprecado por uma versão (os testes fazem `monkeypatch` nesse nome).

### 4.3 Passos da migração

1. **Golden files:** gerar hoje um arquivo de cada tipo do CloseUp com dados fixos e comparar **byte a byte** nos testes. É a rede de segurança da refatoração.
2. Criar `ol_core/layouts/` e mover o fatiamento e a montagem de linhas sem mudar comportamento (os golden files devem continuar passando).
3. Extrair `gerar()` com `PERFIS` e reduzir os `*_service.py` à coleta de dados.
4. Renomear para `IntegracaoService`, com *alias*.
5. Na API, `operacoes.py` passa a chamar o serviço; remover os caminhos FTP fixos e o *fallback* de `_layout()`; mover a reconstrução de `pedidos.py:2188` para o layout.
6. Ler as pastas FTP de `industria_ftp`.
7. Na coleta FTP, iterar sobre todas as indústrias com FTP cadastrado; a regra "vitamina" vira pré-processamento configurável por indústria.

---

## 5. Sistema em tempo real

### 5.1 Ponto de partida

- O front consulta a cada 15 s (`Confeccao.tsx`, `Rastreamento.tsx`, `PedidoDetail.tsx`) ou 30 s (`Servicos.tsx`). O polling já pausa com a aba em segundo plano.
- O backend são 6 scripts batch agendados. A API dispara scripts com `subprocess.Popen([sys.executable, …])` (`routers/servicos.py:80`), usando o Python da API e não o executável publicado.
- `ol_core/core/variaveis_globais.py:3` consulta o banco **no import**. Num processo contínuo, a lista de indústrias nunca seria recarregada.
- **Vantagem:** quase toda mudança de status passa por `atualizar_status_pedido` e `atualizar_status_erp_pedido`, que é o ponto natural para emitir eventos.

### 5.2 Fases

| Fase | O que | Esforço | Prioridade |
|---|---|---|---|
| **1. Outbox + SSE** | Tabela `evento_dominio` (id, tipo, numero_pedido_ol, payload JSON, criado_em) gravada **na mesma transação** da mudança de status. O `transacao()` atual já garante isso, então o evento só existe se o commit acontecer. Uma tarefa da API lê `WHERE id > :ultimo` a cada 1 s e envia por **SSE**. O front invalida o cache do TanStack Query ao receber o evento | 3–5 dias | Alta |
| **2. Worker contínuo** | Um processo `ol_worker` sob NSSM (já usado no deploy) com APScheduler, no lugar dos 6 executáveis. `max_instances=1` evita execuções sobrepostas. O acionamento manual vira um comando gravado em tabela, no lugar do `Popen` | 1–2 semanas | Média |
| **3. Gatilhos rápidos** | `watchdog` nas pastas locais (a dependência já está em `requirements.txt`, sem uso); FTP consultado a cada 30–60 s (só depois de corrigir B4 da seção 7); ERP a cada 1–2 min | 3–5 dias | Média |

**Por que SSE e não WebSocket:** o fluxo é só do servidor para o navegador. O `EventSource` reconecta sozinho com `Last-Event-ID` (o id da outbox), então nenhum evento se perde, e funciona atrás do Caddy sem configuração especial. Não exige Redis. **Celery/RQ não são recomendados:** o Celery não tem suporte oficial no Windows e os dois exigem broker.

**Do lado do front** (pré-requisito: padronizar as chaves de cache, seção 6.3):

```ts
// montado uma vez no AppLayout
const es = new EventSource(`${BASE_URL}/eventos`)            // autenticação por cookie ou token curto
es.addEventListener('pedido.status', (e) => {
  const { id } = JSON.parse(e.data)
  qc.invalidateQueries({ queryKey: ['pedidos'] })            // listas ativas fazem 1 fetch
  qc.invalidateQueries({ queryKey: ['pedidos', 'detalhe', id] })
})
// nas queries: refetchInterval: conectado ? false : 15_000  (polling vira reserva)
```

Agrupar invalidações (≈300 ms) para não disparar N fetches durante um lote de centenas de pedidos.

**Pré-requisito:** corrigir antes os status gravados antes da entrega (B3). Senão, o tempo real anuncia na hora um sucesso que não aconteceu.

---

## 6. Frontend (OL_Web)

Estado das verificações: `tsc` sem erros; `eslint` com **5 erros** (`AuthContext.tsx:39` e `:67`, `IndustriaDetail.tsx:110`, `Confeccao.tsx:653`, `Rastreamento.tsx:515`).

### 6.1 Repetição de código

| # | Repetição | Onde | Extração proposta | Economia |
|---|---|---|---|---|
| F1 | Banner de mensagem `showMsg` + `setTimeout` | 7 telas (`Confeccao`, `Rastreamento`, `Historico`, `PedidoDetail`, `IndustriaDetail`, `Arquivos`, `Servicos`) | Hook `useFlash()` + `<FlashBanner>` ou `ToastProvider` global. Também corrige timers sem limpeza: uma mensagem apaga a seguinte antes da hora | ≈70 linhas |

| F2 | Painel de resultado de lote | `Confeccao.tsx:445-486` e `:491-537`, `Rastreamento.tsx:357-400`; "relatar lote" 2× em `Historico.tsx` | `<LoteResultadoPanel>` + `resumoLote()` | ≈110 |
| F3 | Barra de ação em lote, seleção, "selecionar todos", `Promise.allSettled` | 3 telas de Pedidos | `useSelecao(idsVisiveis)`, `executarEmLote()`, `<BulkBar>` | ≈80 |
| F4 | Tabela: cabeçalho (classe do `<th>` repetida **40×**), skeleton (9×), estado vazio | Todas as listas. O número de colunas está escrito à mão e **errado** em `Confeccao.tsx:611/620` e `Rastreamento.tsx:477` | `<DataTable columns rows loading error>` ou `<Th>`, `<TableSkeleton>`, `<TableEmpty>` | ≈120 |
| F5 | Formatação de data/moeda | 11 arquivos com `fmtDate` próprio, formatos diferentes com o mesmo nome | `lib/format.ts` (`fmtData`, `fmtDataHora`, `fmtMoeda`) | ≈50 |
| F6 | Cores de status | `StatusBadge.tsx` e `RASTREAMENTO_COLORS` com **cores diferentes** para o mesmo status; listas `PODE_GERAR_*` duplicadas entre `Rastreamento` e `PedidoDetail` | `lib/statusConfig.ts` único | ≈30 |
| F7 | Prévia → confirmação → execução | 4 estados `confirmX` em Confecção, 2 em Rastreamento, 1 em Histórico | Hook `useConfirmacao<T>()` | ≈60 |
| F8 | Botões e inputs; cor `#285BBC` escrita **28×** em 17 arquivos (o token `--brand-blue` existe e não é usado) | Geral | Token `@theme { --color-brand }` + `<Button variant loading>` e `<IconButton aria-label>` | ≈150 |
| F9 | Ligação de filtros com a `FilterBar` | 3 telas de Pedidos | Hook `useListFilters()` que devolve as props da barra | ≈60 |
| F10 | Exportação | `exportConfeccao`/`exportRastreamento` idênticos; Confecção e Rastreamento escondem o motivo do erro (o Histórico usa `apiErrBlob`) | `exportar(url, params, nome)` + `useMutation` com `apiErrBlob` | ≈30 |

**Total estimado: ≈750–800 linhas**, cerca de 30% das 4 páginas de Pedidos.

### 6.2 Renderização

| # | Ponto | Evidência | Recomendação | Prioridade |
|---|---|---|---|---|
| R1 | **Cada tecla na pesquisa redesenha a página inteira** | O rascunho do filtro fica no estado da página (Confecção tem 21 `useState`). Cada tecla redesenha cabeçalho, painéis, 4 diálogos e 20 linhas, e cada linha tem de 2 a 4 `Tooltip` com estado próprio | (1) rascunho dentro da `FilterBar`; (2) separar a página em subcomponentes; (3) `memo` na linha da tabela com callbacks estáveis. `useMemo` em listas de 20 itens **não** compensa | Média |
| R2 | **Tabela vira skeleton a cada troca de página** | Nenhuma lista usa `placeholderData: keepPreviousData` | Adicionar nas 4 listas; parar o polling quando a query estiver em erro | Média |
| R3 | **Um único arquivo JS de 848 KB** | Nenhuma rota usa `React.lazy`; recharts e date-fns vão para todas as telas | `lazy()` por página + `<Suspense>` no `AppLayout` | Média |
| R4 | Valor do `AuthContext` sem memoização | `AuthContext.tsx:61` | `useMemo` + `useCallback`; impacto real pequeno | Baixa |
| R5 | Gráficos com objetos de estilo inline | `MotivosCancelamentoChart.tsx` | Só organizar; não é gargalo | Baixa |
| R6 | Dashboard diz "tempo real", mas não atualiza | `Dashboard.tsx:112`; sem polling nem *refetch on focus* | Polling até a seção 5 ficar pronta | Baixa |

### 6.3 Defeitos e qualidade

| # | Problema | Evidência | Prioridade |
|---|---|---|---|
| Q1 | **Erro de carregamento aparece como lista vazia ou em branco** | Nenhuma lista lê `isError`. Um 503 no Histórico mostra "Nenhum pedido concluído encontrado"; Triagem e Rastreamento ficam em branco; o Dashboard mostra `0` nos cards | **Alta** |

| Q2 | **Seleção sobrevive à troca de página e de filtro** (bug) | `selectedIds` não é limpo. No Histórico, o reenvio em lote manda ids de outra página com um tipo de arquivo que eles podem não ter | **Alta** |
| Q3 | Invalidação de cache aponta para chave inexistente | `PedidoDetail.tsx:148` invalida `['pedidos']`, mas as listas usam `['confeccao']`, `['rastreamento']`, `['historico']`. Voltar à lista mostra status antigo | Média |
| Q4 | Mutações sem tipo de retorno | `api/pedidos.ts:118-166` (`api.post` sem genérico) | Média |
| Q5 | Acessibilidade | Botões só com ícone sem `aria-label`; linhas clicáveis sem acesso por teclado; modais sem `role="dialog"`, foco preso ou Esc | Média |
| Q6 | `ErrorBoundary` envolve a Sidebar | Um erro em qualquer página derruba o menu (`App.tsx:38`) | Baixa |

| Q7 | Código morto | `App.css` do template, imagens não usadas, bloco comentado em `PedidoDetail.tsx:616-656` | Baixa | -> Removido codigo morto

---

## 7. Bugs encontrados (corrigir antes de refatorar)

| # | Bug | Evidência | Efeito | Prioridade |
|---|---|---|---|---|
| B1 | **Status de cancelamento comparado com strings que não existem** | `operacoes.py:697`: `{"faturado", "transmitido", "gerando retorno", "retorno enviado"}`. Desses valores, só "transmitido" existe em `TipoStatusErp` | Pedidos em "Aguardando Faturamento", que o próprio lote de cancelamento seleciona, são **sempre recusados** no cancelamento manual | **Alta** | -> Resolvido, foi ajustado para os valores corretos no enum

| B2 | **Pedido preso em "Reprocessando"** | `executar_reprocessar` grava REPROCESSANDO e pode levantar `ValueError` sem restaurar (`operacoes.py`, ≈`:393-410`); `LayouFactory.reprocessar` captura a exceção e devolve `(False, msg)` sem restaurar (`import_service.py`) | Pedido travado até intervenção manual | **Alta** | -> Inserirdo o valor FALHA_REPROCESSAMENTO do Enum.

| B3 | **Arquivo marcado como enviado sem ter sido enviado** | `envia_arquivo_ftp` engole a exceção (`conectar_ftp.py:55`); o espelho marca ESPELHO e `PROCESSO_CONCLUIDO` **antes** do FTP (`espelho_service.py:170-176`); o cancelamento faz o mesmo (`:162-168`); `envia_arquivo_para_pasta` não sobrescreve arquivo existente (`utils/disparar.py:11`) | Painel e indústria divergem; regeração não chega à indústria | **Alta** | -> Feito o reajuste em Espelho e Cancelamento para trocar o status somente quando o arquivo foi enviado; Refatorado a função de enviar_arquivo_para_pasta, agora o arquivo sobreescreve o ultimo enviado.

| B4 | **Coleta FTP pode apagar pedido não copiado** | `coleta_pedidos_ftp.py:82-87` apaga no FTP mesmo quando a cópia não aconteceu; FTP fora do ar devolve `[]` como se não houvesse arquivo | **Perda de pedido** | **Alta** | -> Adicionado validação no `envia_arquivo_para_pasta`, onde ele retorna um bool informando se o arquivo foi enviado com sucesso.

| B5 | **Arquivos essenciais fora do git** | `OL_Services/ambiente_local.py` e `monta_arquivo_pedido.py` não versionados, mas importados por `importa_pedidos.py:12-13`; os `.spec` do PyInstaller ignorados (`OL_Services/.gitignore:39`), e o `deploy_local.ps1` aborta sem eles | Um clone limpo não executa nem publica | **Alta** | -> Arquivos vão subir no proximo commit

| B6 | Reprocessamento sem transação | `LayouFactory.reprocessar`: marca ocorrências resolvidas, recalcula valor, valida e muda status em conexões separadas | Falha no meio deixa ocorrências antigas resolvidas e nenhuma nova | Alta |

| B7 | Geração manual com corrida | `_bloquear_se_em_geracao` lê e depois grava (*check-then-set*); a transmissão já usa UPDATE condicional atômico | Geração duplicada possível com o serviço automático | Média |

| B8 | Dashboard filtra status que nunca é gravado | `dashboard.py:315` (`status_erp == "Faturado"`) | Indicador sempre zerado | Média | -> Atualizado para "Pedido Concluido" == Faturado

| B9 | Retorno pode falhar com `NameError` | `retorno_service.py:163-165` só define data e hora de processamento se `data_pedido` for `datetime`; o conversor grava texto | Vira "Falha no Retorno" | Média | -> Criado validação de tipo datetime

| B10 | Estoque | Grava e "envia" para a mesma pasta (`estoque_service.py:37,44`); `resgata_estoque` devolve `None` e o código seguinte quebra; `envio_estoque` não está no deploy | Envio de estoque inoperante | Média |

| B11 | `_OL_SERVICES_BASE` inconsistente | `routers/arquivos.py:5` ignora `OL_SERVICES_PATH`, que os outros dois respeitam | Download de arquivo procura no lugar errado em produção | Média |

| B12 | Lote de retorno com N+1 | `pedidos.py:1053` não carrega `arquivos`, mas a regra de atraso acessa a coleção | Uma consulta extra por pedido | Média |

---

## 8. Demais estruturas: configuração, infraestrutura, testes

| # | Ponto | Evidência | Recomendação | Prioridade |
|---|---|---|---|---|
| I1 | **3 arquivos `.env` com chaves duplicadas** | `OL_API/.env`, `OL_CORE/ol_core/.env`, `OL_Services/.env` repetem MYSQL_*, ERP_*, FTP_*; o `ol_core` lê o **próprio** `.env`, não o do processo que o importa | Uma única fonte de configuração (variáveis do serviço NSSM ou `PAINEL_ENV_FILE`); `.env.example` documentado; o core sem `.env` próprio | Alta |

| I2 | `load_dotenv` e consultas no import | `conexao.py`, `conectar_ftp.py` (credenciais congeladas no import), `cancelamento_service.py`, `variaveis_globais.py:3` (consulta ao banco no import) | `ol_core/config.py` com `pydantic-settings`, carregado pelo ponto de entrada; `industrias_ativas()` como função | Alta |

| I3 | Empacotamento do `ol_core` | Não aparece em nenhum `requirements.txt`; testes usam `sys.path.insert`; PyInstaller usa `pathex`; pacote `dotenv==0.9.9` (não oficial) junto com `python-dotenv` | `-e ../OL_CORE` nos requirements; remover `sys.path` | Média |

| I4 | Deploy | Dois destinos de publicação; caminhos e IP fixos em `deploy_local.ps1`; *health check* em `/` não testa o banco | Destino único; endpoint `/health` que teste MySQL e ERP | Média |

| I5 | `.gitignore` | `Docs/` ignorado, mas 41 arquivos dele versionados; `*.txt` ignorado no core | Revisar | Baixa |

| I6 | Logs | `FileHandler("logs/app.log")` relativo ao diretório atual, então há logs em 6 pastas diferentes; sem rotação; vários processos no mesmo arquivo; logger chamado "MatadorOL" | `LOG_DIR` configurável, `RotatingFileHandler` por processo, `numero_pedido_ol` no contexto; avaliar Sentry | Média |

| I7 | **Testes de API não rodam** | `models.py:13` usa `ON UPDATE CURRENT_TIMESTAMP` (só MySQL); o SQLite dos testes rejeita, e os ≈190 testes de `OL_TEST/api` falham no *setup* | `server_default=func.now()` + `onupdate=func.now()`, ou testes de API em MySQL (testcontainers) | **Alta** |

| I8 | Cobertura | Sem teste de rota para auth, usuários, indústrias, parâmetros, dashboard, arquivos, ocorrências e todos os lotes e gerações manuais | Testes de caracterização (pré-requisito da seção 2.4) e de autorização por perfil | Alta |
| I9 | Sem CI | Não há pipeline, lint (ruff) ou checagem de tipos no Python | Pipeline mínima: ruff + pytest unitário + build do front | Média |
| I10 | Números mágicos | `cod_filial = 12328` 6× em `contexto_produto.py`; fornecedores `(10423,10425,33929)` amarram o estoque à Hypera; CNPJ do distribuidor fixo; janelas de 5/5/30 dias nos scripts | Configuração ou colunas de `industria` / tabela `parametro` | Média |
| I11 | Fronteira utils/services | `utils/conversor.py` acessa ERP e disco; `utils/substituir.py` é regra da Hypera; `services/conectar_ftp.py` é infraestrutura | Reorganizar em `layouts/`, `infra/`, `domain/`, `services/` (seção 2.2) | Média |
| I12 | Segurança | Refresh token sem rotação nem revogação; login sem limite de tentativas; senha sem tamanho mínimo; autorização por **nome** do perfil com tolerância a erro de charset (`deps.py`); `require_service_key` sem `hmac.compare_digest`; `bootstrap_db` faz `ALTER TABLE` automático na subida | Rotação de refresh, *rate limit*, autorização por id/código do perfil, Alembic e `db_auto_criar=False` em produção | Média |
| I13 | IO lento dentro da requisição | Todos os endpoints são síncronos; lotes sem teto (só o reenvio tem); `top_produtos` consulta o ERP por linha (até 50 por requisição) | Lotes em fila (o worker da Fase 2); teto em todos os lotes; consulta em lote (`IN (...)`) | Alta |
| I14 | Pendências da tarefa anterior | (a) Rodar no ERP a consulta de validação dos formatos de CNPJ antes do deploy da troca de `dbo.RetiraEspacos_E_CatacteresEspeciais`; (b) `dbo.dv(...)` ainda é usado em WHERE em `contexto_produto.py` e precisa da definição da função para ser removido | Ver resumo da tarefa anterior | Alta (a) / Média (b) |

---

## 9. Roteiro sugerido

| Ordem | Entrega | Itens | Esforço aprox. |
|---|---|---|---|
| 1 | **Correções urgentes** | B1–B5, Q1, Q2, I7 | 1 semana |
| 2 | **Base para mudar com segurança** | Golden files de layout, testes de caracterização (I8), CI mínima (I9), configuração única (I1, I2) | 1–2 semanas |
| 3 | **Layouts** | Seção 4 completa (resolve também A4 e boa parte de B3) | 1–2 semanas |
| 4 | **Leitura da API + front** | Read models (A2), handler global de erros (seção 3), componentes e hooks do front (6.1), `lazy` + `keepPreviousData` (R2, R3) | 1–2 semanas |
| 5 | **Tempo real — Fase 1** | Outbox + SSE + invalidação no front (seção 5) | 3–5 dias |
| 6 | **DDD no núcleo de Pedidos** | Agregado, casos de uso, portas (seção 2.4, passos 3 a 6); B6, B7 | 3–4 semanas |
| 7 | **Tempo real — Fases 2 e 3** | Worker contínuo, watchdog, FTP frequente | 2–3 semanas |
| 8 | Contínuo | Segurança (I12), logs (I6), números mágicos (I10), acessibilidade (Q5) | — |