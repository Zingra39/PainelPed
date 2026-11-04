from ol_core.models.pedido import Pedido
from ol_core.models.pedido_item import Pedido_Item
from ol_core.database.mysql.contexto_pedidos import verificar_ean_pedido_coletado
from ol_core.database.sqlserver.contexto_produto import verifica_estoque_item_pedido, verifica_primeiro_ean_valido, verifica_tipo_ean
from ol_core.database.sqlserver.contexto_cliente import verifica_cliente_na_condicao, verificar_condicao, verificar_item_condicao

def valida_ean(numero_pedido: str, codigo_produto: int, ean: str) -> str:
    """
        Verifica se o EAN possui mais de 13 caracteres e retorna os 13 últimos caracteres.

        Args:
            ean (str): EAN a ser verificado.

        Return:
            str: EAN com 13 caracteres.
    """
    if codigo_produto is None or codigo_produto == 0:
        ean_pedido = "0"

        eans_encontrados = verifica_tipo_ean(codigo_produto)

        if eans_encontrados is None:
            return ean

        for ean in eans_encontrados:
            if not verificar_ean_pedido_coletado(numero_pedido, ean):
                continue

            ean_pedido = ean

        if ean_pedido == "0":
            ean_pedido = verifica_primeiro_ean_valido(codigo_produto)
            
        if ean_pedido is None:
            ean_pedido = ean

        return ean_pedido
    else:
        return ean

def valida_motivo(item: Pedido_Item, pedido: Pedido, cnpj: str) -> int:
    if item.cod_motivo != 0:
        if item.cod_motivo == 8 or item.cod_motivo == 10:
            return 125001
        if item.cod_motivo == 17:
            return 125004
        if item.cod_motivo == 4:
            return 229994
        if item.cod_motivo == 12:
            return 221001
        if item.cod_motivo == 7:
            return 125004

        if item.quantidade_atendida != item.quantidade_solicitada and item.quantidade_atendida > 0:
            return 9

        condicao = verificar_condicao(item.condicao)
        if condicao is None:
            return 221007

        if verifica_estoque_item_pedido(item.codigo_produto):
            return 239004

        data_venciamento_cond = condicao['final']
        if data_venciamento_cond < pedido.data_pedido:
            return 221008

        if condicao['todos_clientes'] == 0:
            if not verifica_cliente_na_condicao(item.condicao, cnpj):
                return 221007

        item_condicao = verificar_item_condicao(item.codigo_produto, item.condicao)

        if item_condicao is None:
            return 125005

        # Se a coluna qtd_desc_1 está preenchida significa que é progressiva
        if item_condicao['qtd_desc_1'] is not None:
            qtd_prog_1 = (item.quantidade_atendida >= item_condicao['qtd_desc_1'] or item.quantidade_solicitada >= item_condicao['qtd_desc_1']) and (item.quantidade_atendida < item_condicao['qtd_desc_2'] or item.quantidade_solicitada <item_condicao['qtd_desc_2'])
            if qtd_prog_1 and item.cod_motivo is not None:
                if item.desconto > item_condicao['desc_1'] and item.cod_motivo is not None:
                    return 125009
            else:
                return 239003

            if item_condicao['qtd_desc_2'] is not None:
                qtd_prog_2 = (item.quantidade_atendida >= item_condicao['qtd_desc_2'] or item.quantidade_solicitada >= item_condicao['qtd_desc_2']) and (item.quantidade_atendida < item_condicao['qtd_desc_3'] or item.quantidade_solicitada <item_condicao['qtd_desc_3'])
                if qtd_prog_2 and item.cod_motivo is not None:
                    if item.desconto > item_condicao['desc_2'] and item.cod_motivo is not None:
                        return 125009

            if item_condicao['qtd_desc_3'] is not None:
                qtd_prog_3 = (item.quantidade_atendida >= item_condicao['qtd_desc_3'] or item.quantidade_solicitada >= item_condicao['qtd_desc_3']) and (item.quantidade_atendida < item_condicao['qtd_desc_4'] or item.quantidade_solicitada <item_condicao['qtd_desc_4'])
                if qtd_prog_3 and item.cod_motivo is not None:
                    if item.desconto > item_condicao['desc_3'] and item.cod_motivo is not None:
                        return 125009

            if item_condicao['qtd_desc_4'] is not None:
                qtd_prog_4 = (item.quantidade_atendida >= item_condicao['qtd_desc_4'] or item.quantidade_solicitada >= item_condicao['qtd_desc_4'])
                if qtd_prog_4 and item.cod_motivo is not None:
                    if item.desconto > item_condicao['desc_4'] and item.cod_motivo is not None:
                        return 125009
        else:
            # verificar se o preco - Pedido é maior que o preco da condicao
            if (item_condicao['preco'] is not None and item_condicao['preco'] > 0) and item.preco > item_condicao['preco']:
                return 125006
            if item.desconto > item_condicao['desconto']:
                return 125009


        if item.cod_motivo == 1:
            return 125005

        if item.preco is None:
            return 225004
            
        if item.preco <=0:
            return 225004

        return 125005
    else:
        if pedido.cod_situacao == 10:
            return 229994
        if pedido.cod_situacao == 11:
            return 229993
        if pedido.cod_situacao == 8:
            return 229996
        if pedido.cod_situacao == 6:
            return 229998
        if pedido.cod_situacao == 9:
            return 239011
        if not pedido.cnpj_cliente:
            return 221001
        else:
            return 0
