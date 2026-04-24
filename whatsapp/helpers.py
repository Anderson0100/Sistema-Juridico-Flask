from time import time

from services.whatsapp_service import enviar_mensagem
from utils.phone import limpar_numero
from utils.files import carregar_json_seguro, salvar_json_seguro
from whatsapp.state import (
    SESSOES_WHATSAPP,
    ATENDIMENTOS_HUMANOS,
    EVENTOS_PROCESSADOS,
    FILA_ATENDIMENTO,
    LOCK_MODO_HUMANO,
    LOCK_FILA,
)
from core.config import MODO_HUMANO_FILE, FILA_ATENDIMENTO_FILE, TTL_SESSAO, TTL_EVENTO


def carregar_modo_humano():
    return carregar_json_seguro(MODO_HUMANO_FILE, {})


def salvar_modo_humano_em_arquivo():
    salvar_json_seguro(MODO_HUMANO_FILE, ATENDIMENTOS_HUMANOS)


def carregar_fila():
    return carregar_json_seguro(FILA_ATENDIMENTO_FILE, [])


def salvar_fila():
    salvar_json_seguro(FILA_ATENDIMENTO_FILE, FILA_ATENDIMENTO)


def inicializar_estado_whatsapp():
    ATENDIMENTOS_HUMANOS.clear()
    ATENDIMENTOS_HUMANOS.update(carregar_modo_humano())

    FILA_ATENDIMENTO.clear()
    FILA_ATENDIMENTO.extend(carregar_fila())


def ativar_modo_humano(numero):
    numero = limpar_numero(numero)
    with LOCK_MODO_HUMANO:
        ATENDIMENTOS_HUMANOS[numero] = {
            "ativo": True,
            "desde": time()
        }
        salvar_modo_humano_em_arquivo()


def desativar_modo_humano(numero):
    numero = limpar_numero(numero)
    with LOCK_MODO_HUMANO:
        if numero in ATENDIMENTOS_HUMANOS:
            del ATENDIMENTOS_HUMANOS[numero]
            salvar_modo_humano_em_arquivo()


def esta_em_modo_humano(numero):
    numero = limpar_numero(numero)
    info = ATENDIMENTOS_HUMANOS.get(numero)
    return bool(info and info.get("ativo"))


def atualizar_posicoes_fila():
    for i, item in enumerate(FILA_ATENDIMENTO, start=1):
        item["posicao"] = i


def esta_na_fila(numero):
    numero = limpar_numero(numero)
    return any(item["numero"] == numero for item in FILA_ATENDIMENTO)


def adicionar_na_fila(numero, nome="", assunto=""):
    numero = limpar_numero(numero)

    with LOCK_FILA:
        for item in FILA_ATENDIMENTO:
            if item["numero"] == numero:
                if nome:
                    item["nome"] = nome
                if assunto:
                    item["assunto"] = assunto
                atualizar_posicoes_fila()
                salvar_fila()
                return item["posicao"]

        FILA_ATENDIMENTO.append({
            "numero": numero,
            "nome": nome,
            "assunto": assunto,
            "posicao": len(FILA_ATENDIMENTO) + 1,
            "entrada_em": time()
        })

        atualizar_posicoes_fila()
        salvar_fila()
        return FILA_ATENDIMENTO[-1]["posicao"]


def notificar_subida_fila(fila_antes, fila_depois):
    posicoes_antes = {item["numero"]: item["posicao"] for item in fila_antes}
    posicoes_depois = {item["numero"]: item["posicao"] for item in fila_depois}

    for numero, nova_posicao in posicoes_depois.items():
        posicao_antiga = posicoes_antes.get(numero)

        if posicao_antiga and nova_posicao < posicao_antiga:
            try:
                enviar_mensagem(
                    numero,
                    f"Seu atendimento avançou na fila.\n"
                    f"Nova posição: {nova_posicao}\n"
                    f"Total aguardando: {len(fila_depois)}"
                )
            except Exception as e:
                print(f"Erro ao notificar subida de fila para {numero}:", e)


def notificar_fila_vazia():
    if len(FILA_ATENDIMENTO) == 0:
        print("Fila vazia no momento.")


