from ol_core.models.pedido_item import Pedido_Item


def combinar_itens_sql_e_mysql(
    itens_sql: list[Pedido_Item] | None,
    itens_mysql: list[Pedido_Item] | None,
) -> list[Pedido_Item]:
    """Combina os itens de um pedido vindos do Delage (SQL Server) e do
    MySQL (painel).

    Quando um item existe nas duas fontes, prevalece a versão do SQL Server —
    fonte mais atualizada/oficial. Quando o Delage não tem NENHUM item pro
    pedido (ex.: produto não cadastrado lá, então o Delage nunca criou a linha
    do item), cai integralmente pros dados do MySQL, em vez de devolver lista
    vazia (extraído de retorno_service.verificar_itens_pedido — achado:
    pedido 2026091000328692172P, produto 7896094933071 não cadastrado no
    Delage — e reaproveitado por cancelamento_service pelo mesmo motivo).

    A chave de merge é o EAN, não codigo_produto — produtos não cadastrados
    no Delage caem no fallback codigo_produto=0 e colidiriam entre si se essa
    fosse a chave.
    """
    if not itens_sql:
        return itens_mysql or []

    if not itens_mysql:
        return itens_sql

    eans_sql = {item.ean for item in itens_sql}
    eans_mysql = {item.ean for item in itens_mysql}
    eans_intersecao = eans_sql & eans_mysql

    # Para os itens em comum, fica a versão do SQL Server (fonte mais atualizada/oficial)
    itens_filtrados = [item for item in itens_sql if item.ean in eans_intersecao]

    # Insere também os itens que só existem no MySQL (faltantes na interseção)
    for item_mysql in itens_mysql:
        if item_mysql.ean not in [item.ean for item in itens_filtrados]:
            itens_filtrados.append(item_mysql)

    return itens_filtrados
