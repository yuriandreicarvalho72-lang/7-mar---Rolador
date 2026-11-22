import asyncio
import io
import logging
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import discord
from discord import app_commands
from dotenv import dotenv_values

from dados import rolar
from sete_mares import DadoAusente, LimiteDeExplosoes, RolagemSeteMares


_RERROLL = re.compile(r"(?:/reroll|/rr|rr)(?:\s+(d10|10|[1-9]))?", re.IGNORECASE)


@app_commands.command(name="help", description="Mostra como rolar dados e calcular apostas de 7º Mar.")
async def comando_ajuda(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🎲 Como usar o bot de dados**\n"
        "Envie a expressão sozinha no canal.\n"
        "• `d20` rola um d20. `2d6+3` soma dois d6 e acrescenta 3.\n"
        "• `4d6kh3` soma os três maiores. `2d20kl1` mantém o menor.\n\n"
        "**7º Mar · somente grupos simples de d10**\n"
        "• `8d10` agrupa os dados para obter o máximo de apostas. Use **Ver cálculo** para ver os grupos e as sobras. "
        "Cada grupo de 10 ou mais vale 1 aposta.\n"
        "• `8d10 (12)` exige soma mínima de 12 por aposta. Use qualquer inteiro positivo entre parênteses, depois de ! ou ?.\n"
        "• `8d10!` faz cada 10 explodir, gerando outro d10.\n"
        "• `8d10?` vale 2 apostas por grupo que atingir 15 e a dificuldade da rolagem.\n"
        "• `8d10!?` ou `8d10?!` ativa as duas opções.\n\n"
        "**Rerrolar um d10**\n"
        "Use **Rerrolar o menor** ou **Escolher um dado** no resultado. "
        "Você também pode responder à mensagem com um destes textos.\n"
        "• `/reroll d10` ou `/rr` substitui o menor dado.\n"
        "• `/reroll 2`, `/rr 2` ou `rr 2` substitui um dado que caiu em 2. "
        "Escolha qualquer valor de 1 a 10.\n"
        "Só quem fez a rolagem pode alterar o resultado.",
        ephemeral=True,
    )


@dataclass
class ResultadoPublicado:
    autor_id: int
    mensagem: discord.Message
    rolagem: RolagemSeteMares
    calculo: str
    botoes: discord.ui.View
    trava: asyncio.Lock = field(default_factory=asyncio.Lock)


def preparar_resposta(texto: str) -> tuple[str, list[discord.File]]:
    if len(texto) <= 2000:
        return texto, []
    arquivo = discord.File(io.BytesIO(texto.encode("utf-8")), "rolagem.txt")
    resumo = " · ".join(texto.splitlines()[0].split(" · ", 2)[:2])
    return f"{resumo[:1900]} · Detalhes no anexo.", [arquivo]


def preparar_rerrolagem(rolagem: RolagemSeteMares, valor: int | None):
    nova = rolagem.rerrolar(valor)
    resumo, calculo = nova.formatar()
    return nova, resumo, calculo


class BotoesRerrolagem(discord.ui.View):
    def __init__(self, bot: "BotDeDados"):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Rerrolar o menor", style=discord.ButtonStyle.primary)
    async def menor(self, interacao: discord.Interaction, _: discord.ui.Button):
        await interacao.response.defer(ephemeral=True, thinking=True)
        aviso = await self.bot.atualizar_rolagem(interacao.message.id, interacao.user.id, None)
        await interacao.edit_original_response(content=aviso or "🎲 O resultado foi atualizado.")

    @discord.ui.button(label="Escolher um dado", style=discord.ButtonStyle.secondary)
    async def escolher(self, interacao: discord.Interaction, _: discord.ui.Button):
        mensagem_id = interacao.message.id
        resultado, aviso = self.bot.buscar_resultado(mensagem_id, interacao.user.id)
        if resultado is None:
            await interacao.response.send_message(aviso, ephemeral=True)
            return

        dados = resultado.rolagem.dados + resultado.rolagem.extras
        menu = discord.ui.Select(
            placeholder="Qual valor você quer rerrolar?",
            options=[discord.SelectOption(label=str(valor)) for valor in sorted(set(dados))],
        )
        painel = discord.ui.View(timeout=120)

        async def selecionar(selecao: discord.Interaction):
            valor = int(menu.values[0])
            await selecao.response.defer()
            aviso = await self.bot.atualizar_rolagem(mensagem_id, selecao.user.id, valor)
            await selecao.edit_original_response(
                content=aviso or "🎲 O resultado foi atualizado.",
                view=None,
            )
            painel.stop()

        menu.callback = selecionar
        painel.add_item(menu)
        await interacao.response.send_message("Escolha um valor da pool.", view=painel, ephemeral=True)


    @discord.ui.button(label="Ver cálculo", style=discord.ButtonStyle.secondary)
    async def ver_calculo(self, interacao: discord.Interaction, _: discord.ui.Button):
        resultado = self.bot.resultados.get(interacao.message.id)
        if resultado is None:
            await interacao.response.send_message("🎲 O cálculo dessa rolagem expirou.", ephemeral=True)
            return

        conteudo, arquivos = preparar_resposta(resultado.calculo)
        await interacao.response.send_message(conteudo, files=arquivos, ephemeral=True)


