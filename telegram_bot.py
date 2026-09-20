import os
import time
import json
import requests

from datetime import datetime
from google import genai
from supabase import create_client


# =========================================================
# VARIÁVEIS DE AMBIENTE
# =========================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

SUPABASE_BOT_EMAIL = os.environ.get("SUPABASE_BOT_EMAIL")
SUPABASE_BOT_PASSWORD = os.environ.get("SUPABASE_BOT_PASSWORD")


variaveis = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_TOKEN,
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "SUPABASE_BOT_EMAIL": SUPABASE_BOT_EMAIL,
    "SUPABASE_BOT_PASSWORD": SUPABASE_BOT_PASSWORD,
}

for nome_variavel, valor in variaveis.items():
    if not valor:
        raise ValueError(
            f"{nome_variavel} não configurado."
        )


# =========================================================
# CLIENTES
# =========================================================

TELEGRAM_URL = (
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
)

gemini = genai.Client(
    api_key=GEMINI_API_KEY
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# AUTENTICAÇÃO SUPABASE
# =========================================================

def autenticar_supabase():

    try:

        resposta = supabase.auth.sign_in_with_password(
            {
                "email": SUPABASE_BOT_EMAIL,
                "password": SUPABASE_BOT_PASSWORD,
            }
        )

        if not resposta.session:
            raise ValueError(
                "Supabase não retornou sessão."
            )

        print("Supabase autenticado com sucesso.")

    except Exception as erro:

        print(
            "Erro ao autenticar no Supabase:",
            repr(erro)
        )

        raise


# =========================================================
# MEMÓRIA TEMPORÁRIA
# =========================================================

conversas = {}

# Impede que a mesma solicitação seja salva várias vezes
solicitacoes_salvas = set()


# =========================================================
# TELEGRAM
# =========================================================

def enviar_mensagem(chat_id, texto):

    resposta = requests.post(
        f"{TELEGRAM_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": texto,
        },
        timeout=30,
    )

    resposta.raise_for_status()


# =========================================================
# LIMPEZA DE JSON
# =========================================================

def limpar_json(texto):

    texto = texto.strip()

    if texto.startswith("```json"):
        texto = texto[7:]

    elif texto.startswith("```"):
        texto = texto[3:]

    if texto.endswith("```"):
        texto = texto[:-3]

    return texto.strip()


# =========================================================
# GEMINI - CONVERSA COM O CLIENTE
# =========================================================

def conversar_com_cliente(
    chat_id,
    nome,
    mensagem
):

    if chat_id not in conversas:
        conversas[chat_id] = []

    conversas[chat_id].append(
        {
            "autor": "cliente",
            "texto": mensagem,
        }
    )

    historico = "\n".join(
        [
            f"{item['autor']}: {item['texto']}"
            for item in conversas[chat_id][-14:]
        ]
    )

    prompt = f"""
Você é o Assistente Operacional DOPS.

Você conversa diretamente com clientes de um
prestador de serviços.

Seu objetivo é entender a solicitação e coletar
somente as informações necessárias para que o
profissional possa analisar o atendimento.

Nome do cliente:
{nome}

HISTÓRICO:

{historico}


REGRAS:

- Responda sempre em português brasileiro.
- Seja natural, breve, educado e profissional.
- Não invente informações.
- Não invente preços.
- Não determine mão de obra.
- Não forneça orçamento.
- Não faça diagnóstico técnico definitivo.
- Não tome decisões técnicas pelo profissional.
- Não prometa prazo.
- Não prometa disponibilidade.
- Não confirme a execução do serviço.
- Faça no máximo 3 perguntas por mensagem.
- Não repita informações que o cliente já informou.
- Analise todo o histórico.
- Pergunte somente informações realmente úteis
  para o profissional avaliar a solicitação.
- Quando já houver informações suficientes para
  uma avaliação inicial, não faça novas perguntas.

Para serviços elétricos simples, informações como
tipo de serviço, localização aproximada, tensão
quando relevante e se o cliente já possui o
equipamento podem ser suficientes para uma
avaliação inicial.

IMPORTANTE:

Você deve responder SOMENTE em JSON válido.

Formato obrigatório:

{{
    "concluido": false,
    "resposta_cliente": "mensagem para o cliente"
}}

Quando houver informações suficientes:

{{
    "concluido": true,
    "resposta_cliente": "Perfeito! Já organizei as informações. Vou encaminhar sua solicitação para análise do profissional."
}}

Não escreva nada fora do JSON.
"""

    resposta = gemini.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )

    if not resposta.text:
        raise ValueError(
            "Gemini não retornou texto."
        )

    texto_json = limpar_json(
        resposta.text
    )

    dados = json.loads(
        texto_json
    )

    resposta_cliente = dados.get(
        "resposta_cliente"
    )

    concluido = bool(
        dados.get("concluido", False)
    )

    if not resposta_cliente:
        raise ValueError(
            "Resposta do cliente não encontrada."
        )

    conversas[chat_id].append(
        {
            "autor": "DOPS",
            "texto": resposta_cliente,
        }
    )

    return concluido, resposta_cliente


