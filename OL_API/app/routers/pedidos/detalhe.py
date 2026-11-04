"""Detalhe de um pedido (GET /pedidos/{id} e /pedidos/{id}/detalhes).

Fica num módulo próprio, incluído por ÚLTIMO no router de /pedidos: o
`GET /{id}` casaria com qualquer caminho de um segmento (ex.: /confeccao) se
fosse registrado antes das listagens."""
from datetime import datetime
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.models import Pedido, PedidoHistorico, PedidoItem
from app.schemas.pedido import (
    ArquivoResumo,
    HistoricoResumo,
    ItemOcorrenciaResumo,
    OcorrenciaResumo,
    PedidoDetail,
    PedidoDetalheCompleto,
    PedidoItemSchema,
    TituloSchema,
)
from app.services import operacoes
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger

from ._comum import _TODOS, _analise_campos, _envio_somente_pronto

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def _deduplicar_ocorrencias(ocorrencias):
    """Mantém só a ocorrência mais recente por texto de `descricao`.

    Reprocessamentos sucessivos podem detectar o MESMO problema mais de uma
    vez (ex.: um registrado e resolvido, e o mesmo problema reaparecendo
    depois num reprocessamento posterior) — cada detecção vira uma linha
    nova em `pedido_ocorrencia`/`pedido_item_ocorrencia`, o que é correto
    pro histórico, mas fazia a tela de detalhes do pedido exibir a mesma
    mensagem repetida várias vezes. Aqui só filtramos o que é EXIBIDO,
    mantendo a linha mais recente de cada mensagem — nenhuma linha é
    apagada do banco."""
    mais_recente_por_descricao: dict[str, object] = {}
    for oc in ocorrencias:
        atual = mais_recente_por_descricao.get(oc.descricao)
        if atual is None or (oc.criado_em or datetime.min) >= (atual.criado_em or datetime.min):
            mais_recente_por_descricao[oc.descricao] = oc
    return [oc for oc in ocorrencias if oc is mais_recente_por_descricao.get(oc.descricao)]


