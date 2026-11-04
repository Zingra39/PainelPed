"""Conversão dos registros ORM do painel para os modelos de domínio do ol_core
(Industria/Pedido), incluindo a resolução das pastas relativas ao OL_Services."""
import os

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.models.industria import Industria as IndustriaOL
from ol_core.models.pedido import Pedido as PedidoOL


_OL_SERVICES_BASE = os.getenv("OL_SERVICES_PATH", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "OL_Services")
))


def _layout(nome: str) -> "TipoLayout":
    """Layout configurado na indústria. Vazio ou desconhecido é erro — antes
    caía em CloseUp sem avisar, gerando arquivo no formato errado. (O core já
    recusa esses valores ao carregar a indústria nos serviços automáticos.)"""
    try:
        return TipoLayout((nome or "").strip().lower())
    except ValueError:
        aceitos = ", ".join(t.value for t in TipoLayout)
        raise ValueError(
            f"Tipo de layout '{nome or ''}' não reconhecido. Configure o layout da indústria ({aceitos})."
        ) from None


def _resolve_path(p: "str | None") -> "str | None":
    if not p or os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(_OL_SERVICES_BASE, p))


def _build_industria(industria_db) -> "IndustriaOL":
    try:
        pasta_backup_retorno      = _resolve_path(industria_db.pasta_retorno)
        pasta_envio_retorno       = _resolve_path(industria_db.pasta_retorno_envio)
        pasta_envio_nf            = _resolve_path(industria_db.pasta_espelho)
        pasta_backup_nf           = _resolve_path(industria_db.pasta_retorno_espelho)
        pasta_envio_cancelamento  = _resolve_path(industria_db.pasta_envio_cancelamento)
        pasta_backup_cancelamento = _resolve_path(industria_db.pasta_cancelamento)
        pasta_backup_pedido       = _resolve_path(industria_db.pasta_backup_pedido)
        
        if pasta_envio_retorno is None:
            raise ValueError(
                f"Campo 'pasta_retorno_envio' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
        
        if pasta_backup_retorno is None:
            raise ValueError(
                f"Campo 'pasta_retorno' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
            
        if pasta_envio_nf is None:
            raise ValueError(
                f"Campo 'pasta_espelho' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
        
        if pasta_backup_nf is None:
            raise ValueError(
                f"Campo 'pasta_retorno_espelho' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
        
        if pasta_envio_cancelamento is None:
            raise ValueError(
                f"Campo 'pasta_envio_cancelamento' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
        
        if pasta_backup_cancelamento is None:
            raise ValueError(
                f"Campo 'pasta_cancelamento' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
            
        if pasta_backup_pedido is None:
            raise ValueError(
                f"Campo 'pasta_backup_pedido' não configurado para a indústria '{industria_db.nome}'. "
                "Configure o campo antes de gerar retornos ou espelhos."
            )
        
        return IndustriaOL(
            id_industria=industria_db.id,
            nome=industria_db.nome,
            tipo_layout=_layout(industria_db.layout),
            cond_mae=industria_db.cond_mae or 0,
            pasta_retorno=pasta_backup_retorno,
            pasta_nfe=pasta_envio_nf,
            pasta_envio_retorno=pasta_envio_retorno,
            pasta_envio_nf=pasta_backup_nf,
            pasta_envio_cancelamento=pasta_envio_cancelamento,
            pasta_cancelamento=pasta_backup_cancelamento,
            pasta_backup= pasta_backup_pedido,
        )
    except ErroConexaoBanco:
        raise
    except Exception as e:
        raise RuntimeError(f"Erro ao criar a indústria: {e}")


def _build_pedido(pedido_db) -> "PedidoOL":
    try:
        condicao = int(pedido_db.id_cond) if pedido_db.id_cond is not None else 0
        valor_total = float(pedido_db.valor_total) if pedido_db.valor_total is not None else 0.0
        
        return PedidoOL(
            id_industria=pedido_db.id_industria,
            nome_arquivo=pedido_db.nome_arquivo,
            cnpj_cliente=pedido_db.cnpj_cliente,
            codigo_interno_pedido=pedido_db.codigo_interno_erp,
            id_cond=condicao,
            numero_pedido_ol=pedido_db.numero_pedido_ol,
            data_pedido=pedido_db.data_pedido,
            valor_total=valor_total,
        )
    except ErroConexaoBanco:
        raise
    except Exception as e:
        raise RuntimeError(f"Erro ao criar o pedido: {pedido_db.__dict__}")
