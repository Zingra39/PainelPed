import shutil

# A posição da observação no cabeçalho (87 a 186) é formato do Close-Up:
# ver ol_core.layouts.formato_closeup.aplicar_observacao.
from ol_core.layouts import formato_closeup


def copiar_arquivo_com_observacao(origem: str, destino: str, observacao: str) -> None:
    """Copia o arquivo do pedido pra pasta de entrada, aplicando a observação
    no cabeçalho quando houver uma registrada.

    Função centralizada em OL_CORE (Card de transmissão automática) — usada
    tanto pela transmissão manual (OL_API/app/services/operacoes/envio.py) quanto
    pela transmissão automática (ol_core/services/import_service.py), pra
    garantir que as duas vias sempre produzam exatamente o mesmo arquivo.

    O arquivo de origem (pasta de backup, ou pasta de envio no caso da
    transmissão automática) nunca é alterado — a reescrita acontece só na
    cópia que vai para a pasta de entrada, preservando a regra do PDR de que
    o arquivo original recebido da indústria permanece intacto.

    Sem observação, faz cópia byte a byte: não há motivo para reescrever um
    arquivo cujo campo ninguém tocou (e assim um eventual conteúdo original
    do campo é preservado exatamente como veio).
    """
    if not observacao:
        shutil.copy2(origem, destino)
        return

    # newline="" preserva os fins de linha originais (\r\n) — sem isso o
    # Python traduziria e o arquivo entregue sairia diferente do recebido.
    with open(origem, "r", encoding="utf-8", newline="") as f:
        conteudo = f.read()

    quebra = conteudo.find("\n")
    if quebra == -1:
        cabecalho, resto = conteudo, ""
    else:
        cabecalho, resto = conteudo[:quebra], conteudo[quebra:]

    fim_cr = cabecalho.endswith("\r")
    if fim_cr:
        cabecalho = cabecalho[:-1]

    novo_cabecalho = formato_closeup.aplicar_observacao(cabecalho, observacao)

    with open(destino, "w", encoding="utf-8", newline="") as f:
        f.write(novo_cabecalho + ("\r" if fim_cr else "") + resto)

    shutil.copystat(origem, destino)