# =========================================================
# GEMINI - ESTRUTURAÇÃO PARA O BANCO
# =========================================================

def estruturar_solicitacao(
    chat_id,
    nome
):

    historico = "\n".join(
        [
            f"{item['autor']}: {item['texto']}"
            for item in conversas.get(
                chat_id,
                []
            )
        ]
    )

    prompt = f"""
Você trabalha na organização operacional do DOPS.

Transforme a conversa abaixo em dados estruturados
para o profissional analisar.

Cliente:
{nome}

CONVERSA:

{historico}


REGRAS:

- Não invente informações.
- Não invente preços.
- Não invente materiais.
- Não faça diagnóstico técnico.
- Diferencie pedido do cliente de conclusão técnica.
- Se uma informação não estiver disponível,
  use "Não informado".
- O resumo deve ser curto e objetivo.
- categoria deve descrever a categoria geral.
- servico deve descrever o serviço solicitado ou
  que deverá ser avaliado pelo profissional.
- localizacao deve usar somente a localização
  realmente informada pelo cliente.

Responda SOMENTE em JSON válido:

{{
    "categoria": "",
    "servico": "",
    "localizacao": "",
    "resumo": ""
}}

Não escreva nada fora do JSON.
"""

    resposta = gemini.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )

    if not resposta.text:
        raise ValueError(
            "Gemini não retornou estrutura."
        )

    texto_json = limpar_json(
        resposta.text
    )

    dados = json.loads(
        texto_json
    )

    return dados


# =========================================================
# MENSAGEM ORIGINAL
# =========================================================

def obter_primeira_mensagem_cliente(
    chat_id
):

    for item in conversas.get(
        chat_id,
        []
    ):

        if item["autor"] == "cliente":
            return item["texto"]

    return "Não informado"


# =========================================================
# RESUMO COMPLETO DA CONVERSA
# =========================================================

def obter_conversa_para_observacoes(
    chat_id
):

    partes = []

    for item in conversas.get(
        chat_id,
        []
    ):

        partes.append(
            f"{item['autor']}: "
            f"{item['texto']}"
        )

    return "\n".join(partes)


# =========================================================
# SALVAR NO SUPABASE
# =========================================================

def salvar_no_supabase(
    chat_id,
    nome,
    dados
):

    if chat_id in solicitacoes_salvas:
        print(
            "Solicitação já salva:",
            chat_id
        )

        return

    agora = datetime.now()

    primeira_mensagem = (
        obter_primeira_mensagem_cliente(
            chat_id
        )
    )

    conversa_completa = (
        obter_conversa_para_observacoes(
            chat_id
        )
    )

    registro = {
        "data": agora.strftime(
            "%d/%m/%Y %H:%M"
        ),

        "cliente": nome,

        "categoria": dados.get(
            "categoria",
            "Não informado",
        ),

        "servico": dados.get(
            "servico",
            "Não informado",
        ),

        "localizacao": dados.get(
            "localizacao",
            "Não informado",
        ),

        "mensagem_original": primeira_mensagem,

        "resumo": dados.get(
            "resumo",
            "Não informado",
        ),

        "materiais": "",

        "valor_materiais": 0,

        "valor_mao_obra": 0,

        "valor_total": 0,

        "prazo": "",

        "observacoes": (
            "Origem: Telegram\n\n"
            + conversa_completa
        ),

        "status": "Em revisão",
    }

    resposta = (
        supabase
        .table("atendimentos")
        .insert(registro)
        .execute()
    )

    solicitacoes_salvas.add(
        chat_id
    )

    print(
        "Solicitação salva no Supabase."
    )

    print(
        "Resposta Supabase:",
        resposta.data
    )


