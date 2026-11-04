from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.conexao import transacao
from pathlib import Path
from decimal import Decimal
from ol_core.core.logger import contexto_pedido, logger
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.titulo import Titulo
from ol_core.models.pedido import Pedido
from ol_core.models.industria import Industria
from ol_core.models.pedido_item import Pedido_Item
from ol_core.validators.valida_pedido import valida_pedido
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.database.mysql.contexto_arquivo import registrar_arquivo, atualizar_situacao_arquivo
from ol_core.layouts import LayoutIntegracao, LayoutNaoSuportado, Operacao, layout_de
from ol_core.utils.conversor import converter_arquivo_para_objeto
from ol_core.utils.transmissao import copiar_arquivo_com_observacao
from ol_core.database.sqlserver.contexto_produto import verifica_quantidade_que_sera_atendida
from ol_core.database.mysql.contexto_ocorrencias import marcar_ocorrencias_resolvidas, buscar_ocorrencias_nao_resolvidas
from ol_core.database.mysql.contexto_parametros import parametro_esta_ativo
from ol_core.database.mysql.contexto_historico import registrar_historico, obter_id_usuario_sistema
from ol_core.database.mysql.contexto_pedidos import atualizar_status_erp_pedido, atualizar_transmitido_em, inserir_pedido, inserir_pedido_itens, atualizar_status_pedido, atualizar_valor_total_pedido

_PARAM_TRANSMISSAO_AUTOMATICA = "transmissao_automatica_pronto"

def _layout_para(industria: Industria, operacao: Operacao, registrar_log: bool = True) -> LayoutIntegracao | None:
    """Layout registrado da indústria, se ele suportar a operação; senão None
    (com log de erro, a não ser que o chamador trate a mensagem)."""
    try:
        layout = layout_de(industria)
    except LayoutNaoSuportado as erro:
        if registrar_log:
            logger.error(str(erro))
        return None
    if not layout.suporta(operacao):
        if registrar_log:
            logger.error(f"Layout {layout.tipo.value} não suporta a operação '{operacao.value}'.")
        return None
    return layout


def calcula_valor_total(pedido_itens: list[Pedido_Item]) -> Decimal:
    valor_total = Decimal("0.00")

    for item in pedido_itens:
        qtd_pretendida = verifica_quantidade_que_sera_atendida(item.codigo_produto)

        if qtd_pretendida is None:
            continue

        qtd_efetiva = min(int(qtd_pretendida), item.quantidade_solicitada)

        if qtd_efetiva <= 0:
            continue

        preco = Decimal(str(item.preco))
        desconto = Decimal(str(item.desconto))
        quantidade = Decimal(str(qtd_efetiva))

        valor_unitario_liquido = preco * (Decimal("1") - (desconto / Decimal("100")))
        valor_total += valor_unitario_liquido * quantidade

    return valor_total.quantize(Decimal("0.01"))

class _FalhaRegistro(Exception):
    """Um passo do registro falhou: levantada DENTRO de `transacao()` para o
    banco desfazer o que já tinha sido gravado (pedido sem itens, itens sem
    arquivo...)."""


