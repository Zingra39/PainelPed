# OL_TEST — Testes automatizados do OL_CORE

Testes unitários para as etapas de **validacao de negocio** e **geracao de
arquivos** do `OL_CORE` (retorno, espelho e cancelamento), usando `pytest`.

## Por que uma pasta separada, e nao dentro do OL_CORE?

Para manter o pacote `ol_core` (usado tambem pela API e pelos servicos em
producao) livre de dependencia de teste. `OL_TEST` e um projeto separado que
so importa `ol_core` de fora, como qualquer outro consumidor do pacote.

## Como rodar

1. Ative o ambiente virtual que ja tem o `ol_core` instalado (ex.: o venv do
   `OL_API`), ou instale o `ol_core` em modo editavel a partir da raiz do
   projeto:

   ```
   pip install -e OL_CORE
   ```

2. Instale as dependencias de teste:

   ```
   pip install -r OL_TEST/requirements-test.txt
   ```

3. Rode os testes a partir da raiz do projeto (`PainelOL/`):

   ```
   pytest OL_TEST
   ```

   Com mais detalhes de cada teste:

   ```
   pytest OL_TEST -v
   ```

## O que ja esta coberto

- `test_validador.py` — `valida_ean` e `valida_motivo`
- `test_valida_cliente.py` — `valida_clientes`
- `test_valida_condicao.py` — `valida_condicaos`
- `test_valida_pedido.py` — `valida_pedido`
- `test_valida_produto.py` — `valida_produtos`
- `test_conversor.py` — conversao de descontos e leitura do arquivo de pedido
  (`converter_arquivo_closeup`)
- `test_retorno_service.py` — geracao do arquivo de retorno
- `test_espelho_service.py` — geracao do arquivo de espelho (NF)
- `test_cancelamento_service.py` — geracao do arquivo de cancelamento

Nenhum teste toca o MySQL, o SQL Server (ERP) ou o FTP de verdade — todas as
funcoes que fariam essas chamadas sao substituidas com `monkeypatch` (recurso
nativo do pytest, sem dependencia extra). Ver o comentario no topo do
`conftest.py` para a convencao usada.

## Bugs encontrados ao escrever estes testes

Alguns testes estao marcados com `@pytest.mark.xfail(strict=True)`. Eles
descrevem o comportamento **correto esperado**, mas hoje falham porque foi
encontrado um bug real no codigo enquanto o teste era escrito. Isso e
proposital: o teste documenta o problema e vai "acender uma luz vermelha"
(vira `XPASS` com erro) se alguem corrigir o bug e esquecer de tirar o
`xfail` — o que forca a lembrar de atualizar o teste na hora da correcao.

Resumo dos bugs encontrados (ver o `reason=` de cada `xfail` para o detalhe
tecnico e o arquivo/funcao exatos):

1. `retorno_service.py::verificar_itens_pedido` — busca os itens no ERP mas
   nunca faz o `return` deles no caminho de sucesso; hoje sempre devolve
   `None`, o que faz `gerar_retorno_closeup` falhar sempre que chega nessa
   etapa.
2. `retorno_service.py`, `espelho_service.py` e `cancelamento_service.py` —
   as tres funcoes `gerar_*_closeup` referenciam a variavel `id_arquivo`
   dentro do bloco `except`, mas ela so e atribuida na metade do bloco `try`.
   Qualquer erro que aconteca ANTES dessa atribuicao (ex.: pasta nao
   configurada) faz o proprio tratamento de erro quebrar com
   `UnboundLocalError`, mascarando a causa real do problema.
