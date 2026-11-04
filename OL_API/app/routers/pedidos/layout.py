"""Geração do arquivo do pedido no layout do distribuidor (download)."""
import io
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models import Pedido
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.layouts import formato_closeup
from ol_core.models.enums.tipo_arquivo import TipoArquivo

from ._comum import _OPERACIONAL

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get("/{id}/gerar-pedido")
def gerar_pedido(id: int, db: Session = Depends(get_db), _user=Depends(_OPERACIONAL),):
    try:
        pedido = (
            db.query(Pedido)
            .options(
                selectinload(Pedido.itens),
                selectinload(Pedido.arquivos),
            )
            .filter(Pedido.id == id)
            .first()
        )
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    
        # Tenta usar o arquivo original no disco
        arquivo_original = next(
            (a for a in pedido.arquivos if a.tipo == TipoArquivo.PEDIDO.value and a.caminho),
            None,
        )
        if arquivo_original and os.path.isfile(arquivo_original.caminho):
            nome_download = os.path.basename(arquivo_original.caminho)
            def _stream_file():
                with open(arquivo_original.caminho, "rb") as f:
                    yield from f
            return StreamingResponse(
                _stream_file(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{nome_download}"',
                    # Card #42 — sinaliza ao frontend que este é o arquivo
                    # original recebido da indústria (não uma reconstrução).
                    "X-Arquivo-Origem": "original",
                },
            )
    
        # Reconstrói a partir dos dados do banco
        if not pedido.itens:
            raise HTTPException(status_code=422, detail="Pedido sem itens — não é possível gerar o arquivo.")
    
        # Formato (posições e larguras) no layout Close-Up.
        conteudo = formato_closeup.reconstruir_arquivo_pedido(
            pedido.numero_pedido_ol,
            pedido.cnpj_cliente,
            pedido.data_pedido or datetime.now(),
            pedido.observacao,
            [(item.ean, item.quantidade_solicitada, item.desconto, item.id_cond) for item in pedido.itens],
        )
    
        nome_arquivo = pedido.nome_arquivo or f"PEDIDO_{pedido.numero_pedido_ol}_{pedido.cnpj_cliente}.txt"
        nome_download = os.path.basename(str(nome_arquivo))
    
        return StreamingResponse(
            io.BytesIO(conteudo.encode("utf-8")),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nome_download}"',
                # Card #42 — sinaliza ao frontend que este arquivo foi
                # RECONSTRUÍDO a partir do banco (original não está mais em
                # disco) e pode estar incompleto/divergente.
                "X-Arquivo-Origem": "reconstruido",
            },
        )
    except HTTPException:
        # Repassa sem alterar: os 404/422 levantados de propósito acima
        # (pedido não encontrado / sem itens) são HTTPException, e
        # HTTPException também é uma Exception — sem este except dedicado,
        # o except Exception abaixo os recapturava e trocava por um 500
        # genérico, mascarando o código de erro real (achado do QA no
        # card #60, ponto 5).
        raise
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar arquivo de pedido — {str(err)}")
