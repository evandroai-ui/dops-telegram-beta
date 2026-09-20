import os
import time
import requests
from google import genai


# =========================================================
# CONFIGURAÇÕES
# =========================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não configurado.")


TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = genai.Client(api_key=GEMINI_API_KEY)


# =========================================================
# MEMÓRIA TEMPORÁRIA DAS CONVERSAS
# Depois vamos substituir pelo Supabase
# =========================================================

conversas = {}


# =========================================================
# ENVIO DE MENSAGEM PELO TELEGRAM
# =========================================================

def enviar_mensagem(chat_id, texto):

    resposta = requests.post(
        f"{TELEGRAM_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": texto
        },
        timeout=30
    )

    resposta.raise_for_status()


# =========================================================
# ANÁLISE COM GEMINI
# =========================================================

def analisar_com_gemini(chat_id, nome, mensagem):

    # Cria histórico para esse cliente
    if chat_id not in conversas:
        conversas[chat_id] = []

    # Adiciona mensagem atual
    conversas[chat_id].append(
        f"Cliente: {mensagem}"
    )

    # Mantém as últimas mensagens da conversa
    historico = "\n".join(
        conversas[chat_id][-12:]
    )

    prompt = f"""
Você é o Assistente Operacional DOPS.

Seu papel é ajudar um prestador de serviços a receber,
entender e organizar as solicitações enviadas pelos clientes.

Você está conversando diretamente com o cliente pelo Telegram.

Nome do cliente:
{nome}

HISTÓRICO DA CONVERSA:

{historico}


REGRAS OBRIGATÓRIAS:

1. Responda sempre em português brasileiro.

2. Fale diretamente com o cliente.

3. Use uma linguagem simples, natural, educada e profissional.

4. Não diga que você é Gemini, Google ou uma inteligência
artificial.

5. Não invente nenhuma informação.

6. Não invente preços.

7. Não determine valor de mão de obra.

8. Não forneça orçamento por conta própria.

9. Não faça diagnóstico técnico definitivo.

10. Não determine que um equipamento precisa obrigatoriamente
ser substituído ou reparado.

11. Decisões técnicas e comerciais pertencem ao profissional.

12. Seu objetivo inicial é entender o que o cliente precisa
e coletar as informações necessárias para o profissional
avaliar a solicitação.

13. Quando faltarem informações importantes, faça perguntas
objetivas.

14. Faça no máximo 3 perguntas por mensagem.

15. Nunca repita uma pergunta que o cliente já respondeu.

16. Analise todo o histórico antes de perguntar novamente.

17. Se o cliente responder apenas uma das perguntas,
reconheça a informação e pergunte somente o que ainda estiver
faltando.

18. Não prometa prazo.

19. Não prometa disponibilidade.

20. Não prometa preço.

21. Não diga que o serviço está confirmado.

22. Não diga que o orçamento está aprovado.

23. Quando já houver informações suficientes para o
profissional analisar a solicitação, informe ao cliente que
os dados foram organizados e serão encaminhados para análise
do profissional.

24. Seja breve. Evite textos muito longos.

25. Não use linguagem excessivamente robótica.


EXEMPLO DE CONVERSA:

Cliente:
"Quero trocar um chuveiro."

Resposta adequada:

"Certo! Para organizar sua solicitação, preciso de algumas
informações:

1. Em qual bairro será o serviço?
2. Você sabe se a instalação é 127V ou 220V?
3. Você já possui o chuveiro novo?"


Depois o cliente responde:

"É no Centro, 220V e já tenho o chuveiro."


Resposta adequada:

"Perfeito! Já organizei essas informações.

Vou encaminhar sua solicitação para análise do profissional."


IMPORTANTE:

Não copie exatamente os exemplos.
Responda naturalmente de acordo com a conversa real.

Agora responda somente à última mensagem do cliente.
"""

    resposta = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    if not resposta.text:
        raise ValueError(
            "Gemini não retornou uma resposta de texto."
        )

    texto_resposta = resposta.text.strip()

    # Salva também a resposta do DOPS no histórico
    conversas[chat_id].append(
        f"DOPS: {texto_resposta}"
    )

    return texto_resposta


# =========================================================
# BOT PRINCIPAL
# =========================================================

def iniciar_bot():

    print("======================================")
    print("DOPS Telegram + Gemini iniciado.")
    print("Modelo: Gemini 3.6 Flash")
    print("Aguardando mensagens...")
    print("======================================")

    offset = None

    while True:

        try:

            parametros = {
                "timeout": 30
            }

            if offset is not None:
                parametros["offset"] = offset

            resposta = requests.get(
                f"{TELEGRAM_URL}/getUpdates",
                params=parametros,
                timeout=35
            )

            resposta.raise_for_status()

            dados = resposta.json()

            for update in dados.get("result", []):

                offset = update["update_id"] + 1

                mensagem = update.get("message")

                # Ignora eventos que não sejam mensagens
                if not mensagem:
                    continue

                texto = mensagem.get("text")

                # Por enquanto trabalha apenas com texto
                if not texto:
                    continue

                chat_id = mensagem["chat"]["id"]

                nome = mensagem.get(
                    "from", {}
                ).get(
                    "first_name",
                    "Cliente"
                )

                # =========================================
                # COMANDO /START
                # =========================================

                if texto.strip().lower() == "/start":

                    # Limpa conversa antiga ao reiniciar
                    conversas[chat_id] = []

                    enviar_mensagem(
                        chat_id,
                        f"Olá, {nome}! 👋\n\n"
                        "Sou o assistente de atendimento.\n\n"
                        "Pode me contar qual serviço você precisa?"
                    )

                    continue

                # =========================================
                # MOSTRA NO LOG
                # =========================================

                print("--------------------------------------")
                print("Cliente:", nome)
                print("Chat ID:", chat_id)
                print("Mensagem:", texto)

                # =========================================
                # GEMINI
                # =========================================

                try:

                    resposta_ia = analisar_com_gemini(
                        chat_id,
                        nome,
                        texto
                    )

                    enviar_mensagem(
                        chat_id,
                        resposta_ia
                    )

                    print("Resposta DOPS:")
                    print(resposta_ia)

                except Exception as erro_ia:

                    print(
                        "Erro ao analisar com IA:",
                        repr(erro_ia)
                    )

                    enviar_mensagem(
                        chat_id,
                        "Recebi sua solicitação, mas tive "
                        "um problema ao organizar as informações. "
                        "Tente novamente em alguns instantes."
                    )

        except requests.exceptions.HTTPError as erro_http:

            print(
                "Erro HTTP do Telegram:",
                repr(erro_http)
            )

            time.sleep(5)

        except Exception as erro:

            print(
                "Erro geral do Telegram:",
                repr(erro)
            )

            time.sleep(5)


# =========================================================
# INICIAR
# =========================================================

if __name__ == "__main__":
    iniciar_bot()
