import re
from random import randint

from sete_mares import RolagemSeteMares, rolar_sete_mares

_DADO = r"(?P<quantidade>[0-9]{0,3})d(?P<faces>[0-9]{1,4})(?:(?P<modo>kh|kl)(?P<manter>[0-9]{1,3}))?"
_TERMO = re.compile(rf"(?P<sinal>[+-]?)\s*(?:{_DADO}|(?P<numero>[0-9]{{1,6}}))", re.IGNORECASE)


def rolar(mensagem: str) -> RolagemSeteMares | str | None:
    """Responde com o total e os dados, ou ignora uma mensagem fora da sintaxe."""
    expressao = mensagem.strip()
    if not expressao or len(expressao) > 120:
        return None

    resposta_sete_mares = rolar_sete_mares(expressao)
    if resposta_sete_mares is not None:
        return resposta_sete_mares

    termos = []
    total_dados = 0
    fim = 0
    for termo in _TERMO.finditer(expressao):
        sinal = termo["sinal"]
        if expressao[fim:termo.start()].strip() or (termos and not sinal):
            return None
        fim = termo.end()
        if termo["numero"] is not None:
            termos.append((sinal, int(termo["numero"]), 0, "", 0))
            continue
        quantidade = int(termo["quantidade"] or "1")
        faces = int(termo["faces"])
        modo = (termo["modo"] or "").lower()
        manter = int(termo["manter"]) if modo else quantidade
        if not 1 <= manter <= quantidade or not 2 <= faces <= 1000:
            return None
        total_dados += quantidade
        if total_dados > 100:
            return None
        termos.append((sinal, quantidade, faces, modo, manter))

    if fim != len(expressao) or not total_dados:
        return None

    total = 0
    detalhes = []
    for sinal, quantidade, faces, modo, manter in termos:
        multiplicador = -1 if sinal == "-" else 1
        prefixo = (sinal or "+") + " " if detalhes else ("-" if sinal == "-" else "")
        if not faces:
            total += multiplicador * quantidade
            detalhes.append(f"{prefixo}{quantidade}")
            continue

        dados = [randint(1, faces) for _ in range(quantidade)]
        ordem = sorted(range(quantidade), key=dados.__getitem__, reverse=modo == "kh")
        incluidos = set(ordem[:manter])
        total += multiplicador * sum(dados[i] for i in incluidos)
        resultados = []
        for i in sorted(range(quantidade), key=dados.__getitem__, reverse=True):
            valor = dados[i]
            exibicao = f"**{valor}**" if valor == faces else str(valor)
            resultados.append(exibicao if i in incluidos else f"~~{exibicao}~~")
        resultados_formatados = ", ".join(resultados)
        sufixo = f"{modo}{manter}" if modo else ""
        detalhes.append(f"{prefixo}[{resultados_formatados}] {quantidade}d{faces}{sufixo}")

    return f"`{total}` ← {' '.join(detalhes)}"