class BotDeDados(discord.Client):
    def __init__(self, **opcoes):
        super().__init__(**opcoes)
        self.resultados: OrderedDict[int, ResultadoPublicado] = OrderedDict()
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(comando_ajuda)

    async def setup_hook(self):
        try:
            await self.tree.sync()
        except discord.HTTPException:
            logging.exception("Falha ao registrar /help no Discord.")

    async def on_ready(self):
        logging.info("Bot conectado como %s", self.user)

    async def on_message(self, mensagem: discord.Message):
        if mensagem.author.bot or mensagem.webhook_id is not None:
            return

        pedido = _RERROLL.fullmatch(mensagem.content.strip())
        if pedido is not None:
            argumento = (pedido[1] or "d10").lower()
            valor = None if argumento == "d10" else int(argumento)
            await self.rerrolar(mensagem, valor)
            return

        resultado = await asyncio.to_thread(rolar, mensagem.content)
        if resultado is None:
            return
        if not isinstance(resultado, RolagemSeteMares):
            conteudo, arquivos = preparar_resposta(resultado)
            await mensagem.reply(conteudo, files=arquivos, mention_author=False)
            return

        texto, calculo = await asyncio.to_thread(resultado.formatar)
        conteudo, arquivos = preparar_resposta(texto)
        botoes = BotoesRerrolagem(self)
        publicada = await mensagem.reply(
            conteudo, files=arquivos, view=botoes, mention_author=False,
        )
        self.resultados[publicada.id] = ResultadoPublicado(
            mensagem.author.id, publicada, resultado, calculo, botoes,
        )
        if len(self.resultados) > 1000:
            _, antigo = self.resultados.popitem(last=False)
            antigo.botoes.stop()

    def buscar_resultado(self, mensagem_id: int, autor_id: int):
        resultado = self.resultados.get(mensagem_id)
        if resultado is None:
            return None, "🎲 Esse resultado não está mais disponível para rerrolagem."
        if resultado.autor_id != autor_id:
            return None, "🎲 Só quem fez a rolagem pode rerrolar esse dado."
        return resultado, None

    async def rerrolar(self, mensagem: discord.Message, valor: int | None):
        referencia = mensagem.reference
        resultado = self.resultados.get(referencia.message_id) if referencia else None
        if resultado is None or resultado.mensagem.channel.id != mensagem.channel.id:
            return
        if resultado.autor_id != mensagem.author.id:
            return
        aviso = await self.atualizar_rolagem(resultado.mensagem.id, mensagem.author.id, valor)
        if aviso:
            await mensagem.reply(aviso, mention_author=False)

    async def atualizar_rolagem(self, mensagem_id: int, autor_id: int, valor: int | None) -> str | None:
        resultado, aviso = self.buscar_resultado(mensagem_id, autor_id)
        if resultado is None:
            return aviso

        async with resultado.trava:
            if self.resultados.get(mensagem_id) is not resultado:
                return "🎲 Esse resultado não está mais disponível para rerrolagem."
            try:
                nova, texto, calculo = await asyncio.to_thread(preparar_rerrolagem, resultado.rolagem, valor)
            except DadoAusente as erro:
                return str(erro)
            except LimiteDeExplosoes as erro:
                return f"{erro} O resultado anterior foi mantido."
            conteudo, arquivos = preparar_resposta(texto)
            try:
                editada = await resultado.mensagem.edit(content=conteudo, attachments=arquivos)
            except discord.NotFound:
                self.resultados.pop(mensagem_id, None)
                resultado.botoes.stop()
                return "🎲 A mensagem com o resultado não está mais disponível."
            except discord.HTTPException:
                logging.exception("Falha ao atualizar a mensagem %s.", mensagem_id)
                return "🎲 Não foi possível atualizar a mensagem. A rolagem ficou como estava."
            resultado.mensagem = editada
            resultado.rolagem = nova
            resultado.calculo = calculo
            return None


def carregar_token(pasta: Path) -> str:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if token:
        return token

    try:
        token = (pasta / "token.txt").read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        token = ""
    except (OSError, UnicodeError):
        raise SystemExit("Não consegui ler token.txt. Confira o acesso ao arquivo e salve-o em UTF-8.") from None
    if token:
        return token

    token = (dotenv_values(pasta / ".env").get("DISCORD_TOKEN") or "").strip()
    if token:
        return token

    raise SystemExit("Coloque o token em token.txt ao lado de bot.py ou configure DISCORD_TOKEN.")


def main():
    logging.basicConfig(level=logging.INFO)
    token = carregar_token(Path(__file__).resolve().parent)

    intents = discord.Intents.default()
    intents.message_content = True
    bot = BotDeDados(intents=intents, allowed_mentions=discord.AllowedMentions.none())
    bot.run(token)


if __name__ == "__main__":
    main()
