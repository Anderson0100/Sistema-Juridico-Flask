import re
import unicodedata


def normalizar_texto(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def eh_encerramento_curto(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"[^\w\s]", "", texto).strip()

    frases = {
        "ok", "okk", "obrigado", "obg", "valeu", "certo",
        "beleza", "blz", "otimo", "ta bom", "bom trabalho",
        "otimo dia", "de nada", "thanks", "agradeco",
        "obrigado meu bem", "show", "tmj", "show valeu",
        "certo obrigado", "muito obrigado", "brigado"
    }

    return texto in frases


def eh_pedido_humano(texto):
    texto = normalizar_texto(texto)

    gatilhos = [
        "quero falar com advogado",
        "quero falar com o advogado",
        "quero falar com a secretaria",
        "quero falar com a secretária",
        "quero atendimento humano",
        "falar com atendente",
        "falar com uma pessoa",
        "me encaminhe",
        "me encaminhar",
        "preciso de atendimento humano",
        "quero falar com dr ",
        "quero falar com doutor ",
        "falar com dr ",
        "falar com doutor ",
        "quero o dr ",
        "quero o doutor ",
    ]

    return any(g in texto for g in gatilhos)


def detectar_assunto_sensivel(texto):
    texto = normalizar_texto(texto)

    gatilhos = [
        "valor", "honorario", "honorarios", "preco", "preço",
        "prazo judicial", "resultado garantido", "ganha a causa",
        "ganhar a causa", "certeza", "recurso urgente",
        "audiencia", "audiência", "sentenca", "sentença",
        "acordo", "pericia", "perícia", "documento novo",
        "documento juntado", "movimentacao", "movimentação",
        "cumprimento de sentenca", "cumprimento de sentença",
        "alvara", "alvará", "pagamento", "beneficio", "benefício",
        "aposentadoria", "inss", "prazo para resposta"
    ]

    return any(g in texto for g in gatilhos)


def resposta_insegura(resposta):
    texto = normalizar_texto(resposta)

    sinais = [
        "nao sei", "não sei",
        "nao tenho certeza", "não tenho certeza",
        "talvez", "possivelmente", "provavelmente",
        "acho que", "pode ser", "parece que"
    ]

    return any(s in texto for s in sinais)


def eh_duvida_sobre_consulta(texto):
    texto = normalizar_texto(texto)

    gatilhos = [
        "como consultar",
        "como faco para consultar",
        "como faço para consultar",
        "onde consultar",
        "onde vejo",
        "como vejo",
        "como acompanhar",
        "acompanhar processo",
        "consultar andamento",
        "ver andamento",
        "site do processo",
        "portal do processo",
        "link do processo",
        "como entro no portal",
        "quero consultar"
    ]

    return any(g in texto for g in gatilhos)