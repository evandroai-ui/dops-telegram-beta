import os
import time
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def enviar_mensagem(chat_id, texto):
    resposta = requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": texto
        },
        timeout=30
    )

    resposta.raise_for_status()


def iniciar_bot():
    print("DOPS Telegram iniciado.")
    print("Aguardando mensagens...")

    offset = None

    while True:
        try:
            parametros = {"timeout": 30}

            if offset is not None:
                parametros["offset"] = offset

            resposta = requests.get(
                f"{BASE_URL}/getUpdates",
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

                print("-------------------------")
                print("Cliente:", nome)
                print("Mensagem:", texto)

                enviar_mensagem(
                    chat_id,
                    f"Olá, {nome}! 👋\n\n"
                    "Recebi sua solicitação:\n\n"
                    f"“{texto}”\n\n"
                    "Estou organizando as informações "
                    "para o profissional."
                )

        except Exception as erro:
            print("Erro:", erro)
            time.sleep(5)


if __name__ == "__main__":
    iniciar_bot()