def remover_da_fila(numero):
    numero = limpar_numero(numero)

    with LOCK_FILA:
        fila_antes = [dict(item) for item in FILA_ATENDIMENTO]

        FILA_ATENDIMENTO[:] = [
            item for item in FILA_ATENDIMENTO
            if item["numero"] != numero
        ]

        atualizar_posicoes_fila()
        salvar_fila()

        fila_depois = [dict(item) for item in FILA_ATENDIMENTO]

    notificar_subida_fila(fila_antes, fila_depois)
    notificar_fila_vazia()


def obter_posicao_fila(numero):
    numero = limpar_numero(numero)
    for item in FILA_ATENDIMENTO:
        if item["numero"] == numero:
            return item["posicao"]
    return None


def total_na_fila():
    return len(FILA_ATENDIMENTO)


def obter_sessao(numero):
    agora = time()
    sessao = SESSOES_WHATSAPP.get(numero)

    if not sessao or (agora - sessao.get("updated_at", 0)) > TTL_SESSAO:
        sessao = {
            "apresentou_lia": False,
            "pediu_cpf": False,
            "pediu_nome": False,
            "cliente_identificado": False,
            "numero_processo": "",
            "nome_cliente": "",
            "atendimento_inicial": False,
            "encaminhado_humano": False,
            "modo_humano": False,
            "nome_ja_informado": False,
            "lead_qualificado": False,
            "menu_atual": "principal",
            "aguardando_opcao": True,
            "aguardando_cpf": False,
            "aguardando_nome": False,
            "aguardando_resumo": False,
            "aguardando_assunto": False,
            "assunto_atendimento": "",
            "fluxo": "",
            "updated_at": agora,
        }
        SESSOES_WHATSAPP[numero] = sessao

    if esta_em_modo_humano(numero):
        sessao["modo_humano"] = True

    sessao["updated_at"] = agora
    return sessao


def salvar_sessao(numero, sessao):
    sessao["updated_at"] = time()
    SESSOES_WHATSAPP[numero] = sessao


def resetar_fluxo_menu(sessao):
    sessao["menu_atual"] = "principal"
    sessao["aguardando_opcao"] = True
    sessao["aguardando_cpf"] = False
    sessao["aguardando_nome"] = False
    sessao["aguardando_resumo"] = False
    sessao["aguardando_assunto"] = False
    sessao["assunto_atendimento"] = ""
    sessao["fluxo"] = ""
    return sessao


def liberar_atendimento_humano(numero):
    numero = limpar_numero(numero)

    desativar_modo_humano(numero)

    if numero in SESSOES_WHATSAPP:
        SESSOES_WHATSAPP[numero]["modo_humano"] = False
        SESSOES_WHATSAPP[numero]["encaminhado_humano"] = False
        SESSOES_WHATSAPP[numero]["aguardando_opcao"] = True
        SESSOES_WHATSAPP[numero]["aguardando_cpf"] = False
        SESSOES_WHATSAPP[numero]["aguardando_nome"] = False
        SESSOES_WHATSAPP[numero]["aguardando_resumo"] = False
        SESSOES_WHATSAPP[numero]["aguardando_assunto"] = False
        SESSOES_WHATSAPP[numero]["assunto_atendimento"] = ""
        SESSOES_WHATSAPP[numero]["fluxo"] = ""
        SESSOES_WHATSAPP[numero]["updated_at"] = time()

    remover_da_fila(numero)

    try:
        enviar_mensagem(
            numero,
            "Seu atendimento foi finalizado.\n"
            "Se precisar de algo novo, posso te ajudar novamente por aqui."
        )
    except Exception as e:
        print("Erro ao enviar mensagem de encerramento:", e)

    print(f"IA liberada novamente para {numero}")
    return True


def limpar_eventos_processados():
    agora = time()
    expirados = [
        k for k, v in EVENTOS_PROCESSADOS.items()
        if agora - v > TTL_EVENTO
    ]

    for k in expirados:
        del EVENTOS_PROCESSADOS[k]


def extrair_evento_id(data):
    key_data = data.get("key", {}) or {}
    return (
        key_data.get("id")
        or data.get("messageId")
        or data.get("id")
        or ""
    )


def evento_ja_processado(evento_id):
    if not evento_id:
        return False

    limpar_eventos_processados()

    if evento_id in EVENTOS_PROCESSADOS:
        return True

    EVENTOS_PROCESSADOS[evento_id] = time()
    return False