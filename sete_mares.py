from collections import Counter
from dataclasses import dataclass, replace
from random import randint
import re

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, eye, hstack, kron, vstack

_PISCINA = re.compile(r"([0-9]{0,3})d10\s*(!\s*\?|\?\s*!|[!?])?(?:\s*\(\s*([0-9]+)\s*\))?", re.IGNORECASE)


def agrupar_apostas(
    dados: list[int], especializacao: bool, dificuldade: int = 10
) -> tuple[list[tuple[tuple[int, ...], int]], list[int], bool]:
    """Maximiza apostas e, em empate, preserva mais dados e pontos."""
    disponiveis = Counter(dados)
    if sum(dados) < dificuldade:
        return [], sorted(dados, reverse=True), True
    if dificuldade > 20:
        return agrupar_dificuldade_alta(disponiveis, dificuldade, 2 if especializacao else 1)

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

    if not especializacao or dificuldade < 15:
        adicionar_grupos(dificuldade, 1)
    if especializacao:
        adicionar_grupos(max(15, dificuldade), 2)

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
    return grupos, sorted(disponiveis.elements(), reverse=True), True


def agrupar_dificuldade_alta(
    disponiveis: Counter, dificuldade: int, apostas_por_grupo: int,
) -> tuple[list[tuple[tuple[int, ...], int]], list[int], bool]:
    """Resolve sem enumerar combinações de dados para cada grupo."""
    valores = sorted(disponiveis, reverse=True)
    quantidades = [disponiveis[valor] for valor in valores]
    pontos = sum(valor * disponiveis[valor] for valor in valores)
    # Cada coluna representa uma quantidade de um valor em um grupo ou
    # um indicador binário de que o grupo atingiu a dificuldade.
    vagas = pontos // dificuldade
    tipos = len(valores)
    identidade = eye(vagas, format="csr")
    zeros = csr_matrix((tipos, vagas))
    estoque = hstack((kron(np.ones((1, vagas)), eye(tipos)), zeros))
    limiares = hstack((kron(identidade, np.array([valores])), -dificuldade * identidade))
    ordem = hstack((csr_matrix((vagas - 1, vagas * tipos)), identidade[:-1] - identidade[1:]))
    matriz = vstack((estoque, limiares, ordem), format="csr")

    peso_dado = pontos + 1
    peso_grupo = (sum(quantidades) + 1) * peso_dado
    resultado = milp(
        np.r_[np.tile(np.array(valores) + peso_dado, vagas), np.full(vagas, -peso_grupo)],
        integrality=np.ones(vagas * (tipos + 1)),
        bounds=Bounds(0, np.r_[np.tile(quantidades, vagas), np.ones(vagas)]),
        constraints=LinearConstraint(
            matriz, np.zeros(tipos + 2 * vagas - 1),
            np.r_[quantidades, np.full(2 * vagas - 1, np.inf)],
        ),
        options={"mip_rel_gap": 0.0, "time_limit": 3.0},
    )
    if resultado.status not in (0, 1):
        raise RuntimeError("Não foi possível otimizar as apostas.")

    grupos = []
    if resultado.x is not None:
        contagens = resultado.x[:vagas * tipos].reshape(vagas, tipos)
        for ativo, contagem in zip(resultado.x[-vagas:], contagens):
            if ativo > 0.5:
                grupos.append(tuple(v for v, n in zip(valores, contagem) for _ in range(round(n))))

    if not resultado.success:
        # Se o solver parar cedo, conserva a melhor divisão válida disponível.
        alternativa = []
        grupo = []
        soma = 0
        for valor in sorted(disponiveis.elements(), reverse=True):
            grupo.append(valor)
            soma += valor
            if soma >= dificuldade:
                alternativa.append(tuple(grupo))
                grupo, soma = [], 0
        chave = lambda blocos: (len(blocos), -sum(map(len, blocos)), -sum(map(sum, blocos)))
        grupos = max(grupos, alternativa, key=chave)

    sobras = disponiveis.copy()
    for grupo in grupos:
        sobras.subtract(grupo)
    return (
        [(grupo, apostas_por_grupo) for grupo in sorted(grupos, reverse=True)],
        sorted(sobras.elements(), reverse=True),
        resultado.success,
    )


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
    dificuldade: int = 10

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

    def formatar(self) -> tuple[str, str]:
        def exibir_d10(valor: int) -> str:
            return "**10**" if valor == 10 else str(valor)

        todos = self.dados + self.extras
        grupos, sobras, otimo = agrupar_apostas(list(todos), self.especializacao, self.dificuldade)
        total = sum(apostas for _, apostas in grupos)
        descricao = " · ".join(
            f"({' + '.join(map(exibir_d10, grupo))} = {sum(grupo)})" + (" ×2" if apostas == 2 else "")
            for grupo, apostas in grupos
        ) or "nenhuma"
        sufixo = ("!" if self.explosiva else "") + ("?" if self.especializacao else "")
        if self.dificuldade != 10:
            sufixo += f" ({self.dificuldade})"
        dados = ", ".join(map(exibir_d10, sorted(self.dados, reverse=True)))
        partes = [
            f"`\u00a0\u00a0{sum(todos)}\u00a0\u00a0` ← [{dados}] {len(self.dados)}d10{sufixo}",
            f"**Apostas:** {total}",
        ]
        if self.troca is not None:
            partes[-1] += f" | **Rerrolagens:** {self.rerrolagens}"
            anterior, novo = self.troca
            partes.append(f"**Dado rerrolado:** {exibir_d10(anterior)} → {exibir_d10(novo)}")
        if self.extras:
            partes.append(f"**Dados extras (!):** {', '.join(map(exibir_d10, sorted(self.extras, reverse=True)))}")
        if self.especializacao and self.dificuldade >= 15:
            regra = f"{self.dificuldade} ou mais = 2 apostas (×2) com especialização."
        else:
            regra = f"{self.dificuldade} ou mais = 1 aposta."
            if self.especializacao:
                regra += " Grupos de 15 ou mais podem valer 2 apostas (×2)."
        if not otimo:
            aviso = "Melhor combinação encontrada no tempo de cálculo."
            partes.append(aviso)
            regra += f" {aviso}"
        calculo = "\n".join((
            f"**Cálculo de apostas ({total})**",
            regra,
            f"**Grupos:** {descricao}",
            f"**Sobras:** {', '.join(map(exibir_d10, sobras)) or 'nenhuma'}",
        ))
        return " · ".join(partes), calculo


def rolar_sete_mares(expressao: str) -> RolagemSeteMares | str | None:
    correspondencia = _PISCINA.fullmatch(expressao)
    if correspondencia is None:
        return None
    quantidade = int(correspondencia[1] or "1")
    if not 1 <= quantidade <= 100:
        return None

    dificuldade = int(correspondencia[3]) if correspondencia[3] else 10
    if dificuldade < 1:
        return "🎲 A dificuldade deve ser um inteiro positivo."

    opcoes = correspondencia[2] or ""
    explosiva = "!" in opcoes
    dados = tuple(randint(1, 10) for _ in range(quantidade))
    try:
        extras = explodir(dados.count(10), quantidade) if explosiva else ()
    except LimiteDeExplosoes as erro:
        return f"{erro} Role novamente."
    return RolagemSeteMares(dados, extras, explosiva, "?" in opcoes, dificuldade=dificuldade)