class LayouFactory:
    @staticmethod
    def registra_pedido(pedido: Pedido, id_industria: int, arquivo: str) -> int | None:
        """Grava pedido + itens + arquivo numa ÚNICA transação (uma conexão,
        um COMMIT): ou entra tudo, ou nada. Devolve o id do arquivo, ou None se
        algum passo falhou — nesse caso nada fica gravado.

        Chamada de dentro de outra `transacao()` (como em `importar`), entra na
        transação de fora; o None devolvido obriga quem chamou a desfazê-la."""
        try:
            if pedido.numero_pedido_ol is None:
                logger.error(f"Erro ao registrar pedido {pedido}: Número de pedido OL não informado.")
                return None

            # Consulta o ERP item a item: fica FORA da transação para não
            # segurar a conexão do MySQL aberta à toa.
            pedido.valor_total = float(calcula_valor_total(pedido.itens))

            with transacao():
                if inserir_pedido(id_industria, pedido) is None:
                    raise _FalhaRegistro(f"Erro ao registrar pedido {pedido.numero_pedido_ol}")

                if inserir_pedido_itens(pedido.itens) is None:
                    raise _FalhaRegistro(f"Erro ao registrar itens do pedido {pedido.numero_pedido_ol}")

                arquivo_obj = converter_arquivo_para_objeto(pedido.numero_pedido_ol, arquivo)
                id_arquivo = registrar_arquivo(arquivo_obj, TipoStatusOper.IMPORTANDO.value)
                if id_arquivo is None:
                    raise _FalhaRegistro(f"Erro ao registrar arquivo {arquivo}")

            # Devolve o id do arquivo pra quem chamou poder transicionar a situacao
            # dele (Importando Pedido -> Importado) depois que a importação
            # terminar de fato.
            return id_arquivo
        except ErroConexaoBanco:
            raise
        except _FalhaRegistro as falha:
            logger.error(f"{falha} — nada foi gravado (rollback).")
            return None
        except Exception as err:
            logger.error(f"Erro ao registrar pedido {pedido}: {err}")
            return None

    @staticmethod
    def importar(industria: Industria, arquivo: str) -> bool:
        """Importa um arquivo de pedido. Devolve True só se o pedido ficou
        gravado; com False o arquivo NÃO deve sair da pasta de envio (ver
        OL_Services/importa_pedidos.py), senão o pedido se perde.

        Registro, validação (ocorrências) e status rodam numa ÚNICA transação:
        uma falha no meio desfaz tudo, sem pedido pela metade no banco. A
        transmissão automática roda depois do COMMIT — ela copia arquivo para
        a indústria, o que um ROLLBACK não teria como desfazer.

        Raises:
            ErroConexaoBanco: o banco caiu — quem chama deve interromper o lote.
        """
        try:
            id_industria = industria.id_industria

            layout = _layout_para(industria, Operacao.PEDIDO)
            if layout is None:
                return False
            pedido = layout.ler_pedido(industria, arquivo)

            if pedido is None:
                logger.error(f"Erro ao converter arquivo {arquivo} para objeto Pedido.")
                return False

            if pedido.numero_pedido_ol is None:
                logger.error(f"Erro ao importar {arquivo}: Número de pedido OL não informado.")
                return False

            with contexto_pedido(pedido.numero_pedido_ol), transacao():
                id_arquivo = LayouFactory.registra_pedido(pedido, id_industria, arquivo)
                if not id_arquivo:
                    # Sem levantar, a transação de fora commitaria o que o
                    # registro deixou pela metade.
                    raise _FalhaRegistro(f"Registro do pedido {pedido.numero_pedido_ol} falhou")

                valida_pedido(pedido, industria.cond_mae)

                # Pedido sem pendência vai para "Pronto" mesmo com a transmissão
                # automática ligada: se ela falhar (ou o processo cair antes),
                # o pedido já está na fila de triagem.
                pendencias = buscar_ocorrencias_nao_resolvidas(pedido.numero_pedido_ol)
                status = TipoStatusOper.VERIFICAR.value if pendencias else TipoStatusOper.PRONTO.value
                atualizar_status_pedido(pedido.numero_pedido_ol, status)
                atualizar_situacao_arquivo(int(id_arquivo), TipoStatusOper.IMPORTADO.value)

            if not pendencias and parametro_esta_ativo(_PARAM_TRANSMISSAO_AUTOMATICA):
                with contexto_pedido(pedido.numero_pedido_ol):
                    LayouFactory._transmitir_automaticamente(pedido, industria, arquivo)
            return True
        except ErroConexaoBanco:
            raise
        except _FalhaRegistro as falha:
            logger.error(f"{falha} — importação desfeita (rollback).")
            return False
        except Exception as error:
            logger.exception(f"Erro ao importar pedido: {error} — importação desfeita (rollback).")
            return False

    @staticmethod
    def _transmitir_automaticamente(pedido: Pedido, industria: Industria, arquivo: str) -> None:
        """Transmite o pedido direto pra pasta de entrada, sem ação humana —
        caminho automático do parâmetro `transmissao_automatica_pronto`.

        Espelha o que o botão manual "Transmitir" faz (mesmos status
        TRANSMITINDO/TRANSMITIDO, mesma função de cópia), mas nunca deixa o
        pedido travado em "Transmitindo": qualquer falha reverte pra
        "Pronto" (volta pra fila de triagem) e registra o motivo no
        histórico, em vez de propagar a exceção pro chamador — importar()
        precisa seguir seu fluxo normal (marcar o arquivo como IMPORTADO)
        independente do resultado da transmissão automática.
        """
        numero = pedido.numero_pedido_ol
        id_sistema = obter_id_usuario_sistema()
        
        if id_sistema is None:
            raise RuntimeError("ID do sistema não encontrado.")
        
        try:
            if numero is not None:
                atualizar_status_pedido(str(numero), TipoStatusOper.TRANSMITINDO.value)

            if industria.pasta_entrada is None:
                raise RuntimeError(f"Pasta de entrada não configurada para a indústria '{industria.nome}'.")

            industria.pasta_entrada.mkdir(parents=True, exist_ok=True)
            nome_arquivo = Path(arquivo).name
            destino = industria.pasta_entrada / nome_arquivo

            copiar_arquivo_com_observacao(str(arquivo), str(destino), str(pedido.observacao or ""))
            
            if numero is not None:
                atualizar_status_pedido(numero, TipoStatusOper.TRANSMITIDO.value)
                atualizar_status_erp_pedido(numero, TipoStatusErp.TRANSMITIDO.value)
                atualizar_transmitido_em(numero)
                registrar_historico(
                    numero,
                    "Arquivo transmitido",
                    (
                        f"Arquivo '{nome_arquivo}' copiado automaticamente para a pasta de entrada de "
                        f"'{industria.nome}' (parâmetro '{_PARAM_TRANSMISSAO_AUTOMATICA}' ligado)."
                    ),
                    id_sistema,
                )
        except ErroConexaoBanco:
            raise
        except Exception as erro:
            logger.error(f"Erro ao transmitir automaticamente o pedido {numero}: {erro}")
            
            if numero is not None:
                atualizar_status_pedido(str(numero), TipoStatusOper.PRONTO.value)
                
            registrar_historico(
                str(numero),
                "Falha na transmissão automática",
                f"Erro ao transmitir automaticamente: {erro}. Pedido voltou para a fila de triagem (Pronto).",
                id_sistema,
            )

    @staticmethod
    def gerar_retorno(industria: Industria, pedido: Pedido):
        layout = _layout_para(industria, Operacao.RETORNO)
        if layout is not None:
            with contexto_pedido(pedido.numero_pedido_ol):
                layout.gerar_retorno(industria, pedido)

    @staticmethod
    def gerar_espelho(industria: Industria, titulo: Titulo):
        layout = _layout_para(industria, Operacao.ESPELHO)
        if layout is not None:
            with contexto_pedido(titulo.numero_pedido_ol):
                layout.gerar_espelho(industria, titulo)

    @staticmethod
    def gerar_cancelado(industria: Industria, pedido: Pedido):
        layout = _layout_para(industria, Operacao.CANCELAMENTO)
        if layout is not None:
            with contexto_pedido(pedido.numero_pedido_ol):
                layout.gerar_cancelamento(industria, pedido)

    @staticmethod
    def reprocessar(industria: Industria, pedido: Pedido, arquivo: Path) -> tuple[bool, str]:
        with contexto_pedido(pedido.numero_pedido_ol):
            return LayouFactory._reprocessar(industria, pedido, arquivo)

    @staticmethod
    def _reprocessar(industria: Industria, pedido: Pedido, arquivo: Path) -> tuple[bool, str]:
        """Relê o arquivo original do pedido, recalcula o valor e revalida.

        As gravações (resolver as ocorrências antigas, valor_total, novas
        ocorrências e status) acontecem numa única transação (B6 da
        auditoria). Antes cada uma ia numa conexão própria, e uma falha no meio
        deixava as ocorrências antigas resolvidas sem nenhuma nova — o pedido
        parecia limpo sem ter sido validado. Agora, se qualquer etapa falhar,
        nada é gravado e as ocorrências antigas continuam abertas.

        Em qualquer falha o pedido sai de "Reprocessando" (status gravado pelo
        chamador antes de chamar aqui) para "Falha no Reprocessamento", em vez
        de ficar travado.
        """
        numero = pedido.numero_pedido_ol
        try:
            if numero is None:
                logger.error(f"Erro ao reprocessar pedido {pedido}: Número de pedido OL não informado.")
                return False, f"Erro ao reprocessar pedido {pedido}: Número de pedido OL não informado."

            # Leitura do arquivo e cálculo do valor ficam FORA da transação: não
            # gravam nada no MySQL, e assim a transação não fica aberta durante
            # o IO de disco.
            layout = _layout_para(industria, Operacao.PEDIDO, registrar_log=False)
            if layout is None:
                valor = getattr(industria.tipo_layout, "value", industria.tipo_layout)
                return LayouFactory._falha_reprocessamento(numero, f"Layout {valor} não suportado para reprocessamento.")

            # Re-parseia o arquivo em memória (sem re-inserir no banco)
            pedido_relido = layout.ler_pedido(industria, str(arquivo))
            if pedido_relido is None:
                return LayouFactory._falha_reprocessamento(numero, f"Erro ao reprocessar arquivo {arquivo} para objeto Pedido.")
            if pedido_relido.numero_pedido_ol is None:
                return LayouFactory._falha_reprocessamento(numero, f"Erro ao reprocessar pedido {numero}: Número de pedido OL não informado no arquivo.")
            numero_relido = pedido_relido.numero_pedido_ol

            # Calcula valor_total e atribui antes de valida_pedido (que usa pedido.valor_total)
            valor_total = calcula_valor_total(pedido_relido.itens)
            pedido_relido.valor_total = float(valor_total)

            with transacao():
                # Ocorrências anteriores saem como resolvidas — os validadores
                # recriam as que ainda valem. Dentro da transação: se a validação
                # falhar, esta marcação é desfeita junto (rollback).
                marcar_ocorrencias_resolvidas(numero_relido)
                atualizar_valor_total_pedido(numero_relido, valor_total)

                # Validações ANTES de checar pendências — é aqui que as novas
                # ocorrências são registradas (registrar_ocorrencia).
                valida_pedido(pedido_relido, industria.cond_mae)

                # Mesma conexão da transação: enxerga as ocorrências recém-gravadas.
                pendencias = buscar_ocorrencias_nao_resolvidas(numero_relido)
                status = TipoStatusOper.VERIFICAR.value if pendencias else TipoStatusOper.PRONTO.value
                atualizar_status_pedido(numero_relido, status)

            if pendencias:
                return False, f"Reprocessamento concluído com {len(pendencias)} ocorrência(s) pendente(s)."
            return True, "Reprocessamento concluído. Nenhuma pendência encontrada."
        except ErroConexaoBanco:
            raise
        except Exception as err:
            logger.exception(f"Erro ao reprocessar pedido {numero}: {err} — alterações desfeitas (rollback).")
            return LayouFactory._falha_reprocessamento(numero, f"Erro ao reprocessar pedido {numero}: {err}")

    @staticmethod
    def _falha_reprocessamento(numero_pedido_ol: str | None, mensagem: str) -> tuple[bool, str]:
        """Registra a falha e tira o pedido de "Reprocessando" (fora da
        transação desfeita, para o status de falha ficar gravado)."""
        logger.error(mensagem)
        if numero_pedido_ol:
            atualizar_status_pedido(numero_pedido_ol, TipoStatusOper.FALHA_REPROCESSAMENTO.value)
        return False, mensagem

    @staticmethod
    def gerar_estoque(industria: Industria, pedido: Pedido):
        layout = _layout_para(industria, Operacao.ESTOQUE)
        if layout is not None:
            layout.gerar_estoque(industria, pedido)
