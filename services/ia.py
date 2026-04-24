# services/ia.py

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ==========================
# INSTRUÇÕES FIXAS DO BOT
# ==========================
INSTRUCOES_ATENDIMENTO = """
Você é uma assistente virtual de um escritório de advocacia.

REGRAS OBRIGATÓRIAS:
- Responda de forma profissional, educada e objetiva.
- Não use intimidade (nada de "amigo", "querido", etc).
- Não invente informações.
- Não dê certeza sobre decisões judiciais.
- Não prometa resultados de processos.
- Não estime prazos judiciais sem base clara.
- Não interprete movimentações processuais como resultado final.
- Se faltar informação, diga claramente que não é possível confirmar.
- Se for um assunto que exige análise jurídica, oriente que a equipe irá verificar.

COMPORTAMENTO:
- Seja claro e direto.
- Use linguagem simples para o cliente entender.
- Evite textos longos.
- Nunca trate hipótese como fato.

QUANDO NÃO SOUBER:
- Diga algo como:
  "Para te orientar com segurança, o ideal é que a equipe do escritório verifique esse ponto."

OBJETIVO:
Ajudar de forma inicial e segura, sem substituir o advogado.
"""


# ==========================
# FUNÇÃO PRINCIPAL
# ==========================
def responder_cliente(mensagem, contexto=None):
    """
    Gera resposta segura para o cliente
    """

    try:
        contexto_texto = ""

        if contexto:
            nome = contexto.get("nome_cliente", "")
            processo = contexto.get("numero_processo", "")
            tribunal = contexto.get("tribunal_nome", "")

            if nome:
                contexto_texto += f"Cliente: {nome}\n"

            if processo:
                contexto_texto += f"Número do processo: {processo}\n"

            if tribunal:
                contexto_texto += f"Tribunal: {tribunal}\n"

        prompt = f"""
{INSTRUCOES_ATENDIMENTO}

CONTEXTO DISPONÍVEL:
{contexto_texto}

MENSAGEM DO CLIENTE:
{mensagem}

Responda com base apenas no contexto acima.
Se não tiver certeza, diga que precisa de verificação da equipe.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": INSTRUCOES_ATENDIMENTO},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # baixo = mais seguro
        )

        resposta = response.choices[0].message.content.strip()

        return resposta

    except Exception as e:
        print("Erro na IA:", e)

        return (
            "No momento não consegui gerar uma resposta com segurança.\n"
            "Vou encaminhar para a equipe do escritório verificar."
        )


# ==========================
# FUNÇÃO OPCIONAL DE VALIDAÇÃO
# ==========================
def resposta_segura(resposta):
    """
    Detecta respostas inseguras
    """

    texto = resposta.lower()

    sinais = [
        "acho que",
        "talvez",
        "provavelmente",
        "pode ser",
        "nao sei",
        "não sei",
        "não tenho certeza"
    ]

    return not any(s in texto for s in sinais)