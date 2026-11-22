from collections import Counter
from dataclasses import dataclass, replace
from random import randint
import re

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

_PISCINA = re.compile(r"([0-9]{0,3})d10\s*(!\s*\?|\?\s*!|[!?])?", re.IGNORECASE)


def agrupar_apostas(
    dados: list[int], especializacao: bool
) -> tuple[list[tuple[tuple[int, ...], int]], list[int]]:
    """Maximiza apostas e, em empate, preserva mais dados e pontos."""
    disponiveis = Counter(dados)
    if sum(dados) < 10:
        return [], dados.copy()

    valores = sorted(disponiveis, reverse=True)
    padroes = []
    custos = []
    pesos = []
    # Gera apenas grupos mínimos. Ao cruzar o limiar, o último dado
    # é o menor, portanto tirar qualquer dado desfaz a aposta.
    def adicionar_grupos(limiar, apostas, grupo=(), soma=0, inicio=0):
        if soma >= limiar:
            padroes.append((grupo, apostas))
            uso = Counter(grupo)
            custos.append([uso[valor] for valor in valores])
            pesos.append((len(grupo), soma, apostas))
            return
        for indice in range(inicio, len(valores)):
            valor = valores[indice]
            if grupo.count(valor) < disponiveis[valor]:
                adicionar_grupos(limiar, apostas, (*grupo, valor), soma + valor, indice)

    adicionar_grupos(10, 1)
    if especializacao:
        adicionar_grupos(15, 2)

    # Pesos lexicográficos derrubam primeiro a contagem de apostas,
    # depois o número de dados gastos e por último a soma gasta.
    peso_dado = sum(dados) + 1
    peso_aposta = (len(dados) + 1) * peso_dado
    objetivo = [
        tamanho * peso_dado + pontos - apostas * peso_aposta
        for tamanho, pontos, apostas in pesos
    ]
    resultado = milp(
        objetivo,
        integrality=np.ones(len(padroes)),
        bounds=Bounds(0, np.inf),
        constraints=LinearConstraint(np.array(custos).T, 0, [disponiveis[v] for v in valores]),
        options={"mip_rel_gap": 0.0},
    )
    if not resultado.success:
        raise RuntimeError("Não foi possível otimizar as apostas.")

    grupos = []
    for (grupo, apostas), vezes in zip(padroes, resultado.x):
        for _ in range(round(vezes)):
            grupos.append((grupo, apostas))
            disponiveis.subtract(grupo)
    grupos.sort(key=lambda entrada: (entrada[1], entrada[0]), reverse=True)
    return grupos, sorted(disponiveis.elements(), reverse=True)


class LimiteDeExplosoes(ValueError):
    pass


class DadoAusente(ValueError):
    pass


def explodir(pendentes: int, quantidade_existente: int) -> tuple[int, ...]:
    extras = []
    while pendentes:
        if quantidade_existente + len(extras) >= 500:
            raise LimiteDeExplosoes("🎲 A cadeia de explosões atingiu o limite de 500 dados.")
        extra = randint(1, 10)
        extras.append(extra)
        if extra != 10:
            pendentes -= 1
    return tuple(extras)


@dataclass(frozen=True)
class RolagemSeteMares:
    dados: tuple[int, ...]
    extras: tuple[int, ...]
    explosiva: bool
    especializacao: bool
    troca: tuple[int, int] | None = None
    rerrolagens: int = 0

    def rerrolar(self, valor: int | None = None) -> "RolagemSeteMares":
        todos = list(self.dados + self.extras)
        anterior = min(todos) if valor is None else valor
        try:
            indice = todos.index(anterior)
        except ValueError:
            disponiveis = ", ".join(map(str, sorted(set(todos))))
            raise DadoAusente(
                f"🎲 Não há nenhum dado com valor **{anterior}** nessa pool. "
                f"Valores disponíveis: **{disponiveis}**. A rolagem ficou como estava."
            ) from None
        novo = randint(1, 10)
        todos[indice] = novo
        extras = explodir(1, len(todos)) if self.explosiva and novo == 10 else ()
        corte = len(self.dados)
        return replace(
            self,
            dados=tuple(todos[:corte]),
            extras=tuple(todos[corte:]) + extras,
            troca=(anterior, novo),
            rerrolagens=self.rerrolagens + 1,
        )

    def formatar(self) -> str:
        todos = self.dados + self.extras
        grupos, sobras = agrupar_apostas(list(todos), self.especializacao)
        total = sum(apostas for _, apostas in grupos)
        descricao = " · ".join(
            f"({' + '.join(map(str, grupo))} = {sum(grupo)})" + (" ×2" if apostas == 2 else "")
            for grupo, apostas in grupos
        ) or "nenhuma"
        sufixo = ("!" if self.explosiva else "") + ("?" if self.especializacao else "")
        dados = ", ".join(map(str, self.dados))
        partes = [
            f"`{sum(todos)}` ← [{dados}] {len(self.dados)}d10{sufixo}",
            f"**Apostas:** {total} | **Rerrolagens:** {self.rerrolagens}",
        ]
        if self.troca is not None:
            anterior, novo = self.troca
            partes.append(f"**Dado rerrolado:** {anterior} → {novo}")
        if self.extras:
            partes.append(f"**Dados extras (!):** {', '.join(map(str, self.extras))}")
        partes.extend((
            f"**Grupos:** {descricao}",
            f"**Sobras:** {', '.join(map(str, sobras)) or 'nenhuma'}",
        ))
        return " · ".join(partes)


def rolar_sete_mares(expressao: str) -> RolagemSeteMares | str | None:
    correspondencia = _PISCINA.fullmatch(expressao)
    if correspondencia is None:
        return None
    quantidade = int(correspondencia[1] or "1")
    if not 1 <= quantidade <= 100:
        return None

    opcoes = correspondencia[2] or ""
    explosiva = "!" in opcoes
    dados = tuple(randint(1, 10) for _ in range(quantidade))
    try:
        extras = explodir(dados.count(10), quantidade) if explosiva else ()
    except LimiteDeExplosoes as erro:
        return f"{erro} Role novamente."
    return RolagemSeteMares(dados, extras, explosiva, "?" in opcoes)
