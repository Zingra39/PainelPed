"""Envio de arquivos: transmissão do pedido para o ERP (cópia para a pasta de
entrada) e reenvio de retorno/espelho/cancelamento por FTP."""
import os
import shutil
from datetime import datetime

from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.services.conectar_ftp import envia_arquivo_ftp
from ol_core.utils.transmissao import copiar_arquivo_com_observacao

from .conversao import _resolve_path
from .historico import _log


# Reenvio NÃO é regeração: pega o arquivo que já foi gerado (pelo `caminho`
# gravado na tabela `arquivo`) e refaz apenas a entrega — FTP + pasta de envio
# da indústria. O conteúdo entregue é byte a byte o mesmo que a indústria
# recebeu da primeira vez, e o status do pedido não é alterado: reenviar é uma
# operação de entrega, não de processamento.
#
# Cada tipo tem seu destino próprio, espelhando o que os services fazem na
# geração (retorno_service / espelho_service / cancelamento_service).
_DESTINO_REENVIO = {
    TipoArquivo.RETORNO.value:  ("pasta_retorno_envio",      "/46239901000131/RETORNO"),
    TipoArquivo.ESPELHO.value:  ("pasta_retorno_espelho",    "/46239901000131/ESPELHO"),
    TipoArquivo.CANCELADO.value: ("pasta_envio_cancelamento", "/46239901000131/CANCELAMENTO"),
}


_ROTULO_REENVIO = {
    TipoArquivo.RETORNO.value: "Retorno",
    TipoArquivo.ESPELHO.value: "Espelho",
    TipoArquivo.CANCELADO.value: "Cancelamento",
}


def executar_reenviar_arquivo(pedido_db, tipo: str, id_usuario: int) -> dict:
    """Reenvia o arquivo já gerado de um pedido, sem regerar o conteúdo."""
    if tipo not in _DESTINO_REENVIO:
        raise ValueError(f"Tipo de arquivo inválido para reenvio: '{tipo}'.")

    campo_pasta, caminho_ftp = _DESTINO_REENVIO[tipo]
    rotulo = _ROTULO_REENVIO[tipo]

    # Entre vários arquivos do mesmo tipo (regerações anteriores), reenvia o
    # mais recente — que é o que a indústria tem como válido.
    candidatos = [a for a in pedido_db.arquivos if (a.tipo or "").lower() == tipo]
    if not candidatos:
        raise ValueError(f"Este pedido não possui arquivo de {rotulo.lower()} gerado.")
    arquivo_record = max(candidatos, key=lambda a: (a.criado_em or datetime.min, a.id))

    origem = _resolve_path(arquivo_record.caminho)
    if not origem or not os.path.isfile(origem):
        raise ValueError(
            f"Arquivo de {rotulo.lower()} '{arquivo_record.nome}' não encontrado em disco "
            f"({arquivo_record.caminho}). Não é possível reenviar o original."
        )

    industria_db = pedido_db.industria
    if not industria_db:
        raise ValueError("Indústria do pedido não encontrada.")

    pasta_destino = _resolve_path(getattr(industria_db, campo_pasta, None))
    if not pasta_destino:
        raise ValueError(
            f"Pasta de envio de {rotulo.lower()} não configurada para a indústria '{industria_db.nome}'."
        )

    # O FTP respeita o mesmo guarda dos services: fora de Produção ele apenas
    # loga e não envia.
    envia_arquivo_ftp(caminho_ftp, origem)

    try:
        os.makedirs(pasta_destino, exist_ok=True)
        destino = os.path.join(pasta_destino, os.path.basename(origem))
        # Sobrescreve de propósito: `envia_arquivo_para_pasta` (usado na
        # geração) pula quando o arquivo já existe no destino, o que faria todo
        # reenvio virar no-op — justamente o caso de uso aqui.
        shutil.copy2(origem, destino)
    except OSError as e:
        raise ValueError(f"Erro ao copiar {rotulo.lower()} para a pasta de envio: {e}") from e

    _log(
        pedido_db.numero_pedido_ol,
        f"{rotulo} reenviado",
        (
            f"Arquivo '{arquivo_record.nome}' reenviado para {pasta_destino} "
            f"via painel pelo usuário {id_usuario}. Conteúdo original preservado."
        ),
        id_usuario,
    )

    return {
        "sucesso": True,
        "mensagem": f"{rotulo} '{arquivo_record.nome}' reenviado para {pasta_destino}.",
    }


def executar_transmitir(pedido_db, id_usuario: int) -> dict:
    """Copia o arquivo do pedido para a pasta_entrada da indústria."""
    arquivo_record = next(
        (a for a in pedido_db.arquivos if a.tipo == TipoArquivo.PEDIDO.value), None
    )
    if not arquivo_record or not arquivo_record.nome:
        raise ValueError("Arquivo original do pedido não registrado no banco.")

    industria_db = pedido_db.industria
    if not industria_db:
        raise ValueError("Indústria do pedido não encontrada.")

    pasta_entrada_str = _resolve_path(industria_db.pasta_entrada)
    if not pasta_entrada_str:
        raise ValueError(
            f"Pasta de entrada não configurada para a indústria '{industria_db.nome}'."
        )

    pasta_backup_str = _resolve_path(industria_db.pasta_backup_pedido or "ERP/BACKUP")
    
    if not pasta_backup_str:
        raise ValueError(
            f"Pasta de backup não configurada para a indústria '{industria_db.nome}'."
        )
    
    origem = os.path.join(pasta_backup_str, arquivo_record.nome)

    if not os.path.isfile(origem):
        raise ValueError(
            f"Arquivo '{arquivo_record.nome}' não encontrado na pasta de backup "
            f"({pasta_backup_str})."
        )

    try:
        os.makedirs(pasta_entrada_str, exist_ok=True)
        destino = os.path.join(pasta_entrada_str, arquivo_record.nome)
        # A observação da triagem entra no arquivo aqui, na cópia que vai para
        # a pasta de entrada — é o último ponto antes de o ERP ler o pedido.
        copiar_arquivo_com_observacao(origem, destino, str(pedido_db.observacao or ""))
    except OSError as e:
        raise ValueError(f"Erro ao copiar arquivo para pasta de entrada: {e}") from e

    _log(
        pedido_db.numero_pedido_ol,
        "Arquivo transmitido",
        (
            f"Arquivo '{arquivo_record.nome}' copiado para pasta de entrada de "
            f"'{industria_db.nome}' via painel pelo usuário {id_usuario}."
        ),
        id_usuario,
    )

    return {
        "sucesso": True,
        "mensagem": (
            f"'{arquivo_record.nome}' transmitido para "
            f"{pasta_entrada_str}."
        ),
    }