# =========================================================
# PROCESSAR MENSAGEM
# =========================================================

def processar_mensagem(
    chat_id,
    nome,
    texto
):

    concluido, resposta_cliente = (
        conversar_com_cliente(
            chat_id,
            nome,
            texto,
        )
    )

    if concluido:

        try:

            dados = estruturar_solicitacao(
                chat_id,
                nome,
            )

            salvar_no_supabase(
                chat_id,
                nome,
                dados,
            )

        except Exception as erro:

            print(
                "Erro ao salvar solicitação:",
                repr(erro)
            )

            # Não expõe erro técnico ao cliente.
            # A conversa continua preservada.

    return resposta_cliente


# =========================================================
# BOT PRINCIPAL
# =========================================================

def iniciar_bot():

    autenticar_supabase()

    print(
        "======================================"
    )

    print(
        "DOPS Telegram + Gemini + Supabase"
    )

    print(
        "Modelo: Gemini 3.6 Flash"
    )

    print(
        "Aguardando mensagens..."
    )

    print(
        "======================================"
    )

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
                timeout=35,
            )

            resposta.raise_for_status()

            dados_telegram = resposta.json()

            for update in dados_telegram.get(
                "result",
                []
            ):

                offset = (
                    update["update_id"] + 1
                )

                mensagem = update.get(
                    "message"
                )

                if not mensagem:
                    continue

                texto = mensagem.get(
                    "text"
                )

                if not texto:
                    continue

                chat_id = mensagem[
                    "chat"
                ]["id"]

                nome = mensagem.get(
                    "from",
                    {},
                ).get(
                    "first_name",
                    "Cliente",
                )

                # -----------------------------------------
                # /START
                # -----------------------------------------

                if (
                    texto.strip().lower()
                    == "/start"
                ):

                    conversas[chat_id] = []

                    solicitacoes_salvas.discard(
                        chat_id
                    )

                    enviar_mensagem(
                        chat_id,
                        f"Olá, {nome}! 👋\n\n"
                        "Sou o assistente de atendimento.\n\n"
                        "Pode me contar qual serviço "
                        "você precisa?",
                    )

                    continue

                # -----------------------------------------
                # LOG
                # -----------------------------------------

                print(
                    "--------------------------------------"
                )

                print(
                    "Cliente:",
                    nome
                )

                print(
                    "Chat ID:",
                    chat_id
                )

                print(
                    "Mensagem:",
                    texto
                )

                # -----------------------------------------
                # PROCESSAMENTO
                # -----------------------------------------

                try:

                    resposta_dops = (
                        processar_mensagem(
                            chat_id,
                            nome,
                            texto,
                        )
                    )

                    enviar_mensagem(
                        chat_id,
                        resposta_dops,
                    )

                    print(
                        "Resposta DOPS:"
                    )

                    print(
                        resposta_dops
                    )

                except Exception as erro_ia:

                    print(
                        "Erro no processamento:",
                        repr(erro_ia)
                    )

                    enviar_mensagem(
                        chat_id,
                        "Recebi sua mensagem, mas tive "
                        "um problema ao organizar as "
                        "informações. Tente novamente "
                        "em alguns instantes.",
                    )

        except requests.exceptions.HTTPError as erro_http:

            print(
                "Erro HTTP Telegram:",
                repr(erro_http)
            )

            time.sleep(5)

        except Exception as erro:

            print(
                "Erro geral:",
                repr(erro)
            )

            time.sleep(5)


# =========================================================
# INICIAR
# =========================================================

if __name__ == "__main__":
    iniciar_bot()
