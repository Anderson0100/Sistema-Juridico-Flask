import re


def limpar_numero(numero):
    return re.sub(r"\D", "", str(numero or ""))


def normalizar_telefone_brasil(telefone):
    """
    Salva no padrão:
    55 + DDD + número sem o 9 extra

    Exemplos:
    87 98795-2804 -> 558787952804
    87987952804   -> 558787952804
    5587987952804 -> 558787952804
    """
    numero = re.sub(r"\D", "", str(telefone or ""))

    if numero.startswith("55"):
        numero = numero[2:]

    if len(numero) < 10:
        return ""

    ddd = numero[:2]
    restante = numero[2:]

    if len(restante) == 9 and restante.startswith("9"):
        restante = restante[1:]

    return f"55{ddd}{restante}"