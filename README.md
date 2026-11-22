# Bot de dados para Discord

Envie uma expressão como mensagem comum. O bot responde diretamente à mensagem da rolagem, com o total antes dos dados, como `14` ← [14] 1d20. As mensagens de conversa ficam intactas.

| Mensagem | Rolagem |
| --- | --- |
| `d20` ou `1d20` | Um dado de 20 faces |
| `2d6+3` | Dois d6 com bônus de +3 |
| `1d8 + 1d6 - 2` | Dois tipos de dado com penalidade de −2 |
| `4d6kh3` | Quatro d6, mantendo os três maiores |
| `2d20kl1` | Dois d20, mantendo o menor |

A mensagem inteira deve ser uma expressão. Dados descartados aparecem riscados. São aceitos até 100 dados por mensagem e dados de 2 a 1.000 faces.

## Configurar no Discord

1. Crie uma aplicação em **New Application** no [Discord Developer Portal](https://discord.com/developers/applications).
2. Em **Bot → Privileged Gateway Intents**, habilite **Message Content Intent** e salve. Esse acesso permite ler as expressões enviadas como mensagens comuns.
3. Na mesma página **Bot**, use **Reset Token** para obter o token. Guarde-o localmente em `token.txt` e mantenha-o privado.
4. Em **Installation**, habilite **Guild Install** e selecione **Discord Provided Link**. Configure o escopo `bot` com as permissões **View Channels**, **Send Messages** e **Read Message History**. Abra o link de instalação e escolha um servidor que você gerencia.

## Rodar no computador

Você precisa do Python 3.10 ou mais recente. Extraia o ZIP e abra um terminal na pasta que contém `bot.py`.

No Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No macOS ou Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Crie `token.txt` ao lado de `bot.py` e cole somente o token, sem aspas nem `DISCORD_TOKEN=`. Salve em UTF-8. Em seguida, execute `.\.venv\Scripts\python.exe bot.py` no Windows ou `.venv/bin/python bot.py` no macOS/Linux.

O bot procura primeiro a variável de ambiente `DISCORD_TOKEN`, depois `token.txt` e, por último, o arquivo `.env` de instalações anteriores.

Quando o terminal indicar que o bot está conectado, envie `d20` em um canal que ele possa ver. Mantenha o processo em execução enquanto quiser usar o bot. O bot usa a API do Discord e roda as expressões localmente, sem consumir créditos da OpenAI.

## Apostas de 7º Mar

Envie um grupo simples de d10. A resposta mostra os valores rolados, os grupos que formam apostas e os dados que sobraram.

| Mensagem | Regra |
| --- | --- |
| `8d10` | Cada grupo que soma 10 ou mais vale uma aposta |
| `8d10!` ou `8d10 !` | Cada 10 gera um d10 adicional. Se o dado extra cair em 10, ele gera outro |
| `8d10?` ou `8d10 ?` | Grupos que somam 15 ou mais podem valer duas apostas |
| `8d10!?` ou `8d10?!` | Combina explosões e grupos de duas apostas. Espaços entre os símbolos também funcionam |

O bot busca o maior número de apostas. Em caso de empate, escolhe a combinação que gasta menos dados. Se o empate continuar, prefere deixar a maior soma nas sobras. Cada dado só pode ser usado uma vez. Modificadores, dados mistos e opções `kh`/`kl` continuam na rolagem comum. Os símbolos `!` e `?` são exclusivos dos grupos simples de d10.

Para exibir o detalhamento de rolagens excepcionalmente longas, conceda também **Attach Files** nas permissões do bot.

### Rerrolar um d10

Na mensagem do resultado, clique em **Rerrolar o menor** ou em **Escolher um dado**. O segundo botão abre um menu privado com os valores presentes na pool.

Você também pode clicar em **Responder** e enviar um destes textos:

| Mensagem | Dado substituído |
| --- | --- |
| `/reroll d10`, `/rr d10`, `rr d10` ou só `/rr` | O dado de menor valor |
| `/reroll 2`, `/rr 2` ou `rr 2` | Um dado que caiu em 2. Você pode indicar qualquer valor de 1 a 10 |

Só quem fez a rolagem original pode rerrolar. Se houver mais de um dado com o valor escolhido, o primeiro é substituído. Dados extras e sobras também podem ser escolhidos. Se o valor escolhido não aparecer, o bot responde ao pedido com os valores disponíveis e mantém a rolagem. O bot edita a resposta original com o novo resultado, as apostas e as sobras. As opções `!` e `?` continuam valendo.

A rerrolagem está disponível para as últimas 1.000 rolagens simples de d10 da sessão atual do bot. Reiniciar o processo limpa esse histórico.

### Ajuda no Discord

Use o comando de barra `/help` para abrir um guia com exemplos. A ajuda aparece apenas para quem pediu. O bot registra o comando ao conectar. Se ele ainda não aparecer, aguarde a sincronização do Discord e confira se a aplicação está instalada no servidor.

## Hospedar no Railway

Para manter o bot online com seu computador desligado, use um serviço que
permita processos Python contínuos. O projeto inclui a configuração de
inicialização para o Railway e não precisa de domínio público.

1. Envie os arquivos extraídos para a raiz de um repositório privado no GitHub.
   Mantenha `token.txt` e `.env` fora do repositório.
2. No Railway, crie um projeto a partir desse repositório. Selecione **Add Variables**
   e crie a variável `DISCORD_TOKEN` com o token do bot.
3. Para manter o processo ativo, use um plano que suporte execução contínua e
   deixe **Serverless** desativado nas configurações do serviço.
4. Clique em **Deploy**. Confira se os logs exibem **Bot conectado como** e envie
   `d20` em um canal do servidor em que a aplicação foi instalada.

Use uma única instância do bot para evitar respostas duplicadas.

## Hospedar na Discloud

O pacote já inclui `discloud.config` com Python 3.11 e 100 MB de RAM.
O plano gratuito pode suspender apps inativos.

1. Extraia o pacote em uma pasta privada e crie `token.txt` ao lado de
   `bot.py`. Cole somente o token do bot nesse arquivo.
2. Faça um novo ZIP com os arquivos na raiz. Inclua `token.txt`, `bot.py`,
   `dados.py`, `sete_mares.py`, `requirements.txt` e `discloud.config`.
3. Envie esse ZIP diretamente pelo painel da Discloud. Mantenha essa cópia
   com o token fora do GitHub e de pastas públicas.
4. Confira se os logs mostram **Bot conectado como** e envie `d20` no Discord.

Se os logs indicarem falta de memória, ajuste `RAM` de acordo com a cota do
seu plano. Rolagens grandes podem usar mais memória.
