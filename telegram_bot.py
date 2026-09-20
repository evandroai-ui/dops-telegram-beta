import os
import time
import requests
from google import genai

# =========================
# CONFIGURAÇÕES
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não configurado.")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = genai.Client(api_key=GEMINI_API_KEY)

# Guarda temporariamente o histórico de cada cliente.
# Depois vamos substituir isso pelo Supabase.
conversas = {}


# =========================
# TELEGRAM
# =========================

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


# =========================
# INTELIGÊNCIA DO DOPS
# =========================

def analisar_com_gemini(chat_id, nome, mensagem):

    if chat_id not in conversas:
        conversas[chat_id] = []

    conversas[chat_id].append(
        f"Cliente: {mensagem}"
    )

    historico = "\n".join(
        conversas[chat_id][-10:]
    )

    prompt = f"""
Você é o assistente operacional DOPS.

Seu papel é ajudar um prestador de serviços a coletar
e organizar as informações iniciais enviadas pelo cliente.

Nome do cliente:
{nome}

Histórico da conversa:
{historico}

REGRAS IMPORTANTES:

1. Responda sempre em português brasileiro.

2. Fale diretamente com o cliente de forma simples,
educada, natural e profissional.

3. Não invente informações.

4. Não invente preços.

5. Não faça diagnóstico técnico definitivo.

6. Não diga que determinado equipamento precisa ser
substituído ou reparado sem avaliação do profissional.

7. Nunca tome decisões técnicas pelo profissional.

8. Se faltarem informações importantes para entender
a solicitação, faça perguntas objetivas.

9. Faça no máximo 3 perguntas por mensagem.

10. Não repita perguntas que o cliente já respondeu.

11. Se já houver informações suficientes para o
profissional avaliar a solicitação, diga ao cliente que
as informações foram organizadas e serão encaminhadas
ao profissional.

12. Não prometa prazo, preço ou disponibilidade.

13. Seja breve. A resposta será enviada pelo Telegram.

EXEMPLO:

Cliente:
"Quero trocar um chuveiro."

Resposta adequada:
"Certo! Para organizar sua solicitação, preciso de
algumas informações:

1. Em qual bairro será o serviço?
2. Você sabe se a instalação é 127V ou 220V?
3. Você já possui o chuveiro novo?"

Agora responda à última mensagem do cliente.
"""

    resposta = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    texto_resposta = resposta.text.strip()

    conversas[chat_id].append(
        f"DOPS: {texto_resposta}"
    )

    return texto_resposta


# =========================
# BOT
# =========================

def iniciar_bot():

    print("DOPS Telegram + Gemini iniciado.")
    print("Aguardando mensagens...")

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

                if not mensagem:
                    continue

                texto = mensagem.get("text")

                if not texto:
                    continue

                chat_id = mensagem["chat"]["id"]

                nome = mensagem.get(
                    "from", {}
                ).get(
                    "first_name",
                    "Cliente"
                )

                # Ignora o comando inicial do Telegram
                if texto == "/start":

                    enviar_mensagem(
                        chat_id,
                        f"Olá, {nome}! 👋\n\n"
                        "Sou o assistente de atendimento.\n\n"
                        "Pode me contar qual serviço você precisa?"
                    )

                    continue

                print("-------------------------")
                print("Cliente:", nome)
                print("Mensagem:", texto)

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

                    print("Resposta DOPS:", resposta_ia)

                except Exception as erro_ia:

                    print(
                        "Erro ao analisar com IA:",
                        erro_ia
                    )

                    enviar_mensagem(
                        chat_id,
                        "Recebi sua solicitação, mas tive "
                        "um problema ao organizar as informações. "
                        "Tente novamente em alguns instantes."
                    )

        except Exception as erro:

            print("Erro no Telegram:", erro)

            time.sleep(5)


if __name__ == "__main__":
    iniciar_bot()