@router.get("/{id}/detalhes", response_model=PedidoDetalheCompleto)
def detalhe_completo_pedido(id: int, db: Session = Depends(get_db), _user=Depends(_TODOS),):
    pedido = (
        db.query(Pedido)
        .options(
            joinedload(Pedido.industria),
            joinedload(Pedido.usuario_analise),
            joinedload(Pedido.usuario_analisou),
            selectinload(Pedido.itens).selectinload(PedidoItem.ocorrencias),
            selectinload(Pedido.ocorrencias),
            selectinload(Pedido.arquivos),
            selectinload(Pedido.historico).joinedload(PedidoHistorico.usuario),
        )
        .filter(Pedido.id == id)
        .first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    try:
        itens = [
            PedidoItemSchema(
                id=it.id,
                ean=it.ean,
                codigo_produto_erp=it.codigo_produto_erp,
                quantidade_solicitada=it.quantidade_solicitada,
                quantidade_atendida=it.quantidade_atendida,
                preco=it.preco,
                desconto=it.desconto,
                cod_motivo=it.cod_motivo,
                id_cond=it.id_cond,
                status=it.status,
                ocorrencias=[
                    ItemOcorrenciaResumo(
                        id=oc.id,
                        severidade=oc.severidade,
                        codigo=oc.codigo,
                        descricao=oc.descricao,
                        resolvido=bool(oc.resolvido),
                        criado_em=oc.criado_em,
                    )
                    for oc in _deduplicar_ocorrencias(it.ocorrencias)
                ],
            )
            for it in pedido.itens
        ]

        ocorrencias = [
            OcorrenciaResumo(
                id=oc.id,
                severidade=oc.severidade,
                codigo=oc.codigo,
                descricao=oc.descricao,
                resolvido=bool(oc.resolvido),
                criado_em=oc.criado_em,
            )
            for oc in _deduplicar_ocorrencias(pedido.ocorrencias)
        ]

        arquivos = [
            ArquivoResumo(
                id=a.id,
                numero_pedido_ol=a.numero_pedido_ol,
                nome=a.nome,
                tipo=a.tipo,
                hash_md5=a.hash_md5,
                situacao=a.situacao,
                criado_em=a.criado_em,
            )
            for a in pedido.arquivos
        ]

        historico = [
            HistoricoResumo(
                id=h.id,
                acao=h.acao,
                detalhe=h.detalhe,
                usuario_nome=h.usuario.nome if h.usuario else None,
                criado_em=h.criado_em,
            )
            for h in sorted(pedido.historico, key=lambda x: x.criado_em or datetime.min, reverse=True)
        ]

        titulo_dict = operacoes.buscar_titulo_erp(pedido.nome_arquivo)
        titulo = TituloSchema(**titulo_dict) if titulo_dict else None

        return PedidoDetalheCompleto(
            id=cast(int, pedido.id),
            numero_pedido_ol=cast(str, pedido.numero_pedido_ol),
            nome_arquivo=cast(str, pedido.nome_arquivo),
            codigo_interno_erp=cast(int, pedido.codigo_interno_erp),
            cnpj_cliente=cast(str, pedido.cnpj_cliente),
            condicao=cast(str, pedido.condicao),
            observacao=cast(str, pedido.observacao),
            status_operacional=cast(str, pedido.status_operacional),
            status_erp=cast(str, pedido.status_erp),
            valor_total=cast(Decimal, pedido.valor_total),
            data_pedido=cast(datetime, pedido.data_pedido),
            criado_em=cast(datetime, pedido.criado_em),
            atualizado_em=cast(datetime, pedido.atualizado_em),
            industria_nome=pedido.industria.nome if pedido.industria else None,
            itens=itens,
            ocorrencias=ocorrencias,
            arquivos=arquivos,
            historico=historico,
            titulo=titulo,
            retorno_manual_liberado=operacoes.retorno_manual_liberado_por_atraso(pedido),
            **operacoes.acoes_de_geracao_manual(pedido),
            envio_somente_pronto=_envio_somente_pronto(db),
            **_analise_campos(pedido),
        )
    except HTTPException:
        raise
    except ErroConexaoBanco:
        raise
    except Exception:
        logger.exception(f"Erro ao carregar detalhes do pedido {id} ({pedido.numero_pedido_ol}).")
        raise HTTPException(status_code=500, detail="Erro ao carregar detalhes do pedido.")


@router.get("/{id}", response_model=PedidoDetail)
def detalhe_pedido(id: int, db: Session = Depends(get_db), _user=Depends(_TODOS),):
    try:
        pedido = (
            db.query(Pedido)
            .options(
                joinedload(Pedido.industria),
                joinedload(Pedido.usuario_analise),
                joinedload(Pedido.usuario_analisou),
                selectinload(Pedido.itens).selectinload(PedidoItem.ocorrencias),
                selectinload(Pedido.ocorrencias),
                selectinload(Pedido.arquivos),
                selectinload(Pedido.historico).joinedload(PedidoHistorico.usuario),
            )
            .filter(Pedido.id == id)
            .first()
        )
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")

        itens = [
            PedidoItemSchema(
                id=it.id,
                ean=it.ean,
                codigo_produto_erp=it.codigo_produto_erp,
                quantidade_solicitada=it.quantidade_solicitada,
                quantidade_atendida=it.quantidade_atendida,
                preco=it.preco,
                desconto=it.desconto,
                cod_motivo=it.cod_motivo,
                id_cond=it.id_cond,
                status=it.status,
                ocorrencias=[
                    ItemOcorrenciaResumo(
                        id=oc.id,
                        severidade=oc.severidade,
                        codigo=oc.codigo,
                        descricao=oc.descricao,
                        resolvido=bool(oc.resolvido),
                        criado_em=oc.criado_em,
                    )
                    for oc in _deduplicar_ocorrencias(it.ocorrencias)
                ],
            )
            for it in pedido.itens
        ]

        ocorrencias = [
            OcorrenciaResumo(
                id=oc.id,
                severidade=oc.severidade,
                codigo=oc.codigo,
                descricao=oc.descricao,
                resolvido=bool(oc.resolvido),
                criado_em=oc.criado_em,
            )
            for oc in _deduplicar_ocorrencias(pedido.ocorrencias)
        ]

        arquivos = [
            ArquivoResumo(
                id=a.id,
                numero_pedido_ol=a.numero_pedido_ol,
                nome=a.nome,
                tipo=a.tipo,
                hash_md5=a.hash_md5,
                situacao=a.situacao,
                criado_em=a.criado_em,
            )
            for a in pedido.arquivos
        ]

        historico = [
            HistoricoResumo(
                id=h.id,
                acao=h.acao,
                detalhe=h.detalhe,
                usuario_nome=h.usuario.nome if h.usuario else None,
                criado_em=h.criado_em,
            )
            for h in sorted(pedido.historico, key=lambda x: x.criado_em or datetime.min, reverse=True)
        ]

        return PedidoDetail(
            id=cast(int, pedido.id),
            numero_pedido_ol=cast(str, pedido.numero_pedido_ol),
            nome_arquivo=cast(str, pedido.nome_arquivo),
            codigo_interno_erp=cast(int, pedido.codigo_interno_erp),
            cnpj_cliente=cast(str, pedido.cnpj_cliente),
            condicao=cast(str, pedido.condicao),
            observacao=cast(str, pedido.observacao),
            status_operacional=cast(str, pedido.status_operacional),
            status_erp=cast(str, pedido.status_erp),
            valor_total=cast(Decimal, pedido.valor_total),
            data_pedido=cast(datetime, pedido.data_pedido),
            criado_em=cast(datetime, pedido.criado_em),
            atualizado_em=cast(datetime, pedido.atualizado_em),
            industria_nome=pedido.industria.nome if pedido.industria else None,
            itens=itens,
            ocorrencias=ocorrencias,
            arquivos=arquivos,
            historico=historico,
            retorno_manual_liberado=operacoes.retorno_manual_liberado_por_atraso(pedido),
            **operacoes.acoes_de_geracao_manual(pedido),
            envio_somente_pronto=_envio_somente_pronto(db),
            **_analise_campos(pedido),
        )
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        raise HTTPException(status_code=500, detail=f"Erro ao carregar detalhes do pedido {id}.")
