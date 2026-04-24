TRIBUNAIS = {
    "api_publica_trf1": {
        "nome": "TRF1",
        "alias": "api_publica_trf1",
        "consulta_url": "https://processual.trf1.jus.br/consultaProcessual/"
    },
    "api_publica_trt5": {
        "nome": "TRT5",
        "alias": "api_publica_trt5",
        "consulta_url": "https://pje.trt5.jus.br/consultaprocessual/"
    },
    "api_publica_tjba": {
        "nome": "TJBA",
        "alias": "api_publica_tjba",
        "consulta_url": "https://esaj.tjba.jus.br/cpopg/open.do"
    }
}


def detectar_tribunal(numero_processo):
    numero = (numero_processo or "").strip()

    if ".4.01." in numero:
        return "api_publica_trf1"
    elif ".5.05." in numero:
        return "api_publica_trt5"
    elif ".8.05." in numero:
        return "api_publica_tjba"

    return None


def obter_info_tribunal(codigo_tribunal):
    if not codigo_tribunal:
        return None

    return TRIBUNAIS.get(codigo_tribunal)


def obter_info_tribunal_por_numero(numero_processo):
    codigo = detectar_tribunal(numero_processo)
    if not codigo:
        return None

    info = TRIBUNAIS.get(codigo, {}).copy()
    info["codigo"] = codigo
    return info