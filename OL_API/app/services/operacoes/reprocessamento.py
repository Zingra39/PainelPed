"""Reprocessamento manual de um pedido (reimportação e revalidação do arquivo)."""
from ol_core.database.mysql.contexto_pedidos import atualizar_status_pedido
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.services.import_service import LayouFactory

from .conversao import _build_industria, _build_pedido
from .historico import _log


def executar_reprocessar(pedido_db, id_usuario: int) -> dict:
    # Marca o pedido como "Reprocessando" assim que a operação começa — antes
    # disso não havia nenhum sinal visível de reprocessamento em andamento,
    # só o resultado final (Verificar/Pronto).
    if pedido_db.numero_pedido_ol:
        atualizar_status_pedido(pedido_db.numero_pedido_ol, TipoStatusOper.REPROCESSANDO.value)

    arquivo_record = next(
        (a for a in pedido_db.arquivos if a.tipo == TipoArquivo.PEDIDO.value), None
    )

    if not arquivo_record or not arquivo_record.nome:
        atualizar_status_pedido(pedido_db.numero_pedido_ol, TipoStatusOper.FALHA_REPROCESSAMENTO.value)
        raise ValueError("Arquivo original do pedido não registrado no banco.")

    industria_db = pedido_db.industria
    if not industria_db:
        atualizar_status_pedido(pedido_db.numero_pedido_ol, TipoStatusOper.FALHA_REPROCESSAMENTO.value)
        raise ValueError("Indústria do pedido não encontrada.")

    industria_ol = _build_industria(industria_db)
    pedido_ol    = _build_pedido(pedido_db)

    arquivo_path = industria_ol.pasta_backup / arquivo_record.nome
    if not arquivo_path.exists():
        atualizar_status_pedido(pedido_db.numero_pedido_ol, TipoStatusOper.FALHA_REPROCESSAMENTO.value)
        raise ValueError(
            f"Arquivo '{arquivo_record.nome}' não encontrado na pasta de backup. "
            "Verifique se o backup do pedido está disponível."
        )

    sucesso, mensagem = LayouFactory.reprocessar(industria_ol, pedido_ol, arquivo_path)

    _log(
        pedido_db.numero_pedido_ol,
        "Reprocessamento executado",
        f"Reprocessamento via painel pelo usuário {id_usuario}. {mensagem}",
        id_usuario,
    )

    return {"sucesso": sucesso, "mensagem": mensagem}
